"""Generate fuzzing suggestions for a field from rule tables + validation metadata."""

from __future__ import annotations

from ..extractor import Field
from .models import (
    BOUNDARY,
    EMPTY,
    FORMAT_INVALID,
    FORMAT_VALID,
    Suggestion,
)
from .tables import TEXTAREA_TABLE, TYPE_TABLES


def _empty_required(field: Field) -> list[Suggestion]:
    if not field.validation.required:
        return []
    return [
        Suggestion(EMPTY, "", "blank"),
        Suggestion(EMPTY, "   ", "whitespace only"),
    ]


def _length_boundaries(field: Field) -> list[Suggestion]:
    """Boundary suggestions driven by minlength/maxlength."""
    v = field.validation
    out: list[Suggestion] = []
    if v.minlength is not None and v.minlength > 0:
        out.append(Suggestion(BOUNDARY, "a" * (v.minlength - 1), f"one under minlength ({v.minlength - 1})"))
        out.append(Suggestion(BOUNDARY, "a" * v.minlength, f"exactly minlength ({v.minlength})"))
    if v.maxlength is not None and v.maxlength > 0:
        out.append(Suggestion(BOUNDARY, "a" * v.maxlength, f"exactly maxlength ({v.maxlength})"))
        out.append(Suggestion(BOUNDARY, "a" * (v.maxlength + 1), f"one over maxlength ({v.maxlength + 1})"))
    return out


def _numeric_boundaries(field: Field) -> list[Suggestion]:
    """Boundary suggestions driven by min/max on a numeric field."""
    v = field.validation
    out: list[Suggestion] = []

    def _as_number(raw: str | None) -> int | float | None:
        if raw is None:
            return None
        try:
            if "." in raw or "e" in raw.lower():
                return float(raw)
            return int(raw)
        except ValueError:
            return None

    lo = _as_number(v.min)
    hi = _as_number(v.max)
    if lo is not None:
        out.append(Suggestion(BOUNDARY, str(lo - 1), f"one under min ({lo - 1})"))
        out.append(Suggestion(BOUNDARY, str(lo), f"exactly min ({lo})"))
    if hi is not None:
        out.append(Suggestion(BOUNDARY, str(hi), f"exactly max ({hi})"))
        out.append(Suggestion(BOUNDARY, str(hi + 1), f"one over max ({hi + 1})"))
    return out


def _select_suggestions(field: Field) -> list[Suggestion]:
    out: list[Suggestion] = []
    for opt in field.options:
        if opt.value == "":
            out.append(Suggestion(EMPTY, "", f"placeholder option ({opt.label!r})"))
        else:
            out.append(Suggestion(FORMAT_VALID, opt.value, f"option {opt.label!r}"))
    out.append(Suggestion(FORMAT_INVALID, "__not_a_real_option__", "value not in options"))
    return out


def suggest(field: Field) -> list[Suggestion]:
    """Return ordered, deduplicated suggestions for a single field.

    The function is pure: same field in, same suggestions out, no I/O.
    """
    suggestions: list[Suggestion] = []
    suggestions.extend(_empty_required(field))

    if field.kind == "select":
        suggestions.extend(_select_suggestions(field))
    elif field.kind == "textarea":
        suggestions.extend(TEXTAREA_TABLE)
        suggestions.extend(_length_boundaries(field))
    else:
        table = TYPE_TABLES.get(field.type or "text", TYPE_TABLES["text"])
        suggestions.extend(table)
        if field.type == "number":
            suggestions.extend(_numeric_boundaries(field))
        else:
            suggestions.extend(_length_boundaries(field))

    seen: set[tuple[str, str]] = set()
    deduped: list[Suggestion] = []
    for s in suggestions:
        key = (s.category, s.value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s.with_field(field.selector))
    return deduped


def suggest_all(fields: list[Field]) -> dict[str, list[Suggestion]]:
    """Generate suggestions for every field, keyed by selector."""
    return {f.selector: suggest(f) for f in fields}
