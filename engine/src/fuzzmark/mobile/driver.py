"""Run a MobileTest against an iOS Simulator and produce a MobileRunResult."""

from __future__ import annotations

import re
import time
from pathlib import Path

from .flow import (
    CAPTURE,
    LAUNCH,
    MobileCaptureArtifact,
    MobileRunResult,
    MobileTest,
    OPENURL,
    TERMINATE,
    WAIT,
    device_viewport_label,
)
from .simctl import (
    SimctlError,
    _run,
    boot_device,
    install_app,
    launch_app,
    read_bundle_id,
    resolve_device,
    screenshot,
    terminate_app,
)


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def run_mobile_flow(
    test: MobileTest,
    out_dir: str | Path,
    *,
    launch_settle_seconds: float = 1.5,
) -> MobileRunResult:
    """Execute `test` and write per-capture PNGs into `out_dir`.

    Screenshots land at `<out_dir>/<viewport>/<safe-capture-name>.png` where
    `viewport` is `device_viewport_label(device.name, device.runtime)`. This
    mirrors the multi-viewport layout the web driver writes and lines up with
    the baseline store's `<baselines>/<viewport>/<name>.png` convention so the
    same MobileTest run against multiple devices keeps captures + baselines
    cleanly partitioned.

    Args:
        test: A validated `MobileTest` (see `flow.load_mobile_test`).
        out_dir: Directory to write `<viewport>/<safe-capture-name>.png` files
            into. Created if missing.
        launch_settle_seconds: Time to wait after `launch` for the first frame
            to render. Override per-step waits via explicit `wait` steps.

    Returns:
        A populated `MobileRunResult`. Raises `SimctlError` on any underlying
        simctl/plutil failure.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    bundle_id = test.bundle_id
    if test.app:
        app_bundle_id = read_bundle_id(test.app)
        bundle_id = bundle_id or app_bundle_id

    device = resolve_device(
        name=test.device,
        runtime_contains=test.runtime,
        prefer_booted=True,
    )
    boot_device(device.udid, wait_ready=True)

    if test.app:
        install_app(device.udid, test.app)

    viewport = device_viewport_label(device.name, device.runtime)
    viewport_dir = out / viewport
    viewport_dir.mkdir(parents=True, exist_ok=True)

    result = MobileRunResult(
        test_name=test.name,
        device_udid=device.udid,
        device_name=device.name,
        runtime=device.runtime,
        bundle_id=bundle_id,
        viewport=viewport,
    )

    for index, step in enumerate(test.flow):
        if step.kind == LAUNCH:
            if not bundle_id:
                raise SimctlError(
                    f"step {index} (launch): no bundle_id resolved (set 'bundle_id' or 'app')"
                )
            launch_app(
                device.udid,
                bundle_id,
                settle_seconds=launch_settle_seconds,
            )
        elif step.kind == TERMINATE:
            if not bundle_id:
                raise SimctlError(
                    f"step {index} (terminate): no bundle_id resolved"
                )
            terminate_app(device.udid, bundle_id)
        elif step.kind == OPENURL:
            assert step.url is not None  # validated in flow.py
            _run(
                ["xcrun", "simctl", "openurl", device.udid, step.url],
                timeout=30,
            )
        elif step.kind == WAIT:
            assert step.seconds is not None
            time.sleep(step.seconds)
        elif step.kind == CAPTURE:
            assert step.name is not None
            filename = _safe_filename(step.name) + ".png"
            path = screenshot(device.udid, viewport_dir / filename)
            result.captures.append(
                MobileCaptureArtifact(
                    name=step.name,
                    step_index=index,
                    screenshot_path=str(path),
                    viewport=viewport,
                )
            )
        else:  # pragma: no cover  (parser already restricts to STEP_KINDS)
            raise SimctlError(f"step {index}: unsupported kind {step.kind!r}")

    return result


def _safe_filename(name: str) -> str:
    """Map a capture name to a filesystem-safe filename stem."""
    cleaned = _SAFE_NAME.sub("-", name).strip("-")
    return cleaned or "capture"
