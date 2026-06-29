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
    device_viewport_label,
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
    """openurl with an http: URL routes through Safari. The flow drives Safari
    to two distinct URLs and asserts the two captures differ — this avoids
    Safari's session-restore behavior (which can leave a prior URL loaded on
    launch and mask a no-op openurl)."""
    test = parse_mobile_test(
        {
            "name": "safari-openurl",
            "bundle_id": SAFARI_BUNDLE_ID,
            "flow": [
                {"kind": "launch"},
                {"kind": "openurl", "url": "https://example.com"},
                {"kind": "wait", "seconds": 3.0},
                {"kind": "capture", "name": "example"},
                {"kind": "openurl", "url": "https://example.org"},
                {"kind": "wait", "seconds": 3.0},
                {"kind": "capture", "name": "example-org"},
                {"kind": "terminate"},
            ],
        }
    )
    result = run_mobile_flow(test, tmp_path)

    names = [c.name for c in result.captures]
    assert names == ["example", "example-org"]
    com_png = Path(result.captures[0].screenshot_path).read_bytes()
    org_png = Path(result.captures[1].screenshot_path).read_bytes()
    assert com_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert org_png[:8] == b"\x89PNG\r\n\x1a\n"
    # Two distinct sites must render to different pixels; this guards against
    # an openurl step being silently dropped.
    assert com_png != org_png


def test_run_mobile_flow_tags_viewport_and_nests_screenshot(
    _simctl_present: None, tmp_path: Path
) -> None:
    """Captures inherit the device viewport tag and land under `<out>/<viewport>/`,
    matching the baseline-store layout that `fuzzmark report` and `approve`
    consume."""
    test = parse_mobile_test(
        {
            "name": "safari-viewport-tag",
            "bundle_id": SAFARI_BUNDLE_ID,
            "flow": [
                {"kind": "launch"},
                {"kind": "wait", "seconds": 0.5},
                {"kind": "capture", "name": "launched"},
                {"kind": "terminate"},
            ],
        }
    )
    result = run_mobile_flow(test, tmp_path)

    expected = device_viewport_label(result.device_name, result.runtime)
    assert result.viewport == expected
    cap = result.captures[0]
    assert cap.viewport == expected
    out = Path(cap.screenshot_path)
    assert out.parent == tmp_path / expected
    assert out.exists()


def test_status_bar_override_makes_consecutive_captures_byte_identical(
    _simctl_present: None, tmp_path: Path
) -> None:
    """The mobile counterpart to the MVP no-false-positive gate: with
    `stabilize_status_bar=True` (the default), two captures of the same Safari
    frame, taken seconds apart, must be byte-for-byte identical so the
    comparison pipeline never reports a spurious diff on the live clock."""
    test = parse_mobile_test(
        {
            "name": "safari-status-bar-determinism",
            "bundle_id": SAFARI_BUNDLE_ID,
            "flow": [
                {"kind": "launch"},
                {"kind": "wait", "seconds": 1.0},
                {"kind": "capture", "name": "first"},
                {"kind": "wait", "seconds": 2.0},
                {"kind": "capture", "name": "second"},
                {"kind": "terminate"},
            ],
        }
    )
    result = run_mobile_flow(test, tmp_path)

    first = Path(result.captures[0].screenshot_path).read_bytes()
    second = Path(result.captures[1].screenshot_path).read_bytes()
    assert first == second, (
        "consecutive captures of the same Safari frame should be byte-identical "
        "with the status bar overridden; got len(first)={a} len(second)={b}".format(
            a=len(first), b=len(second)
        )
    )


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
