"""Data model for a single mobile-simulator capture."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MobileCaptureResult:
    """Output of capturing a single screen from an iOS Simulator device."""

    app_path: str
    bundle_id: str
    screenshot_path: str
    device_udid: str
    device_name: str
    runtime: str

    def to_dict(self) -> dict:
        return asdict(self)
