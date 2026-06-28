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

from ..project import (
    Project,
    ProjectError,
    ProjectViewport,
    init_project,
    load_project,
    set_scan_path,
)
from ..scanner import CrawlBounds, SiteMap, crawl as _real_crawl


API_VERSION = "0.1.0"

DEFAULT_SCAN_FILENAME = "scan.json"


class RouteError(Exception):
    """Raised by a route to signal a non-500 error with an HTTP status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


_crawl: Callable[..., SiteMap] = _real_crawl
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
    ("POST", "/api/projects/scan"): _projects_scan,
    ("POST", "/api/projects/scan/save"): _projects_scan_save,
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
