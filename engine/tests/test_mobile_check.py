"""Pure unit tests for `mobile.check.check_mobile_test`.

Monkeypatches the `_run_mobile_flow` injection seam so the orchestrator runs
without `xcrun simctl`. Each test synthesizes the PNGs that the fake flow
"writes," then asserts the gate's pass/fail semantics and that the threshold +
masks + report path actually reach `render_report`.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from fuzzmark.compare import MaskRegion
from fuzzmark.mobile import (
    MobileCaptureArtifact,
    MobileRunResult,
    MobileTest,
    check_mobile_test,
    parse_mobile_test,
)
from fuzzmark.mobile import check as check_module


VIEWPORT = "iPhone-17e_iOS-26-5"


def _solid_png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (40, 60)) -> Path:
    h, w = size
    img = np.full((h, w, 3), color, dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return path


def _mobile_test() -> MobileTest:
    return parse_mobile_test(
        {
            "name": "smoke",
            "bundle_id": "com.example.app",
            "flow": [
                {"kind": "launch"},
                {"kind": "capture", "name": "home"},
                {"kind": "capture", "name": "detail"},
            ],
        }
    )


def _fake_flow_factory(
    out_dir: Path,
    *,
    home_color: tuple[int, int, int] = (10, 20, 30),
    detail_color: tuple[int, int, int] = (200, 100, 50),
):
    """Build a fake `run_mobile_flow` that writes the captures it returns."""

    def fake_run(test: MobileTest, target_dir, *, launch_settle_seconds, stabilize_status_bar):
        # Target dir is whatever the orchestrator hands us; mirror real layout.
        viewport_dir = Path(target_dir) / VIEWPORT
        home_path = _solid_png(viewport_dir / "home.png", home_color)
        detail_path = _solid_png(viewport_dir / "detail.png", detail_color)
        return MobileRunResult(
            test_name=test.name,
            device_udid="UDID-0",
            device_name="iPhone 17e",
            runtime="iOS-26.5",
            bundle_id=test.bundle_id,
            viewport=VIEWPORT,
            captures=[
                MobileCaptureArtifact(
                    name="home", step_index=1, screenshot_path=str(home_path), viewport=VIEWPORT
                ),
                MobileCaptureArtifact(
                    name="detail",
                    step_index=2,
                    screenshot_path=str(detail_path),
                    viewport=VIEWPORT,
                ),
            ],
        )

    return fake_run


def _approve_all(baselines_dir: Path, *, home_color, detail_color) -> None:
    """Mirror an `approve` step by writing the same colors into the baseline dir."""
    _solid_png(baselines_dir / VIEWPORT / "home.png", home_color)
    _solid_png(baselines_dir / VIEWPORT / "detail.png", detail_color)


def test_check_passes_when_every_capture_matches_baselines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shots"
    baselines = tmp_path / "baselines"
    home, detail = (10, 20, 30), (200, 100, 50)
    monkeypatch.setattr(check_module, "_run_mobile_flow", _fake_flow_factory(out, home_color=home, detail_color=detail))
    _approve_all(baselines, home_color=home, detail_color=detail)

    result = check_mobile_test(
        _mobile_test(),
        out,
        report_dir=tmp_path / "report",
        baselines_dir=baselines,
    )

    assert result.passed is True
    assert result.failing == ()
    assert {e.verdict for e in result.report.entries} == {"pass"}
    assert Path(result.report.index_path).is_file()


def test_check_fails_when_any_capture_differs_from_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shots"
    baselines = tmp_path / "baselines"
    home = (10, 20, 30)
    monkeypatch.setattr(
        check_module,
        "_run_mobile_flow",
        _fake_flow_factory(out, home_color=home, detail_color=(200, 100, 50)),
    )
    # detail baseline is a different color → that capture won't pass.
    _approve_all(baselines, home_color=home, detail_color=(0, 0, 0))

    result = check_mobile_test(
        _mobile_test(),
        out,
        report_dir=tmp_path / "report",
        baselines_dir=baselines,
    )

    assert result.passed is False
    assert "detail" in result.failing
    assert "home" not in result.failing


def test_check_fails_when_no_baselines_dir_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shots"
    monkeypatch.setattr(check_module, "_run_mobile_flow", _fake_flow_factory(out))

    result = check_mobile_test(
        _mobile_test(),
        out,
        report_dir=tmp_path / "report",
    )

    # Every capture is no-baseline → gate fails.
    assert result.passed is False
    assert set(result.failing) == {"home", "detail"}
    assert {e.verdict for e in result.report.entries} == {"no-baseline"}


def test_check_forwards_threshold_settle_and_status_bar_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def spy(test, target_dir, *, launch_settle_seconds, stabilize_status_bar):
        captured["test_name"] = test.name
        captured["target_dir"] = Path(target_dir)
        captured["launch_settle_seconds"] = launch_settle_seconds
        captured["stabilize_status_bar"] = stabilize_status_bar
        return _fake_flow_factory(Path(target_dir))(
            test,
            target_dir,
            launch_settle_seconds=launch_settle_seconds,
            stabilize_status_bar=stabilize_status_bar,
        )

    monkeypatch.setattr(check_module, "_run_mobile_flow", spy)

    out = tmp_path / "shots"
    check_mobile_test(
        _mobile_test(),
        out,
        report_dir=tmp_path / "report",
        threshold=0.5,
        launch_settle_seconds=0.25,
        stabilize_status_bar=False,
    )

    assert captured["test_name"] == "smoke"
    assert captured["target_dir"] == out
    assert captured["launch_settle_seconds"] == 0.25
    assert captured["stabilize_status_bar"] is False


def test_check_forwards_masks_to_render_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mask covering the differing region should let the otherwise-failing
    capture pass — proves the masks dict reaches `compare_images` via
    `render_report`."""
    out = tmp_path / "shots"
    baselines = tmp_path / "baselines"

    # Baseline + capture differ only in the top-left 10x10 corner.
    def fake_run(test, target_dir, *, launch_settle_seconds, stabilize_status_bar):
        viewport_dir = Path(target_dir) / VIEWPORT
        cap = _solid_png(viewport_dir / "home.png", (10, 20, 30), size=(40, 60))
        # Stamp a different-color square on top-left of the capture only.
        img = cv2.imread(str(cap))
        img[0:10, 0:10] = (255, 255, 255)
        cv2.imwrite(str(cap), img)
        return MobileRunResult(
            test_name=test.name,
            device_udid="UDID-0",
            device_name="iPhone 17e",
            runtime="iOS-26.5",
            bundle_id=test.bundle_id,
            viewport=VIEWPORT,
            captures=[
                MobileCaptureArtifact(
                    name="home", step_index=1, screenshot_path=str(cap), viewport=VIEWPORT
                ),
            ],
        )

    monkeypatch.setattr(check_module, "_run_mobile_flow", fake_run)
    _solid_png(baselines / VIEWPORT / "home.png", (10, 20, 30), size=(40, 60))

    test = parse_mobile_test(
        {
            "name": "masked",
            "bundle_id": "com.example.app",
            "flow": [
                {"kind": "launch"},
                {"kind": "capture", "name": "home"},
            ],
        }
    )

    # Without the mask: the corner difference is caught.
    unmasked = check_mobile_test(
        test, out / "u", report_dir=tmp_path / "report-u", baselines_dir=baselines
    )
    assert unmasked.passed is False

    # With a mask covering the corner: passes.
    masked = check_mobile_test(
        test,
        out / "m",
        report_dir=tmp_path / "report-m",
        baselines_dir=baselines,
        masks={"home": [MaskRegion(x=0, y=0, width=10, height=10)]},
    )
    assert masked.passed is True


def test_check_writes_report_into_report_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shots"
    report_dir = tmp_path / "custom-report"
    monkeypatch.setattr(check_module, "_run_mobile_flow", _fake_flow_factory(out))

    result = check_mobile_test(
        _mobile_test(),
        out,
        report_dir=report_dir,
    )

    assert Path(result.report.output_dir) == report_dir
    assert Path(result.report.index_path).parent == report_dir
    assert (report_dir / "images").is_dir()
