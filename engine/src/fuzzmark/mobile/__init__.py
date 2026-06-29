"""iOS Simulator capture: install, launch, screenshot.

Phase 8 entry slice. Browser-free; the diff/compare pipeline is reused as-is
because both backends emit PNGs.
"""

from .capture import capture_app
from .result import MobileCaptureResult
from .simctl import (
    SimctlError,
    Device,
    boot_device,
    install_app,
    launch_app,
    list_devices,
    read_bundle_id,
    resolve_device,
    screenshot,
    shutdown_device,
    simctl_available,
    terminate_app,
)

__all__ = [
    "capture_app",
    "MobileCaptureResult",
    "SimctlError",
    "Device",
    "boot_device",
    "install_app",
    "launch_app",
    "list_devices",
    "read_bundle_id",
    "resolve_device",
    "screenshot",
    "shutdown_device",
    "simctl_available",
    "terminate_app",
]
