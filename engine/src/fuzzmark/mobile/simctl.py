"""Thin, testable wrappers over `xcrun simctl` and `plutil`.

Each call shells out at invocation time so the module imports cleanly on
non-macOS hosts; failures surface as `SimctlError` only when a function is
actually called.
"""

from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class SimctlError(RuntimeError):
    """Raised when an `xcrun simctl` (or `plutil`) call fails."""


@dataclass(frozen=True)
class Device:
    """A simulator device entry returned by `simctl list`."""

    udid: str
    name: str
    runtime: str
    state: str

    @property
    def is_booted(self) -> bool:
        return self.state.lower() == "booted"


def simctl_available() -> bool:
    """True iff `xcrun` is on PATH and `xcrun simctl help` runs."""
    if shutil.which("xcrun") is None:
        return False
    try:
        subprocess.run(
            ["xcrun", "simctl", "help"],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return True


def _run(argv: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a subprocess and raise `SimctlError` on non-zero exit or timeout."""
    try:
        result = subprocess.run(
            argv, check=False, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as exc:
        raise SimctlError(f"command not found: {argv[0]!r}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SimctlError(f"timed out after {timeout}s: {' '.join(argv)}") from exc
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise SimctlError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n{stderr}"
        )
    return result


def list_devices(*, available_only: bool = True) -> list[Device]:
    """Return all simulator devices grouped under their runtime."""
    argv = ["xcrun", "simctl", "list", "--json", "devices"]
    if available_only:
        argv.append("available")
    result = _run(argv, timeout=15)
    data = json.loads(result.stdout)
    out: list[Device] = []
    for runtime_id, entries in (data.get("devices") or {}).items():
        for entry in entries or []:
            udid = entry.get("udid")
            name = entry.get("name")
            state = entry.get("state", "Unknown")
            if not udid or not name:
                continue
            out.append(
                Device(udid=udid, name=name, runtime=runtime_id, state=state)
            )
    return out


def _runtime_sort_key(runtime_id: str) -> tuple[int, int, int]:
    """Order runtimes so newer iOS versions sort last.

    `com.apple.CoreSimulator.SimRuntime.iOS-18-4` -> (18, 4, 0). Unknown
    formats sort first.
    """
    tail = runtime_id.rsplit(".", 1)[-1]  # e.g. "iOS-18-4"
    if "-" not in tail:
        return (0, 0, 0)
    parts = tail.split("-")[1:]
    nums: list[int] = []
    for part in parts:
        try:
            nums.append(int(part))
        except ValueError:
            return (0, 0, 0)
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def resolve_device(
    name: str | None = None,
    *,
    runtime_contains: str | None = None,
    prefer_booted: bool = True,
) -> Device:
    """Pick a simulator device by name (and optional runtime substring).

    Selection rules, in order:
      1. If `prefer_booted` and a booted device matches, return it.
      2. Otherwise, the latest-runtime device that matches.

    `name=None` matches any device. `runtime_contains` is a case-insensitive
    substring match against the runtime id (e.g. "iOS-26" or "26-1").
    """
    candidates = list_devices(available_only=True)
    if name:
        wanted = name.strip().lower()
        candidates = [d for d in candidates if d.name.lower() == wanted]
    if runtime_contains:
        needle = runtime_contains.lower()
        candidates = [d for d in candidates if needle in d.runtime.lower()]
    if not candidates:
        raise SimctlError(
            f"no simulator matches name={name!r} runtime~={runtime_contains!r}"
        )
    if prefer_booted:
        booted = [d for d in candidates if d.is_booted]
        if booted:
            booted.sort(key=lambda d: _runtime_sort_key(d.runtime), reverse=True)
            return booted[0]
    candidates.sort(key=lambda d: _runtime_sort_key(d.runtime), reverse=True)
    return candidates[0]


def boot_device(udid: str, *, wait_ready: bool = True, timeout: int = 90) -> None:
    """Boot a device by UDID. No-op if already booted.

    When `wait_ready` is True, polls until `simctl bootstatus` reports the
    device finished launching SpringBoard. This is what prevents the first
    screenshot from being a black frame.
    """
    devices = {d.udid: d for d in list_devices(available_only=False)}
    current = devices.get(udid)
    if current is None:
        raise SimctlError(f"unknown device udid: {udid}")
    if not current.is_booted:
        _run(["xcrun", "simctl", "boot", udid], timeout=timeout)
    if wait_ready:
        _run(["xcrun", "simctl", "bootstatus", udid], timeout=timeout)


def shutdown_device(udid: str) -> None:
    """Shut a device down. No-op if already shut down."""
    devices = {d.udid: d for d in list_devices(available_only=False)}
    current = devices.get(udid)
    if current is None or not current.is_booted:
        return
    _run(["xcrun", "simctl", "shutdown", udid], timeout=60)


def install_app(udid: str, app_path: str | Path) -> None:
    """Install a built `.app` bundle on the given device."""
    path = Path(app_path)
    if not path.exists():
        raise SimctlError(f"app bundle not found: {path}")
    if path.suffix.lower() != ".app":
        raise SimctlError(f"expected a .app bundle, got: {path}")
    _run(["xcrun", "simctl", "install", udid, str(path)], timeout=120)


def launch_app(
    udid: str,
    bundle_id: str,
    *,
    args: Optional[list[str]] = None,
    settle_seconds: float = 1.5,
) -> int:
    """Launch an installed app by bundle id and return its pid.

    Waits `settle_seconds` after launch so the first frame has rendered before
    the caller takes a screenshot.
    """
    argv = ["xcrun", "simctl", "launch", udid, bundle_id]
    if args:
        argv.extend(args)
    result = _run(argv, timeout=30)
    # simctl prints "<bundle_id>: <pid>" on success.
    stdout = (result.stdout or "").strip()
    pid = 0
    if ":" in stdout:
        try:
            pid = int(stdout.rsplit(":", 1)[1].strip())
        except ValueError:
            pid = 0
    if settle_seconds > 0:
        time.sleep(settle_seconds)
    return pid


def terminate_app(udid: str, bundle_id: str) -> None:
    """Terminate a running app by bundle id. Errors are swallowed."""
    try:
        _run(
            ["xcrun", "simctl", "terminate", udid, bundle_id],
            timeout=15,
        )
    except SimctlError:
        pass


DEFAULT_STATUS_BAR_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("--time", "9:41"),
    ("--dataNetwork", "wifi"),
    ("--wifiMode", "active"),
    ("--wifiBars", "3"),
    ("--cellularMode", "active"),
    ("--cellularBars", "4"),
    ("--operatorName", "Fuzzmark"),
    ("--batteryState", "charged"),
    ("--batteryLevel", "100"),
)


def override_status_bar(
    udid: str,
    *,
    overrides: tuple[tuple[str, str], ...] = DEFAULT_STATUS_BAR_OVERRIDES,
) -> None:
    """Freeze the iOS Simulator status bar so consecutive captures are byte-identical.

    The default override pins the marketing time (9:41), full battery + signal,
    and a stable operator name. Without it, the live clock and signal
    indicators tick between captures and every baseline comparison reports a
    spurious diff.

    `overrides` is a sequence of `(flag, value)` pairs forwarded to
    `simctl status_bar <udid> override`. Pass `()` to skip the override
    entirely (the call still no-ops cleanly).
    """
    if not overrides:
        return
    argv: list[str] = ["xcrun", "simctl", "status_bar", udid, "override"]
    for flag, value in overrides:
        argv.extend([flag, value])
    _run(argv, timeout=15)


def clear_status_bar(udid: str) -> None:
    """Drop any active status-bar override and return the bar to its live state."""
    _run(["xcrun", "simctl", "status_bar", udid, "clear"], timeout=15)


def screenshot(udid: str, output_path: str | Path) -> Path:
    """Write a PNG screenshot of the device's current frame and return the path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        ["xcrun", "simctl", "io", udid, "screenshot", str(path)],
        timeout=30,
    )
    if not path.exists():
        raise SimctlError(f"simctl reported success but no file at {path}")
    return path


def read_bundle_id(app_path: str | Path) -> str:
    """Read `CFBundleIdentifier` from a built `.app`'s Info.plist."""
    app = Path(app_path)
    if not app.exists():
        raise SimctlError(f"app bundle not found: {app}")
    plist = app / "Info.plist"
    if not plist.exists():
        raise SimctlError(f"Info.plist missing in {app_path}")
    try:
        with plist.open("rb") as fh:
            data = plistlib.load(fh)
    except (plistlib.InvalidFileException, OSError) as exc:
        raise SimctlError(f"could not parse {plist}: {exc}") from exc
    bundle_id = data.get("CFBundleIdentifier")
    if not bundle_id:
        raise SimctlError(f"CFBundleIdentifier missing in {plist}")
    return str(bundle_id)
