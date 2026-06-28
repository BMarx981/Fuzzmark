"""Decorate a multi-page extract payload with per-field suggestions.

Pure: takes the dict `extractor.extract_site` produces and returns the same
shape with each field augmented by `suggestion_count` and `suggestions`. No
browser; the suggestion engine itself is rule-based and table-driven.
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..extractor import Field, Option, Validation
from .engine import suggest
from .models import Suggestion


def suggest_site(
    site_extract: dict,
    tables: Optional[Mapping[str, tuple[Suggestion, ...]]] = None,
) -> dict:
    """Return a copy of `site_extract` with suggestions attached to every field."""
    out_pages: list[dict] = []
    for page in site_extract.get("pages", []):
        out_fields = []
        for raw in page.get("fields", []):
            field = _field_from_dict(raw)
            sugs = suggest(field, tables=tables)
            out_fields.append(
                {
                    **raw,
                    "suggestion_count": len(sugs),
                    "suggestions": [s.to_dict() for s in sugs],
                }
            )
        out_pages.append({**page, "fields": out_fields})
    return {**site_extract, "pages": out_pages}


def _field_from_dict(raw: dict) -> Field:
    return Field(
        selector=raw["selector"],
        kind=raw["kind"],
        type=raw.get("type"),
        name=raw.get("name"),
        id=raw.get("id"),
        label=raw.get("label"),
        validation=Validation(**raw.get("validation", {})),
        options=[Option(**o) for o in raw.get("options", [])],
    )
