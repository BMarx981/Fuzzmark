"""End-to-end iOS-simulator capture: resolve device → boot → install → launch → screenshot."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .result import MobileCaptureResult
from .simctl import (
    boot_device,
    install_app,
    launch_app,
    read_bundle_id,
    resolve_device,
    screenshot,
    terminate_app,
)


def capture_app(
    app_path: str | Path,
    screenshot_path: str | Path,
    *,
    device_name: Optional[str] = None,
    runtime_contains: Optional[str] = None,
    bundle_id: Optional[str] = None,
    launch_args: Optional[list[str]] = None,
    settle_seconds: float = 1.5,
    terminate_after: bool = False,
) -> MobileCaptureResult:
    """Install `app_path` on a resolved iOS Simulator and capture its first frame.

    Args:
        app_path: Path to a built `.app` bundle (simulator slice).
        screenshot_path: PNG output path. Parent directory is created.
        device_name: Simulator name to target (e.g. "iPhone 16"); when None,
            the latest-runtime device of any name is used. Prefers a device
            that is already booted.
        runtime_contains: Case-insensitive substring of the runtime id to
            constrain the device pick (e.g. "iOS-26").
        bundle_id: Override the bundle id read from the app's Info.plist. Use
            when launching an app variant whose plist identifier differs from
            the bundle id you want to launch.
        launch_args: Extra args passed to the app after `simctl launch`.
        settle_seconds: Time to wait after launch before screenshotting, so the
            first frame has rendered.
        terminate_after: If True, kill the app process after capture. The
            device is left booted — subsequent captures are fast that way.

    Returns:
        A populated `MobileCaptureResult`. Raises `SimctlError` on any
        underlying simctl/plutil failure.
    """
    app = Path(app_path)
    resolved_bundle_id = bundle_id or read_bundle_id(app)

    device = resolve_device(
        name=device_name,
        runtime_contains=runtime_contains,
        prefer_booted=True,
    )
    boot_device(device.udid, wait_ready=True)

    install_app(device.udid, app)
    launch_app(
        device.udid,
        resolved_bundle_id,
        args=launch_args,
        settle_seconds=settle_seconds,
    )
    out_path = screenshot(device.udid, screenshot_path)

    if terminate_after:
        terminate_app(device.udid, resolved_bundle_id)

    return MobileCaptureResult(
        app_path=str(app),
        bundle_id=resolved_bundle_id,
        screenshot_path=str(out_path),
        device_udid=device.udid,
        device_name=device.name,
        runtime=device.runtime,
    )
