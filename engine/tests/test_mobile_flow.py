"""Pure unit tests for the MobileTest JSON loader/validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fuzzmark.mobile.flow import (
    CAPTURE,
    LAUNCH,
    OPENURL,
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


def _ok(**overrides) -> dict:
    base = {
        "name": "t",
        "bundle_id": "com.example.app",
        "flow": [
            {"kind": LAUNCH},
            {"kind": CAPTURE, "name": "after-launch"},
        ],
    }
    base.update(overrides)
    return base


def test_parse_minimal_test() -> None:
    test = parse_mobile_test(_ok())
    assert isinstance(test, MobileTest)
    assert test.name == "t"
    assert test.bundle_id == "com.example.app"
    assert test.app is None
    assert len(test.flow) == 2
    assert test.flow[0].kind == LAUNCH
    assert test.flow[1] == MobileFlowStep(kind=CAPTURE, name="after-launch")


def test_round_trip_to_dict_omits_none() -> None:
    raw = _ok(
        device="iPhone 16",
        runtime="iOS-26",
        flow=[
            {"kind": OPENURL, "url": "myapp://x"},
            {"kind": WAIT, "seconds": 0.5},
            {"kind": CAPTURE, "name": "x"},
            {"kind": TERMINATE},
        ],
    )
    test = parse_mobile_test(raw)
    out = test.to_dict()
    assert out["device"] == "iPhone 16"
    assert out["runtime"] == "iOS-26"
    assert out["flow"][0] == {"kind": OPENURL, "url": "myapp://x"}
    assert out["flow"][1] == {"kind": WAIT, "seconds": 0.5}
    assert out["flow"][2] == {"kind": CAPTURE, "name": "x"}
    assert out["flow"][3] == {"kind": TERMINATE}
    assert "app" not in out


def test_load_mobile_test_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "test.json"
    path.write_text(json.dumps(_ok()), encoding="utf-8")
    test = load_mobile_test(path)
    assert test.name == "t"


def test_either_app_or_bundle_id_required() -> None:
    raw = _ok()
    del raw["bundle_id"]
    with pytest.raises(ValueError, match="must declare 'app'"):
        parse_mobile_test(raw)


def test_app_alone_is_sufficient() -> None:
    raw = _ok()
    del raw["bundle_id"]
    raw["app"] = "/some/path/A.app"
    test = parse_mobile_test(raw)
    assert test.app == "/some/path/A.app"
    assert test.bundle_id is None


def test_flow_must_start_with_launch_or_openurl() -> None:
    bad = _ok(flow=[{"kind": CAPTURE, "name": "x"}])
    with pytest.raises(ValueError, match="must begin with"):
        parse_mobile_test(bad)


def test_openurl_first_is_allowed() -> None:
    raw = _ok(
        flow=[
            {"kind": OPENURL, "url": "https://example.com"},
            {"kind": CAPTURE, "name": "x"},
        ]
    )
    parse_mobile_test(raw)  # no raise


def test_flow_requires_a_capture() -> None:
    bad = _ok(flow=[{"kind": LAUNCH}])
    with pytest.raises(ValueError, match="at least one 'capture'"):
        parse_mobile_test(bad)


def test_capture_names_must_be_unique() -> None:
    bad = _ok(
        flow=[
            {"kind": LAUNCH},
            {"kind": CAPTURE, "name": "dup"},
            {"kind": CAPTURE, "name": "dup"},
        ]
    )
    with pytest.raises(ValueError, match="capture step names must be unique"):
        parse_mobile_test(bad)


def test_unknown_kind_rejected() -> None:
    bad = _ok(flow=[{"kind": "fly"}, {"kind": CAPTURE, "name": "x"}])
    with pytest.raises(ValueError, match="unknown kind"):
        parse_mobile_test(bad)


def test_openurl_requires_url() -> None:
    bad = _ok(flow=[{"kind": OPENURL}, {"kind": CAPTURE, "name": "x"}])
    with pytest.raises(ValueError, match="missing fields \\['url'\\]"):
        parse_mobile_test(bad)


def test_openurl_url_must_be_nonempty() -> None:
    bad = _ok(
        flow=[{"kind": OPENURL, "url": "  "}, {"kind": CAPTURE, "name": "x"}]
    )
    with pytest.raises(ValueError, match="non-empty string"):
        parse_mobile_test(bad)


def test_wait_seconds_must_be_positive_number() -> None:
    bad = _ok(
        flow=[
            {"kind": LAUNCH},
            {"kind": WAIT, "seconds": -1},
            {"kind": CAPTURE, "name": "x"},
        ]
    )
    with pytest.raises(ValueError, match=r"> 0"):
        parse_mobile_test(bad)

    bad2 = _ok(
        flow=[
            {"kind": LAUNCH},
            {"kind": WAIT, "seconds": "1"},
            {"kind": CAPTURE, "name": "x"},
        ]
    )
    with pytest.raises(ValueError, match="positive number"):
        parse_mobile_test(bad2)

    bad3 = _ok(
        flow=[
            {"kind": LAUNCH},
            {"kind": WAIT, "seconds": True},
            {"kind": CAPTURE, "name": "x"},
        ]
    )
    with pytest.raises(ValueError, match="positive number"):
        parse_mobile_test(bad3)


def test_capture_requires_name() -> None:
    bad = _ok(flow=[{"kind": LAUNCH}, {"kind": CAPTURE}])
    with pytest.raises(ValueError, match="missing fields \\['name'\\]"):
        parse_mobile_test(bad)


def test_capture_name_must_be_nonempty() -> None:
    bad = _ok(flow=[{"kind": LAUNCH}, {"kind": CAPTURE, "name": "  "}])
    with pytest.raises(ValueError, match="non-empty string"):
        parse_mobile_test(bad)


def test_empty_flow_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty 'flow'"):
        parse_mobile_test(_ok(flow=[]))


def test_missing_name_rejected() -> None:
    raw = _ok()
    del raw["name"]
    with pytest.raises(ValueError, match="non-empty 'name'"):
        parse_mobile_test(raw)


def test_top_level_must_be_object() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_mobile_test([])  # type: ignore[arg-type]


class TestDeviceViewportLabel:
    def test_slugifies_spaces_and_punctuation(self) -> None:
        assert device_viewport_label("iPhone 17e", "iOS-26.5") == "iPhone-17e_iOS-26-5"

    def test_collapses_runs_of_separators(self) -> None:
        assert (
            device_viewport_label("iPad  Pro (11-inch)", "com.apple.CoreSimulator.SimRuntime.iOS-26-5")
            == "iPad-Pro-11-inch_com-apple-CoreSimulator-SimRuntime-iOS-26-5"
        )

    def test_empty_runtime_uses_device_only(self) -> None:
        assert device_viewport_label("iPhone 17e", "") == "iPhone-17e"

    def test_fully_empty_falls_back_to_device_sentinel(self) -> None:
        assert device_viewport_label("", "") == "device"


class TestMobileCaptureArtifactDict:
    def test_omits_viewport_when_none(self) -> None:
        out = MobileCaptureArtifact(
            name="a", step_index=0, screenshot_path="/x.png"
        ).to_dict()
        assert out == {"name": "a", "step_index": 0, "screenshot_path": "/x.png"}

    def test_includes_viewport_when_set(self) -> None:
        out = MobileCaptureArtifact(
            name="a", step_index=2, screenshot_path="/x.png", viewport="iPhone_iOS"
        ).to_dict()
        assert out["viewport"] == "iPhone_iOS"


class TestMobileRunResultDict:
    def test_omits_none_bundle_and_viewport(self) -> None:
        out = MobileRunResult(
            test_name="t",
            device_udid="U",
            device_name="iPhone",
            runtime="iOS-26",
        ).to_dict()
        assert "bundle_id" not in out
        assert "viewport" not in out
        assert out["captures"] == []

    def test_serializes_captures_via_to_dict(self) -> None:
        result = MobileRunResult(
            test_name="t",
            device_udid="U",
            device_name="iPhone",
            runtime="iOS",
            bundle_id="com.x",
            viewport="iPhone_iOS",
            captures=[
                MobileCaptureArtifact(
                    name="a", step_index=0, screenshot_path="/x.png", viewport="iPhone_iOS"
                ),
            ],
        )
        out = result.to_dict()
        assert out["bundle_id"] == "com.x"
        assert out["viewport"] == "iPhone_iOS"
        assert out["captures"][0]["viewport"] == "iPhone_iOS"
