"""Command-line interface for the QA engine."""

from __future__ import annotations

import argparse
import json
import sys

from .baselines import apply_approval, plan_approval
from .capture import capture_page
from .compare import DEFAULT_THRESHOLD, MaskRegion, compare_images, parse_mask_spec
from .driver import load_test, run_flow
from .extractor import extract_fields, extract_site
from .report import render_report
from .scanner import CrawlBounds, crawl
from .suggestions import suggest, suggest_site


def _cmd_extract(args: argparse.Namespace) -> None:
    if args.scan:
        site_map = json.loads(open(args.scan, encoding="utf-8").read())
        extractor = lambda url: extract_fields(url, headless=not args.headed)
        payload = extract_site(site_map, extractor=extractor, include=args.include or None)
    else:
        if not args.url:
            raise SystemExit("extract: pass a URL or --scan <site-map.json>")
        fields = extract_fields(args.url, headless=not args.headed)
        payload = {
            "url": args.url,
            "field_count": len(fields),
            "fields": [f.to_dict() for f in fields],
        }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_suggest(args: argparse.Namespace) -> None:
    if args.scan:
        site_map = json.loads(open(args.scan, encoding="utf-8").read())
        extractor = lambda url: extract_fields(url, headless=not args.headed)
        site = extract_site(site_map, extractor=extractor, include=args.include or None)
        payload = suggest_site(site)
    else:
        if not args.url:
            raise SystemExit("suggest: pass a URL or --scan <site-map.json>")
        fields = extract_fields(args.url, headless=not args.headed)
        items = []
        for field in fields:
            suggestions = suggest(field)
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
            "url": args.url,
            "field_count": len(fields),
            "fields": items,
        }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_capture(args: argparse.Namespace) -> None:
    result = capture_page(
        args.url,
        args.output,
        viewport=(args.width, args.height),
        full_page=not args.viewport_only,
        headless=not args.headed,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_run(args: argparse.Namespace) -> None:
    test = load_test(args.test)
    result = run_flow(
        test,
        args.out,
        viewport=(args.width, args.height),
        headless=not args.headed,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_report(args: argparse.Namespace) -> None:
    data = json.loads(open(args.result, encoding="utf-8").read())
    masks = _parse_named_masks(args.mask or [])
    report = render_report(
        data,
        args.out,
        baselines_dir=args.baselines,
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
    data = json.loads(open(args.result, encoding="utf-8").read())
    captures = _split_csv(args.captures)
    plan = plan_approval(data, args.baselines, capture_names=captures)
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
    bounds = CrawlBounds(
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        same_origin=not args.allow_cross_origin,
        respect_robots=not args.ignore_robots,
        rate_limit_seconds=args.rate_limit,
    )
    site = crawl(args.url, bounds, headless=not args.headed)
    json.dump(site.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fuzzmark", description="Scan-first QA engine")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser(
        "extract",
        help="Extract form fields from a page (or every page in a scan)",
    )
    extract.add_argument("url", nargs="?", help="Page URL; omit when using --scan")
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
    extract.set_defaults(func=_cmd_extract)

    suggest_p = sub.add_parser(
        "suggest",
        help="Emit fuzzing suggestions per field (single URL or every page in a scan)",
    )
    suggest_p.add_argument("url", nargs="?", help="Page URL; omit when using --scan")
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
    suggest_p.add_argument("--headed", action="store_true", help="Run the browser headed")
    suggest_p.set_defaults(func=_cmd_suggest)

    capture = sub.add_parser(
        "capture", help="Load a page and write a screenshot plus error-signal JSON"
    )
    capture.add_argument("url")
    capture.add_argument("output", help="Path to write the PNG screenshot to")
    capture.add_argument("--width", type=int, default=1280, help="Viewport width (px)")
    capture.add_argument("--height", type=int, default=800, help="Viewport height (px)")
    capture.add_argument(
        "--viewport-only",
        action="store_true",
        help="Capture only the visible viewport instead of the full page",
    )
    capture.add_argument("--headed", action="store_true", help="Run the browser headed")
    capture.set_defaults(func=_cmd_capture)

    run_p = sub.add_parser(
        "run", help="Execute a Test JSON flow and write per-step screenshots"
    )
    run_p.add_argument("test", help="Path to a Test JSON file")
    run_p.add_argument("--out", required=True, help="Directory to write screenshots into")
    run_p.add_argument("--width", type=int, default=1280, help="Viewport width (px)")
    run_p.add_argument("--height", type=int, default=800, help="Viewport height (px)")
    run_p.add_argument("--headed", action="store_true", help="Run the browser headed")
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
    report_p.set_defaults(func=_cmd_report)

    approve = sub.add_parser(
        "approve",
        help="Promote selected captures from a run result into approved baselines",
    )
    approve.add_argument("result", help="Path to a result JSON produced by `fuzzmark run`")
    approve.add_argument(
        "--baselines",
        required=True,
        help="Directory to write approved baseline PNGs into (created if missing)",
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
    approve.set_defaults(func=_cmd_approve)

    scan = sub.add_parser(
        "scan",
        help="Crawl a base URL within bounds and emit a site map as JSON",
    )
    scan.add_argument("url")
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
    scan.set_defaults(func=_cmd_scan)

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

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
