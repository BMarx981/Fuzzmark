"""Command-line interface for the QA engine."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path

from .baselines import apply_approval, plan_approval
from .capture import capture_page
from .compare import DEFAULT_THRESHOLD, MaskRegion, compare_images, parse_mask_spec
from .driver import load_test, run_flow
from .extractor import extract_ctas, extract_fields, extract_site
from .mobile import (
    SimctlError,
    capture_app as mobile_capture_app,
    check_mobile_test,
    list_devices as mobile_list_devices,
    load_mobile_test,
    run_mobile_flow,
    simctl_available,
)
from .project import Project, ProjectError, ProjectViewport, init_project, load_project
from .report import render_report
from .scanner import CrawlBounds, crawl
from .server import serve_forever
from .sessions import SessionError, capture_session, validate_session
from .suggestions import load_custom_tables, merge_tables, suggest, suggest_site


DEFAULT_VIEWPORT = (1280, 800)


def _cmd_extract(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    session = _resolve_session_arg(args, project)
    scan_path = _resolve_scan_arg(args, project)
    reveal = max(0, int(getattr(args, "reveal", 0) or 0))
    if scan_path:
        site_map = json.loads(open(scan_path, encoding="utf-8").read())
        extractor = lambda url: extract_fields(
            url, headless=not args.headed, session=session, reveal=reveal
        )
        payload = extract_site(site_map, extractor=extractor, include=args.include or None)
    else:
        url = args.url or (project.base_url if project else None)
        if not url:
            raise SystemExit(
                "extract: pass a URL, --scan <site-map.json>, or --project <project.json>"
            )
        fields = extract_fields(url, headless=not args.headed, session=session, reveal=reveal)
        payload = {
            "url": url,
            "field_count": len(fields),
            "fields": [f.to_dict() for f in fields],
        }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_suggest(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    tables_path = _resolve_tables_arg(args, project)
    tables = merge_tables(load_custom_tables(tables_path)) if tables_path else None
    session = _resolve_session_arg(args, project)
    scan_path = _resolve_scan_arg(args, project)
    reveal = max(0, int(getattr(args, "reveal", 0) or 0))
    if scan_path:
        site_map = json.loads(open(scan_path, encoding="utf-8").read())
        extractor = lambda url: extract_fields(
            url, headless=not args.headed, session=session, reveal=reveal
        )
        site = extract_site(site_map, extractor=extractor, include=args.include or None)
        payload = suggest_site(site, tables=tables)
    else:
        url = args.url or (project.base_url if project else None)
        if not url:
            raise SystemExit(
                "suggest: pass a URL, --scan <site-map.json>, or --project <project.json>"
            )
        fields = extract_fields(url, headless=not args.headed, session=session, reveal=reveal)
        items = []
        for field in fields:
            suggestions = suggest(field, tables=tables)
            items.append(
                {
                    "selector": field.selector,
                    "kind": field.kind,
                    "type": field.type,
                    "label": field.label,
                    "suggestion_count": len(suggestions),
                    "suggestions": [s.to_dict() for s in suggestions],
                }
            )
        payload = {
            "url": url,
            "field_count": len(fields),
            "fields": items,
        }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_ctas(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    session = _resolve_session_arg(args, project)
    url = args.url or (project.base_url if project else None)
    if not url:
        raise SystemExit("ctas: pass a URL, or --project <project.json>")
    ctas = extract_ctas(url, headless=not args.headed, session=session)
    payload = {
        "url": url,
        "cta_count": len(ctas),
        "ctas": [c.to_dict() for c in ctas],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_capture(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    session = _resolve_session_arg(args, project)
    result = capture_page(
        args.url,
        args.output,
        viewport=_resolve_viewport(args, project),
        full_page=not args.viewport_only,
        headless=not args.headed,
        session=session,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_run(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    test = load_test(args.test)
    session = _resolve_session_arg(args, project)
    result = run_flow(
        test,
        args.out,
        viewport=_resolve_viewport(args, project),
        headless=not args.headed,
        session=session,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _resolve_session_arg(
    args: argparse.Namespace, project: Project | None = None
) -> str | None:
    """Validate `--session` if provided; return the resolved path or None.

    Falls back to the project's `session` path when `--session` is not set.
    """
    path = getattr(args, "session", None)
    if not path and project is not None and project.session_resolved is not None:
        path = str(project.session_resolved)
    if not path:
        return None
    try:
        validate_session(path)
    except SessionError as exc:
        raise SystemExit(f"--session: {exc}") from exc
    return path


def _load_project_arg(args: argparse.Namespace) -> Project | None:
    """Load a `--project` file if provided; otherwise return None."""
    path = getattr(args, "project", None)
    if not path:
        return None
    try:
        return load_project(path)
    except ProjectError as exc:
        raise SystemExit(f"--project: {exc}") from exc


def _resolve_viewport(
    args: argparse.Namespace, project: Project | None
) -> tuple[int, int]:
    """Resolve width/height: explicit flags > project's first viewport > built-in default."""
    w, h = args.width, args.height
    if w is None and project is not None and project.viewports:
        w = project.viewports[0].width
    if h is None and project is not None and project.viewports:
        h = project.viewports[0].height
    return (w or DEFAULT_VIEWPORT[0], h or DEFAULT_VIEWPORT[1])


def _resolve_scan_arg(
    args: argparse.Namespace, project: Project | None
) -> str | None:
    path = getattr(args, "scan", None)
    if not path and project is not None and project.scan_resolved is not None:
        path = str(project.scan_resolved)
    return path


def _resolve_tables_arg(
    args: argparse.Namespace, project: Project | None
) -> str | None:
    path = getattr(args, "tables", None)
    if not path and project is not None and project.tables_resolved is not None:
        path = str(project.tables_resolved)
    return path


def _resolve_baselines_arg(
    value: str | None, project: Project | None
) -> str | None:
    if value:
        return value
    if project is not None and project.baselines_resolved is not None:
        return str(project.baselines_resolved)
    return None


def _default_log_path() -> Path:
    """Return the engine log file path for this platform."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs" / "fuzzmark"
    else:
        state = os.environ.get("XDG_STATE_HOME")
        base = Path(state) / "fuzzmark" if state else Path.home() / ".local" / "state" / "fuzzmark"
    return base / "engine.log"


def _configure_serve_logging(log_path: Path) -> None:
    """Send engine logs to `log_path` (rotated) + stderr at INFO."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_h = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_h.setFormatter(fmt)
    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setFormatter(fmt)
    root.handlers.clear()
    root.addHandler(file_h)
    root.addHandler(stderr_h)


def _cmd_serve(args: argparse.Namespace) -> None:
    log_path = Path(args.log_file) if args.log_file else _default_log_path()
    _configure_serve_logging(log_path)
    logging.getLogger(__name__).info("fuzzmark serve logging to %s", log_path)
    print(f"fuzzmark serve logging to {log_path}", file=sys.stderr, flush=True)
    serve_forever(host=args.host, port=args.port)


def _cmd_session(args: argparse.Namespace) -> None:
    result = capture_session(
        args.url,
        args.out,
        wait_for_url=args.wait_for_url,
        timeout_s=args.timeout,
        headless=args.headless,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_report(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    data = json.loads(open(args.result, encoding="utf-8").read())
    masks = _parse_named_masks(args.mask or [])
    report = render_report(
        data,
        args.out,
        baselines_dir=_resolve_baselines_arg(args.baselines, project),
        threshold=args.threshold,
        masks=masks or None,
    )
    json.dump(report.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _parse_named_masks(specs: list[str]) -> dict[str, list[MaskRegion]]:
    out: dict[str, list[MaskRegion]] = {}
    for spec in specs:
        if ":" not in spec:
            raise SystemExit(
                f"--mask must be 'capture_name:x,y,w,h[,source]'; got {spec!r}"
            )
        name, rest = spec.split(":", 1)
        name = name.strip()
        if not name:
            raise SystemExit(f"--mask missing capture name in {spec!r}")
        out.setdefault(name, []).append(parse_mask_spec(rest))
    return out


def _cmd_approve(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    data = json.loads(open(args.result, encoding="utf-8").read())
    captures = _split_csv(args.captures)
    baselines = _resolve_baselines_arg(args.baselines, project)
    if not baselines:
        raise SystemExit(
            "approve: --baselines is required (or set 'baselines' in --project)"
        )
    plan = plan_approval(data, baselines, capture_names=captures)
    result = apply_approval(plan, dry_run=args.dry_run)
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if not result.written and not args.dry_run:
        sys.exit(1)


def _split_csv(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or None


def _cmd_scan(args: argparse.Namespace) -> None:
    project = _load_project_arg(args)
    url = args.url or (project.base_url if project else None)
    if not url:
        raise SystemExit("scan: pass a URL or --project <project.json>")
    bounds = CrawlBounds(
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        same_origin=not args.allow_cross_origin,
        respect_robots=not args.ignore_robots,
        rate_limit_seconds=args.rate_limit,
    )
    session = _resolve_session_arg(args, project)
    site = crawl(url, bounds, headless=not args.headed, session=session)
    json.dump(site.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_project_init(args: argparse.Namespace) -> None:
    viewports = tuple(_parse_viewport_spec(spec) for spec in (args.viewport or []))
    try:
        project = init_project(
            args.path,
            name=args.name,
            base_url=args.base_url,
            viewports=viewports,
            overwrite=args.force,
        )
    except ProjectError as exc:
        raise SystemExit(f"project init: {exc}") from exc
    payload = {
        "path": str(Path(args.path).resolve()),
        "project": project.to_dict(),
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_project_show(args: argparse.Namespace) -> None:
    try:
        project = load_project(args.path)
    except ProjectError as exc:
        raise SystemExit(f"project show: {exc}") from exc
    out = project.to_dict()
    out["resolved"] = {
        "source_dir": str(project.source_dir),
        "session": _path_or_none(project.session_resolved),
        "tables": _path_or_none(project.tables_resolved),
        "scan": _path_or_none(project.scan_resolved),
        "baselines": _path_or_none(project.baselines_resolved),
        "tests": [str(p) for p in project.tests_resolved],
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _path_or_none(p: Path | None) -> str | None:
    return str(p) if p is not None else None


def _parse_viewport_spec(spec: str) -> ProjectViewport:
    """Parse 'name:WIDTHxHEIGHT' (e.g. 'desktop:1280x800') into a ProjectViewport."""
    if ":" not in spec:
        raise SystemExit(
            f"--viewport must be 'name:WIDTHxHEIGHT'; got {spec!r}"
        )
    name, dims = spec.split(":", 1)
    name = name.strip()
    if not name:
        raise SystemExit(f"--viewport missing name in {spec!r}")
    if "x" not in dims:
        raise SystemExit(
            f"--viewport dims must be WIDTHxHEIGHT; got {dims!r} in {spec!r}"
        )
    w_str, h_str = dims.split("x", 1)
    try:
        width = int(w_str)
        height = int(h_str)
    except ValueError as exc:
        raise SystemExit(
            f"--viewport width/height must be integers in {spec!r}"
        ) from exc
    if width <= 0 or height <= 0:
        raise SystemExit(
            f"--viewport width/height must be positive in {spec!r}"
        )
    return ProjectViewport(name=name, width=width, height=height)


def _cmd_sim_devices(args: argparse.Namespace) -> None:
    if not simctl_available():
        raise SystemExit(
            "sim-devices: `xcrun simctl` not available; install Xcode command-line tools"
        )
    try:
        devices = mobile_list_devices(available_only=not args.all)
    except SimctlError as exc:
        raise SystemExit(f"sim-devices: {exc}") from exc
    payload = {"devices": [d.__dict__ for d in devices]}
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_sim_capture(args: argparse.Namespace) -> None:
    if not simctl_available():
        raise SystemExit(
            "sim-capture: `xcrun simctl` not available; install Xcode command-line tools"
        )
    try:
        result = mobile_capture_app(
            args.app,
            args.output,
            device_name=args.device,
            runtime_contains=args.runtime,
            bundle_id=args.bundle_id,
            settle_seconds=args.settle,
            terminate_after=args.terminate_after,
            stabilize_status_bar=not args.no_stabilize_status_bar,
        )
    except SimctlError as exc:
        raise SystemExit(f"sim-capture: {exc}") from exc
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_sim_run(args: argparse.Namespace) -> None:
    if not simctl_available():
        raise SystemExit(
            "sim-run: `xcrun simctl` not available; install Xcode command-line tools"
        )
    try:
        test = load_mobile_test(args.test)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"sim-run: {exc}") from exc
    try:
        result = run_mobile_flow(
            test,
            args.out,
            launch_settle_seconds=args.settle,
            stabilize_status_bar=not args.no_stabilize_status_bar,
        )
    except SimctlError as exc:
        raise SystemExit(f"sim-run: {exc}") from exc
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_sim_check(args: argparse.Namespace) -> None:
    if not simctl_available():
        raise SystemExit(
            "sim-check: `xcrun simctl` not available; install Xcode command-line tools"
        )
    project = _load_project_arg(args)
    try:
        test = load_mobile_test(args.test)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"sim-check: {exc}") from exc
    masks = _parse_named_masks(args.mask or [])
    baselines = _resolve_baselines_arg(args.baselines, project)
    report_dir = Path(args.report_out) if args.report_out else Path(args.out) / "report"
    try:
        check = check_mobile_test(
            test,
            args.out,
            report_dir=report_dir,
            baselines_dir=baselines,
            threshold=args.threshold,
            masks=masks or None,
            launch_settle_seconds=args.settle,
            stabilize_status_bar=not args.no_stabilize_status_bar,
        )
    except SimctlError as exc:
        raise SystemExit(f"sim-check: {exc}") from exc
    json.dump(check.report.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.exit(0 if check.passed else 1)


def _cmd_compare(args: argparse.Namespace) -> None:
    masks = [parse_mask_spec(spec) for spec in (args.mask or [])]
    result = compare_images(
        args.baseline,
        args.candidate,
        threshold=args.threshold,
        diff_path=args.diff_out,
        masks=masks or None,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(0 if result.verdict == "pass" else 1)


def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        default=None,
        metavar="PATH",
        help="Path to a Fuzzmark project JSON; supplies defaults for missing flags",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fuzzmark", description="Scan-first QA engine")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser(
        "extract",
        help="Extract form fields from a page (or every page in a scan)",
    )
    extract.add_argument(
        "url",
        nargs="?",
        help="Page URL; omit when using --scan or --project's base_url",
    )
    extract.add_argument(
        "--scan",
        default=None,
        help="Path to a `fuzzmark scan` result JSON; extract from each page in it",
    )
    extract.add_argument(
        "--include",
        action="append",
        default=None,
        metavar="URL",
        help="Restrict --scan extraction to this URL; repeatable",
    )
    extract.add_argument("--headed", action="store_true", help="Run the browser headed")
    extract.add_argument(
        "--session",
        default=None,
        metavar="PATH",
        help="Replay a Playwright storage_state JSON for authenticated extraction",
    )
    extract.add_argument(
        "--reveal",
        type=int,
        default=0,
        metavar="N",
        help="Active discovery: click up to N reveal-triggers (aria-expanded, closed <details>) and merge newly-mounted fields. Default 0 (passive only).",
    )
    _add_project_arg(extract)
    extract.set_defaults(func=_cmd_extract)

    ctas = sub.add_parser(
        "ctas",
        help="Extract clickable CTAs (buttons + link-CTAs) from a page",
    )
    ctas.add_argument(
        "url",
        nargs="?",
        help="Page URL; omit when using --project's base_url",
    )
    ctas.add_argument("--headed", action="store_true", help="Run the browser headed")
    ctas.add_argument(
        "--session",
        default=None,
        metavar="PATH",
        help="Replay a Playwright storage_state JSON for authenticated extraction",
    )
    _add_project_arg(ctas)
    ctas.set_defaults(func=_cmd_ctas)

    suggest_p = sub.add_parser(
        "suggest",
        help="Emit fuzzing suggestions per field (single URL or every page in a scan)",
    )
    suggest_p.add_argument(
        "url",
        nargs="?",
        help="Page URL; omit when using --scan or --project's base_url",
    )
    suggest_p.add_argument(
        "--scan",
        default=None,
        help="Path to a `fuzzmark scan` result JSON; suggest for each page in it",
    )
    suggest_p.add_argument(
        "--include",
        action="append",
        default=None,
        metavar="URL",
        help="Restrict --scan extraction to this URL; repeatable",
    )
    suggest_p.add_argument(
        "--tables",
        default=None,
        metavar="PATH",
        help="Path to a JSON file of user-authored suggestion tables to merge with the built-ins",
    )
    suggest_p.add_argument("--headed", action="store_true", help="Run the browser headed")
    suggest_p.add_argument(
        "--session",
        default=None,
        metavar="PATH",
        help="Replay a Playwright storage_state JSON for authenticated extraction",
    )
    suggest_p.add_argument(
        "--reveal",
        type=int,
        default=0,
        metavar="N",
        help="Active discovery: click up to N reveal-triggers and merge newly-mounted fields before suggesting. Default 0 (passive only).",
    )
    _add_project_arg(suggest_p)
    suggest_p.set_defaults(func=_cmd_suggest)

    capture = sub.add_parser(
        "capture", help="Load a page and write a screenshot plus error-signal JSON"
    )
    capture.add_argument("url")
    capture.add_argument("output", help="Path to write the PNG screenshot to")
    capture.add_argument(
        "--width",
        type=int,
        default=None,
        help=f"Viewport width (px); falls back to --project's first viewport, then {DEFAULT_VIEWPORT[0]}",
    )
    capture.add_argument(
        "--height",
        type=int,
        default=None,
        help=f"Viewport height (px); falls back to --project's first viewport, then {DEFAULT_VIEWPORT[1]}",
    )
    capture.add_argument(
        "--viewport-only",
        action="store_true",
        help="Capture only the visible viewport instead of the full page",
    )
    capture.add_argument("--headed", action="store_true", help="Run the browser headed")
    capture.add_argument(
        "--session",
        default=None,
        metavar="PATH",
        help="Replay a Playwright storage_state JSON for authenticated capture",
    )
    _add_project_arg(capture)
    capture.set_defaults(func=_cmd_capture)

    run_p = sub.add_parser(
        "run", help="Execute a Test JSON flow and write per-step screenshots"
    )
    run_p.add_argument("test", help="Path to a Test JSON file")
    run_p.add_argument("--out", required=True, help="Directory to write screenshots into")
    run_p.add_argument(
        "--width",
        type=int,
        default=None,
        help=f"Viewport width (px); falls back to --project's first viewport, then {DEFAULT_VIEWPORT[0]}",
    )
    run_p.add_argument(
        "--height",
        type=int,
        default=None,
        help=f"Viewport height (px); falls back to --project's first viewport, then {DEFAULT_VIEWPORT[1]}",
    )
    run_p.add_argument("--headed", action="store_true", help="Run the browser headed")
    run_p.add_argument(
        "--session",
        default=None,
        metavar="PATH",
        help="Replay a Playwright storage_state JSON for an authenticated run (Test JSON 'session' wins when set)",
    )
    _add_project_arg(run_p)
    run_p.set_defaults(func=_cmd_run)

    report_p = sub.add_parser(
        "report",
        help="Render a static HTML report from a run-result JSON and optional baselines",
    )
    report_p.add_argument("result", help="Path to a result JSON produced by `fuzzmark run`")
    report_p.add_argument(
        "--out", required=True, help="Directory to write the HTML report into"
    )
    report_p.add_argument(
        "--baselines",
        default=None,
        help="Optional directory of approved baseline PNGs keyed by capture name",
    )
    report_p.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"SSIM threshold for a pass verdict (default {DEFAULT_THRESHOLD})",
    )
    report_p.add_argument(
        "--mask",
        action="append",
        default=None,
        metavar="CAPTURE_NAME:X,Y,W,H[,SOURCE]",
        help="Per-capture region to blank before scoring; repeatable",
    )
    _add_project_arg(report_p)
    report_p.set_defaults(func=_cmd_report)

    approve = sub.add_parser(
        "approve",
        help="Promote selected captures from a run result into approved baselines",
    )
    approve.add_argument("result", help="Path to a result JSON produced by `fuzzmark run`")
    approve.add_argument(
        "--baselines",
        default=None,
        help="Directory to write approved baseline PNGs into; falls back to --project's 'baselines'",
    )
    approve.add_argument(
        "--captures",
        default=None,
        help="Comma-separated capture names to approve; default approves every capture in the run",
    )
    approve.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the approval and print it without writing any files",
    )
    _add_project_arg(approve)
    approve.set_defaults(func=_cmd_approve)

    scan = sub.add_parser(
        "scan",
        help="Crawl a base URL within bounds and emit a site map as JSON",
    )
    scan.add_argument(
        "url",
        nargs="?",
        help="Base URL to crawl; omit when --project supplies base_url",
    )
    scan.add_argument(
        "--max-depth", type=int, default=CrawlBounds.max_depth, help="Max link-hops from the start URL"
    )
    scan.add_argument(
        "--max-pages",
        type=int,
        default=CrawlBounds.max_pages,
        help="Soft cap on pages visited",
    )
    scan.add_argument(
        "--allow-cross-origin",
        action="store_true",
        help="Follow links to other origins (default: same-origin only)",
    )
    scan.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Skip robots.txt (intended for local dev)",
    )
    scan.add_argument(
        "--rate-limit",
        type=float,
        default=0.0,
        help="Seconds to sleep between page loads",
    )
    scan.add_argument("--headed", action="store_true", help="Run the browser headed")
    scan.add_argument(
        "--session",
        default=None,
        metavar="PATH",
        help="Replay a Playwright storage_state JSON for an authenticated crawl",
    )
    _add_project_arg(scan)
    scan.set_defaults(func=_cmd_scan)

    project_p = sub.add_parser(
        "project",
        help="Initialize or inspect a Fuzzmark project JSON file",
    )
    project_sub = project_p.add_subparsers(dest="project_command", required=True)

    project_init = project_sub.add_parser(
        "init", help="Write a starter project JSON file"
    )
    project_init.add_argument("path", help="Destination path for the project JSON")
    project_init.add_argument(
        "--name", required=True, help="Project name (non-empty)"
    )
    project_init.add_argument(
        "--base-url", required=True, help="Base URL the target lives at"
    )
    project_init.add_argument(
        "--viewport",
        action="append",
        default=None,
        metavar="NAME:WIDTHxHEIGHT",
        help="Add a viewport entry (e.g. 'desktop:1280x800'); repeatable",
    )
    project_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination if it already exists",
    )
    project_init.set_defaults(func=_cmd_project_init)

    project_show = project_sub.add_parser(
        "show", help="Load a project JSON file and print it with resolved paths"
    )
    project_show.add_argument("path", help="Path to a project JSON file")
    project_show.set_defaults(func=_cmd_project_show)

    session_p = sub.add_parser(
        "session",
        help="Open a headed browser at a login URL and save the resulting session",
    )
    session_p.add_argument("url", help="Login page URL to open")
    session_p.add_argument(
        "--out",
        required=True,
        help="Path to write the Playwright storage_state JSON to",
    )
    session_p.add_argument(
        "--wait-for-url",
        default=None,
        metavar="REGEX",
        help="Save once the page URL matches REGEX; default saves on first navigation away from the login URL",
    )
    session_p.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Max seconds to wait for the trigger navigation",
    )
    session_p.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (use only when --wait-for-url is automatable; default is headed for interactive login)",
    )
    session_p.set_defaults(func=_cmd_session)

    serve_p = sub.add_parser(
        "serve",
        help="Run the local HTTP API on 127.0.0.1 so the desktop frontend can talk to the engine",
    )
    serve_p.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)"
    )
    serve_p.add_argument(
        "--port", type=int, default=8765, help="Bind port (default 8765)"
    )
    serve_p.add_argument(
        "--log-file",
        default=None,
        help="Engine log file path (default ~/Library/Logs/fuzzmark/engine.log on macOS, "
        "~/.local/state/fuzzmark/engine.log otherwise)",
    )
    serve_p.set_defaults(func=_cmd_serve)

    compare = sub.add_parser(
        "compare",
        help="Compare a candidate screenshot against a baseline; exits 1 on change",
    )
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"SSIM threshold for a pass verdict (default {DEFAULT_THRESHOLD})",
    )
    compare.add_argument(
        "--diff-out",
        default=None,
        help="Optional path to write a heatmap PNG visualizing the diff",
    )
    compare.add_argument(
        "--mask",
        action="append",
        default=None,
        metavar="X,Y,W,H[,SOURCE]",
        help="Region to blank on both images before scoring; repeatable",
    )
    compare.set_defaults(func=_cmd_compare)

    sim_devices_p = sub.add_parser(
        "sim-devices",
        help="List iOS Simulator devices visible to `xcrun simctl`",
    )
    sim_devices_p.add_argument(
        "--all",
        action="store_true",
        help="Include unavailable devices (defaults to available-only)",
    )
    sim_devices_p.set_defaults(func=_cmd_sim_devices)

    sim_capture_p = sub.add_parser(
        "sim-capture",
        help="Install a .app on an iOS Simulator, launch it, and screenshot the first frame",
    )
    sim_capture_p.add_argument("app", help="Path to a built .app bundle (simulator slice)")
    sim_capture_p.add_argument("output", help="Path to write the PNG screenshot to")
    sim_capture_p.add_argument(
        "--device",
        default=None,
        help='Simulator name (e.g. "iPhone 16"); defaults to the latest-runtime device of any name',
    )
    sim_capture_p.add_argument(
        "--runtime",
        default=None,
        metavar="SUBSTR",
        help='Case-insensitive runtime substring (e.g. "iOS-26") to constrain device picking',
    )
    sim_capture_p.add_argument(
        "--bundle-id",
        default=None,
        help="Override the bundle id read from the app's Info.plist",
    )
    sim_capture_p.add_argument(
        "--settle",
        type=float,
        default=1.5,
        help="Seconds to wait after launch before screenshotting (default 1.5)",
    )
    sim_capture_p.add_argument(
        "--terminate-after",
        action="store_true",
        help="Kill the app process after capture (sim is left booted either way)",
    )
    sim_capture_p.add_argument(
        "--no-stabilize-status-bar",
        action="store_true",
        help="Leave the live status bar untouched (default freezes time/battery/signal so consecutive captures are byte-identical)",
    )
    sim_capture_p.set_defaults(func=_cmd_sim_capture)

    sim_run_p = sub.add_parser(
        "sim-run",
        help="Execute a MobileTest JSON against an iOS Simulator and write per-step screenshots",
    )
    sim_run_p.add_argument("test", help="Path to a MobileTest JSON file")
    sim_run_p.add_argument("--out", required=True, help="Directory to write screenshots into")
    sim_run_p.add_argument(
        "--settle",
        type=float,
        default=1.5,
        help="Seconds to wait after a 'launch' step for the first frame (default 1.5)",
    )
    sim_run_p.add_argument(
        "--no-stabilize-status-bar",
        action="store_true",
        help="Leave the live status bar untouched (default freezes time/battery/signal so consecutive captures are byte-identical)",
    )
    sim_run_p.set_defaults(func=_cmd_sim_run)

    sim_check_p = sub.add_parser(
        "sim-check",
        help="Run a MobileTest, render its report, exit non-zero on any non-pass verdict",
    )
    sim_check_p.add_argument("test", help="Path to a MobileTest JSON file")
    sim_check_p.add_argument(
        "--out", required=True, help="Directory to write screenshots into"
    )
    sim_check_p.add_argument(
        "--report-out",
        default=None,
        metavar="DIR",
        help="Directory to write the HTML report into (default <out>/report)",
    )
    sim_check_p.add_argument(
        "--baselines",
        default=None,
        metavar="DIR",
        help="Approved-baselines directory; captures with no baseline fail the gate",
    )
    sim_check_p.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"SSIM threshold (default {DEFAULT_THRESHOLD})",
    )
    sim_check_p.add_argument(
        "--mask",
        action="append",
        default=[],
        metavar="CAPTURE:x,y,w,h[,source]",
        help="Region to blank on both images before scoring; repeatable",
    )
    sim_check_p.add_argument(
        "--settle",
        type=float,
        default=1.5,
        help="Seconds to wait after a 'launch' step for the first frame (default 1.5)",
    )
    sim_check_p.add_argument(
        "--no-stabilize-status-bar",
        action="store_true",
        help="Leave the live status bar untouched (default freezes time/battery/signal so consecutive captures are byte-identical)",
    )
    _add_project_arg(sim_check_p)
    sim_check_p.set_defaults(func=_cmd_sim_check)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
