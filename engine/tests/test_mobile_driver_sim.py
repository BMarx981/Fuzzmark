"""Live-sim run_mobile_flow test using Mobile Safari (built into every sim)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.simulator

if sys.platform != "darwin":
    pytest.skip("iOS Simulator is macOS-only", allow_module_level=True)

from fuzzmark.mobile import (  # noqa: E402
    MobileTest,
    parse_mobile_test,
    run_mobile_flow,
    simctl_available,
)


SAFARI_BUNDLE_ID = "com.apple.mobilesafari"


@pytest.fixture(scope="module")
def _simctl_present() -> None:
    if not simctl_available():
        pytest.skip("`xcrun simctl` not available on this host")


def test_run_mobile_flow_safari_launch_and_capture(
    _simctl_present: None, tmp_path: Path
) -> None:
    test = parse_mobile_test(
        {
            "name": "safari-smoke",
            "bundle_id": SAFARI_BUNDLE_ID,
            "flow": [
                {"kind": "launch"},
                {"kind": "wait", "seconds": 1.0},
                {"kind": "capture", "name": "safari-launched"},
                {"kind": "terminate"},
            ],
        }
    )
    result = run_mobile_flow(test, tmp_path)

    assert result.test_name == "safari-smoke"
    assert result.bundle_id == SAFARI_BUNDLE_ID
    assert result.device_udid
    assert len(result.captures) == 1
    cap = result.captures[0]
    assert cap.name == "safari-launched"
    assert cap.step_index == 2  # 0:launch, 1:wait, 2:capture
    out = Path(cap.screenshot_path)
    assert out.exists() and out.stat().st_size > 0
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_run_mobile_flow_openurl_via_safari(
    _simctl_present: None, tmp_path: Path
) -> None:
    """openurl with an http: URL routes through Safari and produces a different
    screenshot than the bare launch frame."""
    test = parse_mobile_test(
        {
            "name": "safari-openurl",
            "bundle_id": SAFARI_BUNDLE_ID,
            "flow": [
                {"kind": "launch"},
                {"kind": "wait", "seconds": 0.5},
                {"kind": "capture", "name": "before"},
                {"kind": "openurl", "url": "https://example.com"},
                {"kind": "wait", "seconds": 3.0},
                {"kind": "capture", "name": "after"},
                {"kind": "terminate"},
            ],
        }
    )
    result = run_mobile_flow(test, tmp_path)

    names = [c.name for c in result.captures]
    assert names == ["before", "after"]
    before = Path(result.captures[0].screenshot_path).read_bytes()
    after = Path(result.captures[1].screenshot_path).read_bytes()
    assert before[:8] == b"\x89PNG\r\n\x1a\n"
    assert after[:8] == b"\x89PNG\r\n\x1a\n"
    # Frames differ once the URL has loaded; this guards against the openurl
    # step being silently dropped.
    assert before != after


def test_run_mobile_flow_capture_name_with_unsafe_chars(
    _simctl_present: None, tmp_path: Path
) -> None:
    test = MobileTest(
        name="unsafe-name",
        bundle_id=SAFARI_BUNDLE_ID,
        flow=parse_mobile_test(
            {
                "name": "x",
                "bundle_id": SAFARI_BUNDLE_ID,
                "flow": [
                    {"kind": "launch"},
                    {"kind": "capture", "name": "step 1 / final"},
                ],
            }
        ).flow,
    )
    result = run_mobile_flow(test, tmp_path)
    out = Path(result.captures[0].screenshot_path)
    assert "/" not in out.name and " " not in out.name
    assert out.exists()
