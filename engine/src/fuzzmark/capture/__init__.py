"""Screenshot capture and console / runtime error collection."""

from .result import CaptureResult, ConsoleMessage, FailedRequest
from .runner import capture_page

__all__ = ["capture_page", "CaptureResult", "ConsoleMessage", "FailedRequest"]
