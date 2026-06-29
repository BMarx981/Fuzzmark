"""Unit tests for the simctl wrapper that don't need a real simulator."""

from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from fuzzmark.mobile import simctl
from fuzzmark.mobile.simctl import (
    Device,
    SimctlError,
    _run,
    _runtime_sort_key,
    read_bundle_id,
    resolve_device,
)


def test_runtime_sort_key_orders_newer_runtimes_last() -> None:
    runtimes = [
        "com.apple.CoreSimulator.SimRuntime.iOS-18-4",
        "com.apple.CoreSimulator.SimRuntime.iOS-26-2",
        "com.apple.CoreSimulator.SimRuntime.iOS-18-1",
        "com.apple.CoreSimulator.SimRuntime.iOS-26-0",
    ]
    ordered = sorted(runtimes, key=_runtime_sort_key)
    assert ordered[-1].endswith("iOS-26-2")
    assert ordered[0].endswith("iOS-18-1")


def test_runtime_sort_key_unknown_format_sorts_first() -> None:
    weird = "com.apple.CoreSimulator.SimRuntime.someThingElse"
    assert _runtime_sort_key(weird) == (0, 0, 0)


def _device(name: str, runtime_tail: str, state: str = "Shutdown") -> Device:
    return Device(
        udid=f"udid-{name}-{runtime_tail}",
        name=name,
        runtime=f"com.apple.CoreSimulator.SimRuntime.{runtime_tail}",
        state=state,
    )


def test_resolve_device_prefers_latest_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = [
        _device("iPhone 16", "iOS-18-1"),
        _device("iPhone 16", "iOS-26-2"),
        _device("iPhone 16", "iOS-18-4"),
    ]
    monkeypatch.setattr(simctl, "list_devices", lambda *, available_only=True: fake)
    picked = resolve_device("iPhone 16")
    assert picked.runtime.endswith("iOS-26-2")


def test_resolve_device_prefers_booted_over_newer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = [
        _device("iPhone 16", "iOS-26-2"),
        _device("iPhone 16", "iOS-18-4", state="Booted"),
    ]
    monkeypatch.setattr(simctl, "list_devices", lambda *, available_only=True: fake)
    picked = resolve_device("iPhone 16")
    assert picked.is_booted
    assert picked.runtime.endswith("iOS-18-4")


def test_resolve_device_filters_by_runtime_substring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = [
        _device("iPhone 16", "iOS-26-2"),
        _device("iPhone 16", "iOS-18-4"),
    ]
    monkeypatch.setattr(simctl, "list_devices", lambda *, available_only=True: fake)
    picked = resolve_device("iPhone 16", runtime_contains="iOS-18")
    assert picked.runtime.endswith("iOS-18-4")


def test_resolve_device_raises_when_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(simctl, "list_devices", lambda *, available_only=True: [])
    with pytest.raises(SimctlError, match="no simulator matches"):
        resolve_device("iPhone 16")


def test_run_raises_simctl_error_on_nonzero_exit() -> None:
    # `false` is universally present and exits 1.
    with pytest.raises(SimctlError, match=r"command failed \(1\)"):
        _run(["false"], timeout=5)


def test_run_raises_simctl_error_on_missing_binary() -> None:
    with pytest.raises(SimctlError, match="command not found"):
        _run(["fuzzmark-nonexistent-binary-xyz"], timeout=5)


def test_run_raises_simctl_error_on_timeout() -> None:
    with pytest.raises(SimctlError, match="timed out"):
        _run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)


def test_read_bundle_id_from_app_bundle(tmp_path: Path) -> None:
    app = tmp_path / "Sample.app"
    app.mkdir()
    plist = {"CFBundleIdentifier": "com.fuzzmark.sample"}
    (app / "Info.plist").write_bytes(plistlib.dumps(plist))
    assert read_bundle_id(app) == "com.fuzzmark.sample"


def test_read_bundle_id_missing_plist(tmp_path: Path) -> None:
    app = tmp_path / "Empty.app"
    app.mkdir()
    with pytest.raises(SimctlError, match="Info.plist missing"):
        read_bundle_id(app)


def test_read_bundle_id_plist_without_identifier(tmp_path: Path) -> None:
    app = tmp_path / "NoId.app"
    app.mkdir()
    (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleName": "x"}))
    with pytest.raises(SimctlError, match="CFBundleIdentifier missing"):
        read_bundle_id(app)


def test_list_devices_parses_simctl_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-26-2": [
                {
                    "udid": "UDID-A",
                    "name": "iPhone 16",
                    "state": "Booted",
                    "isAvailable": True,
                },
                {
                    "udid": "UDID-B",
                    "name": "iPad mini",
                    "state": "Shutdown",
                    "isAvailable": True,
                },
            ],
            "com.apple.CoreSimulator.SimRuntime.iOS-18-4": [
                {
                    "udid": "UDID-C",
                    "name": "iPhone 15",
                    "state": "Shutdown",
                    "isAvailable": True,
                },
            ],
        }
    }

    def fake_run(argv, *, timeout=60):
        proc = subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        return proc

    monkeypatch.setattr(simctl, "_run", fake_run)
    devices = simctl.list_devices()
    assert {d.udid for d in devices} == {"UDID-A", "UDID-B", "UDID-C"}
    booted = [d for d in devices if d.is_booted]
    assert len(booted) == 1 and booted[0].udid == "UDID-A"
