"""Mutate a saved project file in place.

These helpers re-read the raw JSON, mutate one field, validate the result,
and write it back, preserving any keys the loader does not currently model
so hand-edited extras survive a round trip through the engine.
"""

from __future__ import annotations

import json
from pathlib import Path

from .load import ProjectError, parse_project
from .models import Project


def set_scan_path(project_file: str | Path, scan: str | None) -> Project:
    """Set (or clear) the project's `scan` field and rewrite the file.

    `scan` is stored as written — relative paths resolve against the project
    file's directory at read time, the same as every other path field.
    Returns the reparsed `Project` for the caller's convenience.
    """
    path = Path(project_file)
    raw = _read_raw(path)
    if scan is None:
        raw.pop("scan", None)
    else:
        scan = scan.strip()
        if not scan:
            raise ProjectError("'scan' must be a non-empty string")
        raw["scan"] = scan
    project = parse_project(raw, source_dir=path.parent)
    path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return project


def add_test_path(project_file: str | Path, test_path: str) -> Project:
    """Append `test_path` to the project's `tests` list and rewrite the file.

    `test_path` is stored as written, the same as every other path field.
    Duplicates are rejected by `parse_project`; the call is therefore
    idempotent only if the caller has already deduplicated.
    """
    path = Path(project_file)
    raw = _read_raw(path)
    test_path = test_path.strip()
    if not test_path:
        raise ProjectError("test path must be a non-empty string")
    existing = list(raw.get("tests") or [])
    if test_path not in existing:
        existing.append(test_path)
    raw["tests"] = existing
    project = parse_project(raw, source_dir=path.parent)
    path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return project


def _read_raw(path: Path) -> dict:
    if not path.exists():
        raise ProjectError(f"project file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectError(f"project file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProjectError("project must be a JSON object")
    return raw
