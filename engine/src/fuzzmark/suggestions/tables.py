"""Per-type fuzzing suggestion tables.

Pure data: every entry is a fixed (category, value, label) row keyed off a
field's `type`. Boundary suggestions that depend on a field's own validation
attributes are computed in `engine.py`, not stored here.
"""

from __future__ import annotations

from .models import (
    FORMAT_INVALID,
    FORMAT_VALID,
    I18N,
    SECURITY,
    TYPE_SPECIFIC,
    Suggestion,
)


_GENERIC_TEXT: tuple[Suggestion, ...] = (
    Suggestion(SECURITY, "<script>alert(1)</script>", "script tag"),
    Suggestion(SECURITY, "' OR '1'='1 --", "SQL-style payload"),
    Suggestion(SECURITY, "javascript:alert(1)", "javascript: URL"),
    Suggestion(I18N, "naïve café", "accented Latin"),
    Suggestion(I18N, "日本語テスト", "CJK characters"),
    Suggestion(I18N, "مرحبا بالعالم", "RTL Arabic"),
    Suggestion(I18N, "🚀🎉🔥", "emoji"),
)


_TEXT: tuple[Suggestion, ...] = _GENERIC_TEXT + (
    Suggestion(FORMAT_VALID, "Quick brown fox", "ordinary text"),
)


_EMAIL: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "user@example.com", "ordinary email"),
    Suggestion(FORMAT_INVALID, "not-an-email", "missing @"),
    Suggestion(FORMAT_INVALID, "user@", "missing domain"),
    Suggestion(FORMAT_INVALID, "user@@example.com", "double @"),
    Suggestion(FORMAT_INVALID, "user @example.com", "internal whitespace"),
    Suggestion(TYPE_SPECIFIC, "user+tag@example.com", "plus-addressed"),
    Suggestion(TYPE_SPECIFIC, "user@例え.テスト", "internationalized domain"),
    Suggestion(SECURITY, '"<script>"@example.com', "script in local part"),
    Suggestion(I18N, "日本語@example.com", "non-ASCII local part"),
)


_NUMBER: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "42", "ordinary integer"),
    Suggestion(FORMAT_INVALID, "abc", "letters in numeric field"),
    Suggestion(FORMAT_INVALID, "1.5e3", "scientific notation"),
    Suggestion(FORMAT_INVALID, "--1", "double sign"),
    Suggestion(TYPE_SPECIFIC, "007", "leading zeros"),
    Suggestion(TYPE_SPECIFIC, "-0", "negative zero"),
)


_TEL: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "+15555550123", "E.164"),
    Suggestion(FORMAT_VALID, "(555) 555-0123", "US formatted"),
    Suggestion(FORMAT_INVALID, "not-a-phone", "letters"),
    Suggestion(FORMAT_INVALID, "555 555 0123 ext 99", "trailing extension text"),
    Suggestion(TYPE_SPECIFIC, "+44 20 7946 0958", "UK international"),
    Suggestion(TYPE_SPECIFIC, "+81-3-1234-5678", "JP international"),
) + tuple(s for s in _GENERIC_TEXT if s.category == SECURITY)


TYPE_TABLES: dict[str, tuple[Suggestion, ...]] = {
    "text": _TEXT,
    "search": _TEXT,
    "url": _TEXT,
    "email": _EMAIL,
    "number": _NUMBER,
    "tel": _TEL,
}


TEXTAREA_TABLE: tuple[Suggestion, ...] = _TEXT + (
    Suggestion(I18N, "line one\nline two\nline three", "embedded newlines"),
)
