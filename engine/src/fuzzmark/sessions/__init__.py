"""Capture and replay a logged-in browser session for authenticated runs.

The engine never injects into the site under test (spec §4). Auth is handled
by capturing Playwright's `storage_state` once via `capture_session` and
passing the resulting JSON to driver/capture/scanner/extractor on later runs.
"""

from .capture import SessionCaptureResult, capture_session
from .load import SessionError, validate_session

__all__ = [
    "SessionCaptureResult",
    "SessionError",
    "capture_session",
    "validate_session",
]
