"""iOS Simulator capture: install, launch, screenshot.

Phase 8 entry slice. Browser-free; the diff/compare pipeline is reused as-is
because both backends emit PNGs.
"""

from .capture import capture_app
from .driver import run_mobile_flow
from .flow import (
    CAPTURE,
    LAUNCH,
    OPENURL,
    STEP_KINDS,
    TERMINATE,
    WAIT,
    MobileCaptureArtifact,
    MobileFlowStep,
    MobileRunResult,
    MobileTest,
    device_viewport_label,
    load_mobile_test,
    parse_mobile_test,
)
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
    "run_mobile_flow",
    "load_mobile_test",
    "parse_mobile_test",
    "MobileTest",
    "MobileFlowStep",
    "MobileRunResult",
    "MobileCaptureArtifact",
    "MobileCaptureResult",
    "device_viewport_label",
    "STEP_KINDS",
    "LAUNCH",
    "TERMINATE",
    "OPENURL",
    "WAIT",
    "CAPTURE",
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
