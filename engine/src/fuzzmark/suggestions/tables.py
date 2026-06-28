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


_URL: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "https://example.com", "ordinary https"),
    Suggestion(FORMAT_VALID, "http://example.com/path?q=1", "with path and query"),
    Suggestion(FORMAT_INVALID, "example.com", "missing scheme"),
    Suggestion(FORMAT_INVALID, "https://", "scheme only"),
    Suggestion(FORMAT_INVALID, "https://exa mple.com", "internal whitespace"),
    Suggestion(TYPE_SPECIFIC, "https://例え.テスト/パス", "internationalized host"),
    Suggestion(TYPE_SPECIFIC, "https://user:pass@example.com", "userinfo in authority"),
    Suggestion(SECURITY, "javascript:alert(1)", "javascript: URL"),
    Suggestion(SECURITY, "data:text/html,<script>alert(1)</script>", "data: URL with script"),
    Suggestion(SECURITY, "file:///etc/passwd", "file: URL"),
)


_PASSWORD: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "Hunter2!Hunter2", "ordinary strong password"),
    Suggestion(FORMAT_INVALID, "password", "common weak password"),
    Suggestion(FORMAT_INVALID, "12345678", "all-digits weak"),
    Suggestion(TYPE_SPECIFIC, " leading space", "leading whitespace"),
    Suggestion(TYPE_SPECIFIC, "trailing space ", "trailing whitespace"),
    Suggestion(TYPE_SPECIFIC, "a" * 200, "very long password"),
    Suggestion(SECURITY, "' OR '1'='1 --", "SQL-style payload"),
    Suggestion(SECURITY, "<script>alert(1)</script>", "script tag"),
    Suggestion(I18N, "пароль🔑", "non-ASCII password"),
)


_DATE: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "2025-06-15", "ordinary date"),
    Suggestion(FORMAT_INVALID, "2025-02-30", "impossible day"),
    Suggestion(FORMAT_INVALID, "2025-13-01", "month 13"),
    Suggestion(FORMAT_INVALID, "not-a-date", "letters"),
    Suggestion(FORMAT_INVALID, "06/15/2025", "US slash format"),
    Suggestion(TYPE_SPECIFIC, "2024-02-29", "leap day"),
    Suggestion(TYPE_SPECIFIC, "0001-01-01", "year 1"),
    Suggestion(TYPE_SPECIFIC, "9999-12-31", "far future"),
)


_TIME: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "09:30", "ordinary time"),
    Suggestion(FORMAT_INVALID, "25:00", "hour over 23"),
    Suggestion(FORMAT_INVALID, "12:60", "minute 60"),
    Suggestion(FORMAT_INVALID, "9-30", "wrong separator"),
    Suggestion(TYPE_SPECIFIC, "00:00", "midnight"),
    Suggestion(TYPE_SPECIFIC, "23:59:59", "with seconds"),
    Suggestion(TYPE_SPECIFIC, "12:00:00.500", "with milliseconds"),
)


_DATETIME_LOCAL: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "2025-06-15T09:30", "ordinary datetime"),
    Suggestion(FORMAT_INVALID, "2025-06-15 09:30", "space instead of T"),
    Suggestion(FORMAT_INVALID, "2025-02-30T09:30", "impossible day"),
    Suggestion(FORMAT_INVALID, "2025-06-15T25:00", "hour over 23"),
    Suggestion(TYPE_SPECIFIC, "2025-06-15T09:30:00", "with seconds"),
    Suggestion(TYPE_SPECIFIC, "2024-02-29T00:00", "leap day midnight"),
)


_MONTH: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "2025-06", "ordinary month"),
    Suggestion(FORMAT_INVALID, "2025-13", "month 13"),
    Suggestion(FORMAT_INVALID, "2025-00", "month 0"),
    Suggestion(FORMAT_INVALID, "2025/06", "wrong separator"),
    Suggestion(TYPE_SPECIFIC, "0001-01", "year 1"),
    Suggestion(TYPE_SPECIFIC, "9999-12", "far future"),
)


_WEEK: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "2025-W24", "ordinary week"),
    Suggestion(FORMAT_INVALID, "2025-W54", "week 54"),
    Suggestion(FORMAT_INVALID, "2025-W00", "week 0"),
    Suggestion(FORMAT_INVALID, "2025-24", "missing W marker"),
    Suggestion(TYPE_SPECIFIC, "2020-W53", "53-week year"),
)


_COLOR: tuple[Suggestion, ...] = (
    Suggestion(FORMAT_VALID, "#ff0000", "red"),
    Suggestion(FORMAT_VALID, "#000000", "black"),
    Suggestion(FORMAT_INVALID, "red", "color name"),
    Suggestion(FORMAT_INVALID, "rgb(255,0,0)", "rgb() notation"),
    Suggestion(FORMAT_INVALID, "#f00", "3-digit hex"),
    Suggestion(FORMAT_INVALID, "not-a-color", "garbage"),
    Suggestion(TYPE_SPECIFIC, "#FFFFFF", "uppercase hex"),
)


TYPE_TABLES: dict[str, tuple[Suggestion, ...]] = {
    "text": _TEXT,
    "search": _TEXT,
    "url": _URL,
    "email": _EMAIL,
    "password": _PASSWORD,
    "number": _NUMBER,
    "range": _NUMBER,
    "tel": _TEL,
    "date": _DATE,
    "time": _TIME,
    "datetime-local": _DATETIME_LOCAL,
    "month": _MONTH,
    "week": _WEEK,
    "color": _COLOR,
}


TEXTAREA_TABLE: tuple[Suggestion, ...] = _TEXT + (
    Suggestion(I18N, "line one\nline two\nline three", "embedded newlines"),
)
