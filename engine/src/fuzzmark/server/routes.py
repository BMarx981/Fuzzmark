"""Pure request handlers for the local HTTP API.

Each route is a function `(payload: dict) -> dict`. They never touch
sockets, so they're trivially callable from tests without a server. The
HTTP layer in `app.py` is a thin adapter that parses JSON, dispatches, and
serializes the response.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..baselines import ApprovalResult, apply_approval, plan_approval
from ..compare import DEFAULT_THRESHOLD, MaskRegion
from ..driver import RunResult, load_test, parse_test, run_flow as _real_run_flow
from ..extractor import (
    CTA,
    Field,
    Option,
    Validation,
    extract_ctas as _real_extract_ctas,
    extract_fields as _real_extract_fields,
)
from ..project import (
    Project,
    ProjectError,
    ProjectViewport,
    add_test_path,
    init_project,
    load_project,
    set_base_url,
    set_scan_path,
)
from ..report import Report, render_report
from ..scanner import CrawlBounds, SiteMap, crawl as _real_crawl
from ..suggestions import (
    CustomTablesError,
    Suggestion,
    load_custom_tables,
    merge_tables,
    suggest_all,
)


API_VERSION = "0.1.0"

DEFAULT_SCAN_FILENAME = "scan.json"
DEFAULT_RUNS_DIR = "runs"
DEFAULT_REPORTS_DIR = "reports"
RUN_RESULT_FILENAME = "result.json"


class RouteError(Exception):
    """Raised by a route to signal a non-500 error with an HTTP status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


_crawl: Callable[..., SiteMap] = _real_crawl
"""Injection seam: tests monkeypatch this to skip the browser."""

_extract_fields: Callable[..., list] = _real_extract_fields
"""Injection seam: tests monkeypatch this to skip the browser."""

_extract_ctas: Callable[..., list[CTA]] = _real_extract_ctas
"""Injection seam: tests monkeypatch this to skip the browser."""

_run_flow: Callable[..., RunResult] = _real_run_flow
"""Injection seam: tests monkeypatch this to skip the browser."""


def _health(_: dict) -> dict:
    return {"ok": True, "api_version": API_VERSION}


def _require_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RouteError(400, f"{key!r} is required")
    return value.strip()


def _projects_load(payload: dict) -> dict:
    path = _require_str(payload, "path")
    project = _load_project(path)
    return _project_payload(path, project)


def _projects_init(payload: dict) -> dict:
    path = _require_str(payload, "path")
    name = _require_str(payload, "name")
    base_url = _require_str(payload, "base_url")
    overwrite = bool(payload.get("force", False))
    viewports = tuple(_parse_viewport(v) for v in payload.get("viewports") or ())
    try:
        project = init_project(
            path,
            name=name,
            base_url=base_url,
            viewports=viewports,
            overwrite=overwrite,
        )
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc
    return _project_payload(path, project)


def _projects_set_base_url(payload: dict) -> dict:
    """Update a project's `base_url` and return the reparsed project."""
    path = _require_str(payload, "path")
    base_url = _require_str(payload, "base_url")
    project_file = Path(path)
    if not project_file.exists():
        raise RouteError(400, f"project file not found: {project_file}")
    try:
        project = set_base_url(project_file, base_url)
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc
    return _project_payload(path, project)


def _projects_scan(payload: dict) -> dict:
    """Crawl a project's base_url and return the discovered site map.

    The scan result is not persisted here; the caller decides what to keep
    by sending it back to `/api/projects/scan/save` with a selected subset.
    """
    path = _require_str(payload, "path")
    project = _load_project(path)
    bounds = _parse_bounds(payload)
    headed = bool(payload.get("headed", False))
    session = project.session_resolved
    session_arg = str(session) if session is not None else None
    try:
        site = _crawl(
            project.base_url,
            bounds,
            headless=not headed,
            session=session_arg,
        )
    except Exception as exc:  # noqa: BLE001 — surfaces as 500 with a tidy message
        raise RouteError(500, f"scan failed: {exc}") from exc
    return {"site_map": site.to_dict()}


def _projects_scan_save(payload: dict) -> dict:
    """Persist a (possibly filtered) site map and wire it into the project.

    Writes the JSON to `<source_dir>/<scan_filename>` (default `scan.json`)
    and updates the project file's `scan` field so the next load sees it.
    The site_map payload is written verbatim — filtering of pages happens
    on the client before save.
    """
    path = _require_str(payload, "path")
    site_map = payload.get("site_map")
    if not isinstance(site_map, dict):
        raise RouteError(400, "'site_map' must be a JSON object")
    filename = (payload.get("filename") or DEFAULT_SCAN_FILENAME).strip()
    if not filename or "/" in filename or "\\" in filename:
        raise RouteError(400, "'filename' must be a single path segment")

    project_file = Path(path)
    if not project_file.exists():
        raise RouteError(400, f"project file not found: {project_file}")
    scan_path = project_file.parent / filename
    try:
        scan_path.write_text(
            json.dumps(site_map, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        project = set_scan_path(project_file, filename)
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc
    out = _project_payload(path, project)
    out["scan_path"] = str(scan_path.resolve())
    return out


def _projects_pages(payload: dict) -> dict:
    """Return the pages of a project's saved scan, sans the link graph.

    The Test builder uses this to populate its page picker without re-running
    the crawl. Returns 400 when the project has no scan saved or the file
    referenced by the project no longer exists.
    """
    path = _require_str(payload, "path")
    project = _load_project(path)
    scan_path = project.scan_resolved
    if scan_path is None:
        raise RouteError(400, "project has no saved scan; run a scan first")
    if not scan_path.exists():
        raise RouteError(400, f"scan file not found: {scan_path}")
    try:
        site_map = json.loads(scan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouteError(400, f"scan file is not valid JSON: {exc}") from exc
    if not isinstance(site_map, dict):
        raise RouteError(400, "scan file must be a JSON object")
    pages = []
    for raw in site_map.get("pages") or ():
        if not isinstance(raw, dict):
            continue
        raw_ctas = raw.get("ctas")
        ctas = list(raw_ctas) if isinstance(raw_ctas, list) else []
        pages.append(
            {
                "url": raw.get("url"),
                "depth": raw.get("depth"),
                "title": raw.get("title"),
                "ctas": ctas,
                "error": raw.get("error"),
            }
        )
    return {"base_url": site_map.get("base_url", project.base_url), "pages": pages}


def _projects_extract(payload: dict) -> dict:
    """Extract interactive form fields from a page URL.

    Drives the browser-backed extractor under the project's saved session
    when present, so authenticated pages work. The injection seam is
    `_extract_fields`; tests stub it to skip Playwright entirely.
    """
    path = _require_str(payload, "path")
    url = _require_str(payload, "url")
    project = _load_project(path)
    session = project.session_resolved
    try:
        fields = _extract_fields(
            url,
            session=str(session) if session is not None else None,
        )
    except Exception as exc:  # noqa: BLE001
        raise RouteError(500, f"extract failed: {exc}") from exc
    return {"url": url, "fields": [_field_to_dict(f) for f in fields]}


def _projects_ctas(payload: dict) -> dict:
    """Extract clickable CTAs (buttons + link CTAs) from a page URL.

    Mirrors `_projects_extract`: drives the browser-backed CTA walker under
    the project's saved session when present. The injection seam is
    `_extract_ctas`; tests stub it to skip Playwright entirely.
    """
    path = _require_str(payload, "path")
    url = _require_str(payload, "url")
    project = _load_project(path)
    session = project.session_resolved
    try:
        ctas = _extract_ctas(
            url,
            session=str(session) if session is not None else None,
        )
    except Exception as exc:  # noqa: BLE001
        raise RouteError(500, f"ctas failed: {exc}") from exc
    return {"url": url, "ctas": [c.to_dict() for c in ctas]}


def _projects_suggest(payload: dict) -> dict:
    """Generate suggestions for a list of fields against the project's tables.

    Pure: no browser. Honors the project's custom-tables file when present.
    The `fields` payload uses the same shape `_projects_extract` returns.
    """
    path = _require_str(payload, "path")
    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list):
        raise RouteError(400, "'fields' must be a list")
    project = _load_project(path)
    fields = [_field_from_dict(item, idx) for idx, item in enumerate(raw_fields)]
    tables_path = project.tables_resolved
    if tables_path is not None:
        try:
            tables = merge_tables(load_custom_tables(tables_path))
        except (CustomTablesError, OSError) as exc:
            raise RouteError(400, f"custom tables load failed: {exc}") from exc
    else:
        tables = None
    suggestions = suggest_all(fields, tables=tables)
    return {
        "suggestions": {
            selector: [s.to_dict() for s in items]
            for selector, items in suggestions.items()
        }
    }


def _projects_tests_save(payload: dict) -> dict:
    """Persist a Test JSON file under the project and link it into the manifest.

    Validates the test body via `driver.parse_test` so what the engine writes
    is guaranteed loadable. The file is placed at `<source_dir>/<filename>`
    (default `tests/<sanitized-name>.json`). The project file's `tests` list
    is updated to include the relative path.
    """
    path = _require_str(payload, "path")
    test_raw = payload.get("test")
    if not isinstance(test_raw, dict):
        raise RouteError(400, "'test' must be a JSON object")
    try:
        validated = parse_test(test_raw)
    except ValueError as exc:
        raise RouteError(400, f"invalid test: {exc}") from exc

    project_file = Path(path)
    if not project_file.exists():
        raise RouteError(400, f"project file not found: {project_file}")

    filename = payload.get("filename")
    if filename is None:
        filename = f"tests/{_safe_name(validated.name)}.json"
    if not isinstance(filename, str) or not filename.strip():
        raise RouteError(400, "'filename' must be a non-empty string")
    filename = filename.strip()
    if filename.startswith("/") or ".." in Path(filename).parts:
        raise RouteError(400, "'filename' must be a relative, non-escaping path")
    overwrite = bool(payload.get("force", False))

    target = project_file.parent / filename
    if target.exists() and not overwrite:
        raise RouteError(400, f"refusing to overwrite existing file: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(validated.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        project = add_test_path(project_file, filename)
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc

    out = _project_payload(path, project)
    out["test_path"] = str(target.resolve())
    return out


def _projects_tests_run(payload: dict) -> dict:
    """Execute one of the project's tests and return the RunResult.

    The test is identified by `test` — either a path relative to the project
    directory (matching what `project.tests` stores) or an absolute path that
    must resolve under the project root. Screenshots and a `result.json` are
    written to `<source_dir>/runs/<test-stem>/`, overwritten on each run.
    The injection seam is `_run_flow`; tests stub it to skip Playwright.
    """
    path = _require_str(payload, "path")
    test_rel = _require_str(payload, "test")
    project = _load_project(path)

    test_path = _resolve_project_relative(project, test_rel, "test")
    if not test_path.exists():
        raise RouteError(400, f"test file not found: {test_path}")
    try:
        test = load_test(test_path)
    except (ValueError, OSError) as exc:
        raise RouteError(400, f"invalid test: {exc}") from exc

    run_dir = project.source_dir / DEFAULT_RUNS_DIR / _safe_name(test_path.stem)
    run_dir.mkdir(parents=True, exist_ok=True)

    session = project.session_resolved
    viewport = _resolve_viewport(project)
    try:
        result = _run_flow(
            test,
            run_dir,
            viewport=viewport,
            headless=not bool(payload.get("headed", False)),
            session=str(session) if session is not None else None,
        )
    except Exception as exc:  # noqa: BLE001 — surfaces as 500 with a tidy message
        raise RouteError(500, f"run failed: {exc}") from exc

    result_dict = result.to_dict()
    result_path = run_dir / RUN_RESULT_FILENAME
    result_path.write_text(
        json.dumps(result_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "result": result_dict,
        "run_dir": str(run_dir.resolve()),
        "result_path": str(result_path.resolve()),
    }


def _projects_tests_report(payload: dict) -> dict:
    """Render a report from a run result and return the populated Report dict.

    The HTML index + copied images land at `<source_dir>/reports/<test-stem>/`,
    overwritten on each call. `baselines_dir` defaults to the project's
    `baselines_resolved` so per-step diffs surface as soon as baselines exist.
    """
    path = _require_str(payload, "path")
    run_result = payload.get("result")
    if not isinstance(run_result, dict):
        raise RouteError(400, "'result' must be a JSON object (a RunResult dict)")
    project = _load_project(path)

    threshold = _opt_threshold(payload.get("threshold"))
    masks = _parse_named_masks(payload.get("masks"))

    test_name = (run_result.get("test_name") or "report").strip() or "report"
    out_dir = project.source_dir / DEFAULT_REPORTS_DIR / _safe_name(test_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    baselines = project.baselines_resolved
    try:
        report = render_report(
            run_result,
            out_dir,
            baselines_dir=str(baselines) if baselines is not None else None,
            threshold=threshold,
            masks=masks,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise RouteError(400, f"render report failed: {exc}") from exc

    return {
        "report": report.to_dict(),
        "report_dir": str(out_dir.resolve()),
        "index_path": report.index_path,
        "baselines_dir": str(baselines.resolve()) if baselines is not None else None,
    }


def _projects_baselines_approve(payload: dict) -> dict:
    """Promote captures from a run result into the project's baselines directory.

    Requires the project to declare a `baselines` path. Accepts an optional
    `captures: [name, ...]` whitelist and a `dry_run` flag mirroring the CLI.
    """
    path = _require_str(payload, "path")
    run_result = payload.get("result")
    if not isinstance(run_result, dict):
        raise RouteError(400, "'result' must be a JSON object (a RunResult dict)")
    project = _load_project(path)

    baselines = project.baselines_resolved
    if baselines is None:
        raise RouteError(
            400,
            "project has no 'baselines' path; set one before approving captures",
        )

    captures_raw = payload.get("captures")
    capture_names: list[str] | None = None
    if captures_raw is not None:
        if not isinstance(captures_raw, list) or not all(
            isinstance(c, str) and c.strip() for c in captures_raw
        ):
            raise RouteError(
                400, "'captures' must be a list of non-empty strings when present"
            )
        capture_names = [c.strip() for c in captures_raw]

    dry_run = bool(payload.get("dry_run", False))

    plan = plan_approval(run_result, baselines, capture_names=capture_names)
    result = apply_approval(plan, dry_run=dry_run)
    return result.to_dict()


def _opt_threshold(value: object) -> float:
    if value is None:
        return DEFAULT_THRESHOLD
    if isinstance(value, bool):
        raise RouteError(400, "'threshold' must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RouteError(400, f"'threshold' must be a number: {exc}") from exc


def _parse_named_masks(
    raw: object,
) -> dict[str, list[MaskRegion]] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise RouteError(400, "'masks' must be an object keyed by capture name")
    out: dict[str, list[MaskRegion]] = {}
    for name, regions in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise RouteError(400, "'masks' keys must be non-empty strings")
        if not isinstance(regions, list):
            raise RouteError(
                400, f"masks[{name!r}] must be a list of mask regions"
            )
        parsed: list[MaskRegion] = []
        for idx, region in enumerate(regions):
            if not isinstance(region, dict):
                raise RouteError(400, f"masks[{name!r}][{idx}] must be an object")
            try:
                parsed.append(
                    MaskRegion(
                        x=int(region["x"]),
                        y=int(region["y"]),
                        width=int(region["width"]),
                        height=int(region["height"]),
                        source=str(region.get("source", "region")),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RouteError(
                    400, f"masks[{name!r}][{idx}]: {exc}"
                ) from exc
        out[name] = parsed
    return out


def _resolve_project_relative(project: Project, raw: str, label: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (project.source_dir / candidate).resolve()
    try:
        resolved.relative_to(project.source_dir.resolve())
    except ValueError as exc:
        raise RouteError(400, f"{label!r} must resolve inside the project directory") from exc
    return resolved


def _resolve_viewport(project: Project) -> tuple[int, int]:
    if project.viewports:
        first = project.viewports[0]
        return (first.width, first.height)
    return (1280, 800)


def _field_to_dict(field: Field) -> dict:
    return field.to_dict()


def _field_from_dict(raw: object, idx: int) -> Field:
    if not isinstance(raw, dict):
        raise RouteError(400, f"fields[{idx}] must be a JSON object")
    try:
        validation_raw = raw.get("validation") or {}
        if not isinstance(validation_raw, dict):
            raise RouteError(400, f"fields[{idx}].validation must be a JSON object")
        validation = Validation(
            required=bool(validation_raw.get("required", False)),
            maxlength=_opt_int(validation_raw.get("maxlength")),
            minlength=_opt_int(validation_raw.get("minlength")),
            min=_opt_str(validation_raw.get("min")),
            max=_opt_str(validation_raw.get("max")),
            step=_opt_str(validation_raw.get("step")),
            pattern=_opt_str(validation_raw.get("pattern")),
            accept=_opt_str(validation_raw.get("accept")),
        )
        options_raw = raw.get("options") or []
        if not isinstance(options_raw, list):
            raise RouteError(400, f"fields[{idx}].options must be a list")
        options = [
            Option(value=str(o.get("value", "")), label=str(o.get("label", "")))
            for o in options_raw
            if isinstance(o, dict)
        ]
        return Field(
            selector=_require_field(raw, "selector", idx),
            kind=_require_field(raw, "kind", idx),
            type=_opt_str(raw.get("type")),
            name=_opt_str(raw.get("name")),
            id=_opt_str(raw.get("id")),
            label=_opt_str(raw.get("label")),
            validation=validation,
            options=options,
        )
    except (TypeError, ValueError) as exc:
        raise RouteError(400, f"fields[{idx}]: {exc}") from exc


def _require_field(raw: dict, key: str, idx: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise RouteError(400, f"fields[{idx}].{key} must be a non-empty string")
    return value


def _opt_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("bool is not a valid integer")
    return int(value)


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expected a string")
    return value


def _safe_name(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip("-")
    return cleaned or "test"


def _parse_bounds(payload: dict) -> CrawlBounds:
    defaults = CrawlBounds()
    try:
        max_depth = int(payload.get("max_depth", defaults.max_depth))
        max_pages = int(payload.get("max_pages", defaults.max_pages))
        rate_limit = float(payload.get("rate_limit", defaults.rate_limit_seconds))
    except (TypeError, ValueError) as exc:
        raise RouteError(400, f"invalid crawl bound: {exc}") from exc
    if max_depth < 0:
        raise RouteError(400, "'max_depth' must be >= 0")
    if max_pages <= 0:
        raise RouteError(400, "'max_pages' must be > 0")
    if rate_limit < 0:
        raise RouteError(400, "'rate_limit' must be >= 0")
    return CrawlBounds(
        max_depth=max_depth,
        max_pages=max_pages,
        same_origin=not bool(payload.get("allow_cross_origin", False)),
        respect_robots=not bool(payload.get("ignore_robots", False)),
        rate_limit_seconds=rate_limit,
        user_agent=defaults.user_agent,
    )


def _parse_viewport(spec: object) -> ProjectViewport:
    if not isinstance(spec, dict):
        raise RouteError(400, "each viewport must be a JSON object")
    try:
        name = str(spec["name"]).strip()
        width = int(spec["width"])
        height = int(spec["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RouteError(
            400, "viewport requires 'name' (str), 'width' (int), 'height' (int)"
        ) from exc
    if not name:
        raise RouteError(400, "viewport 'name' must be non-empty")
    if width <= 0 or height <= 0:
        raise RouteError(400, "viewport width/height must be positive")
    return ProjectViewport(name=name, width=width, height=height)


def _load_project(path: str) -> Project:
    try:
        return load_project(path)
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc


def _project_payload(path: str, project: Project) -> dict:
    out = project.to_dict()
    out["path"] = str(Path(path).resolve())
    out["resolved"] = {
        "source_dir": str(project.source_dir),
        "session": _path_or_none(project.session_resolved),
        "tables": _path_or_none(project.tables_resolved),
        "scan": _path_or_none(project.scan_resolved),
        "baselines": _path_or_none(project.baselines_resolved),
        "tests": [str(p) for p in project.tests_resolved],
    }
    return out


def _path_or_none(p: Path | None) -> str | None:
    return str(p) if p is not None else None


Route = Callable[[dict], dict]

ROUTES: dict[tuple[str, str], Route] = {
    ("GET", "/api/health"): _health,
    ("POST", "/api/projects/load"): _projects_load,
    ("POST", "/api/projects/init"): _projects_init,
    ("POST", "/api/projects/base_url"): _projects_set_base_url,
    ("POST", "/api/projects/scan"): _projects_scan,
    ("POST", "/api/projects/scan/save"): _projects_scan_save,
    ("POST", "/api/projects/pages"): _projects_pages,
    ("POST", "/api/projects/extract"): _projects_extract,
    ("POST", "/api/projects/ctas"): _projects_ctas,
    ("POST", "/api/projects/suggest"): _projects_suggest,
    ("POST", "/api/projects/tests/save"): _projects_tests_save,
    ("POST", "/api/projects/tests/run"): _projects_tests_run,
    ("POST", "/api/projects/tests/report"): _projects_tests_report,
    ("POST", "/api/projects/baselines/approve"): _projects_baselines_approve,
}


def dispatch(method: str, path: str, payload: dict) -> dict:
    """Find and invoke the route for (method, path).

    Raises `RouteError(404)` when no route matches. Route exceptions
    propagate as-is.
    """
    handler = ROUTES.get((method.upper(), path))
    if handler is None:
        raise RouteError(404, f"no route for {method} {path}")
    return handler(payload)
