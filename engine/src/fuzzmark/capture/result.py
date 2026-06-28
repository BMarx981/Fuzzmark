"""Data models for a single page capture."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ConsoleMessage:
    """A console message emitted by the page during capture."""

    level: str
    text: str


@dataclass(frozen=True)
class FailedRequest:
    """A network request that failed outright or returned an HTTP error status."""

    url: str
    method: str
    failure: Optional[str] = None
    status: Optional[int] = None


@dataclass
class CaptureResult:
    """Output of capturing a single page: screenshot path plus collected error signals."""

    url: str
    screenshot_path: str
    viewport_width: int
    viewport_height: int
    full_page: bool
    console_errors: list[ConsoleMessage] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[FailedRequest] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.console_errors or self.page_errors or self.failed_requests)

    def to_dict(self) -> dict:
        return asdict(self)
