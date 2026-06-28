"""Command-line interface for the QA engine."""

from __future__ import annotations

import argparse
import json
import sys

from .capture import capture_page
from .compare import DEFAULT_THRESHOLD, compare_images
from .driver import load_test, run_flow
from .extractor import extract_fields
from .report import render_report
from .suggestions import suggest


def _cmd_extract(args: argparse.Namespace) -> None:
    fields = extract_fields(args.url, headless=not args.headed)
    payload = {
        "url": args.url,
        "field_count": len(fields),
        "fields": [f.to_dict() for f in fields],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _cmd_suggest(args: argparse.Namespace) -> None:
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
    report = render_report(
        data,
        args.out,
        baselines_dir=args.baselines,
        threshold=args.threshold,
    )
    json.dump(report.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_compare(args: argparse.Namespace) -> None:
    result = compare_images(
        args.baseline,
        args.candidate,
        threshold=args.threshold,
        diff_path=args.diff_out,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(0 if result.verdict == "pass" else 1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fuzzmark", description="Scan-first QA engine")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Extract form fields from a page")
    extract.add_argument("url")
    extract.add_argument("--headed", action="store_true", help="Run the browser headed")
    extract.set_defaults(func=_cmd_extract)

    suggest_p = sub.add_parser(
        "suggest", help="Extract fields and emit fuzzing suggestions per field"
    )
    suggest_p.add_argument("url")
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
    report_p.set_defaults(func=_cmd_report)

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
    compare.set_defaults(func=_cmd_compare)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
