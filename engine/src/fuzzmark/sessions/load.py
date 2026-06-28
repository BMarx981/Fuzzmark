"""Load and structurally validate a Playwright `storage_state` JSON file.

The on-disk shape matches what `BrowserContext.storage_state(path=...)` emits:
`{"cookies": [...], "origins": [...]}`. We validate only the top-level shape;
Playwright itself owns the inner field semantics.
"""

from __future__ import annotations

import json
from pathlib import Path


class SessionError(ValueError):
    """Raised when a session file is missing, unreadable, or malformed."""


def validate_session(path: str | Path) -> dict:
    """Read `path` and return the decoded storage-state dict.

    Raises `SessionError` if the file does not exist, is not valid JSON, or
    does not look like a Playwright storage_state payload.
    """
    p = Path(path)
    if not p.exists():
        raise SessionError(f"session file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionError(f"session file is not valid JSON: {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SessionError(f"session file must be a JSON object: {p}")
    cookies = raw.get("cookies")
    origins = raw.get("origins")
    if not isinstance(cookies, list) or not isinstance(origins, list):
        raise SessionError(
            f"session file must have 'cookies' and 'origins' lists: {p}"
        )
    return raw
