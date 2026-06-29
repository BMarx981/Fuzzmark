"""End-to-end sim capture tests. Skipped unless `pytest --run-sim` on macOS with Xcode."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.simulator

if sys.platform != "darwin":
    pytest.skip("iOS Simulator is macOS-only", allow_module_level=True)

from fuzzmark.mobile import (  # noqa: E402  (guarded import is intentional)
    capture_app,
    list_devices,
    resolve_device,
    screenshot,
    simctl_available,
)
from fuzzmark.mobile.simctl import boot_device, SimctlError  # noqa: E402


@pytest.fixture(scope="module")
def _simctl_present() -> None:
    if not simctl_available():
        pytest.skip("`xcrun simctl` not available on this host")


def test_list_devices_returns_at_least_one(_simctl_present: None) -> None:
    devices = list_devices(available_only=True)
    assert devices, "no available simulator devices found; install one in Xcode"


def test_screenshot_on_booted_device_writes_png(
    _simctl_present: None, tmp_path: Path
) -> None:
    device = resolve_device(name=None)
    boot_device(device.udid, wait_ready=True)
    out = tmp_path / "frame.png"
    screenshot(device.udid, out)
    assert out.exists() and out.stat().st_size > 0
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_capture_app_missing_bundle_raises(
    _simctl_present: None, tmp_path: Path
) -> None:
    with pytest.raises(SimctlError, match="not found"):
        capture_app(
            tmp_path / "nope.app",
            tmp_path / "out.png",
            device_name=None,
        )
