"""Load user-authored suggestion tables and merge them with the built-ins.

Phase 4 (spec §5.3): the curated `tables.py` set ships as the strong default;
projects can ship their own per-type rows (e.g. company-specific email patterns,
domain-specific SSN/postcode tables) by handing a JSON file to the engine.

File format::

    {
      "tables": {
        "email": {
          "extend": [
            {"category": "format-valid", "value": "ceo@acme.com", "label": "CEO"}
          ]
        },
        "color": {
          "replace": [
            {"category": "format-valid", "value": "#003366", "label": "brand blue"}
          ]
        },
        "postcode": {
          "extend": [
            {"category": "format-valid", "value": "12345", "label": "US ZIP"}
          ]
        }
      }
    }

`extend` appends rows after the built-in table for that type. `replace` drops
the built-in table entirely and uses only the user rows. A type with no
built-in (e.g. ``postcode`` above) takes ``extend`` rows as its full table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .models import CATEGORIES, Suggestion
from .tables import TYPE_TABLES


class CustomTablesError(ValueError):
    """Raised when a user-tables file is malformed."""


def load_custom_tables(path: str | Path) -> dict[str, dict]:
    """Read and validate a user-tables JSON file.

    Returns the per-type spec dict (``{type: {"extend"|"replace": [...]}}``).
    Use `merge_tables` to fold it into a runtime `TYPE_TABLES` map.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CustomTablesError(f"{path}: top level must be a JSON object")
    tables = raw.get("tables", raw)
    if not isinstance(tables, dict):
        raise CustomTablesError(f"{path}: 'tables' must be a JSON object")

    known = set(CATEGORIES)
    out: dict[str, dict] = {}
    for type_key, spec in tables.items():
        if not isinstance(type_key, str) or not type_key:
            raise CustomTablesError(f"{path}: table key must be a non-empty string")
        if not isinstance(spec, dict):
            raise CustomTablesError(f"{path}: '{type_key}' must be a JSON object")

        extras = set(spec) - {"extend", "replace"}
        if extras:
            raise CustomTablesError(
                f"{path}: '{type_key}' has unknown keys {sorted(extras)}; allow extend/replace"
            )
        if not spec:
            raise CustomTablesError(f"{path}: '{type_key}' must define extend or replace")

        cleaned: dict[str, tuple[Suggestion, ...]] = {}
        for mode in ("extend", "replace"):
            if mode not in spec:
                continue
            rows = spec[mode]
            if not isinstance(rows, list):
                raise CustomTablesError(
                    f"{path}: '{type_key}.{mode}' must be a JSON array"
                )
            cleaned[mode] = tuple(
                _parse_row(row, type_key, mode, idx, known)
                for idx, row in enumerate(rows)
            )
        out[type_key] = cleaned
    return out


def _parse_row(row: object, type_key: str, mode: str, idx: int, known: set[str]) -> Suggestion:
    if not isinstance(row, dict):
        raise CustomTablesError(f"'{type_key}.{mode}[{idx}]' must be an object")
    missing = {"category", "value", "label"} - row.keys()
    if missing:
        raise CustomTablesError(
            f"'{type_key}.{mode}[{idx}]' missing required keys {sorted(missing)}"
        )
    category = row["category"]
    if category not in known:
        raise CustomTablesError(
            f"'{type_key}.{mode}[{idx}]' uses unknown category {category!r}; "
            f"allow {sorted(known)}"
        )
    value = row["value"]
    label = row["label"]
    if not isinstance(value, str) or not isinstance(label, str):
        raise CustomTablesError(
            f"'{type_key}.{mode}[{idx}]' value and label must be strings"
        )
    return Suggestion(category, value, label)


def merge_tables(
    custom: Mapping[str, dict],
    base: Mapping[str, tuple[Suggestion, ...]] = TYPE_TABLES,
) -> dict[str, tuple[Suggestion, ...]]:
    """Merge a custom-tables spec onto a baseline `TYPE_TABLES` map."""
    merged: dict[str, tuple[Suggestion, ...]] = dict(base)
    for type_key, spec in custom.items():
        if "replace" in spec:
            merged[type_key] = spec["replace"] + spec.get("extend", ())
        else:
            merged[type_key] = merged.get(type_key, ()) + spec.get("extend", ())
    return merged
