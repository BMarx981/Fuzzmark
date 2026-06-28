"""Command-line interface for the QA engine."""

from __future__ import annotations

import argparse
import json
import sys

from .extractor import extract_fields
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

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
