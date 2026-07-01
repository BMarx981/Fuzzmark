"""Pure unit tests for `check.check_test`.

Monkeypatches the `_run_flow` injection seam so the orchestrator runs without
Playwright. Each test synthesizes the PNGs that the fake flow "writes," then
asserts the gate's pass/fail semantics and that the threshold + masks + report
path + viewport/session/headless kwargs actually reach the callees.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from fuzzmark import check as check_module
from fuzzmark.check import check_test
from fuzzmark.compare import MaskRegion
from fuzzmark.driver import CaptureArtifact, RunResult, Test, parse_test


def _solid_png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (40, 60)) -> Path:
    h, w = size
    img = np.full((h, w, 3), color, dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return path


def _web_test() -> Test:
    return parse_test(
        {
            "name": "smoke",
            "flow": [
                {"kind": "visit", "url": "https://example.com"},
                {"kind": "capture", "name": "home"},
                {"kind": "capture", "name": "detail"},
            ],
        }
    )


def _fake_flow_factory(
    *,
    home_color: tuple[int, int, int] = (10, 20, 30),
    detail_color: tuple[int, int, int] = (200, 100, 50),
):
    """Build a fake `run_flow` that writes the captures it returns."""

    def fake_run(test: Test, output_dir, *, viewport, headless, slow_mo_ms, session):
        out = Path(output_dir)
        home_path = _solid_png(out / "home.png", home_color)
        detail_path = _solid_png(out / "detail.png", detail_color)
        return RunResult(
            test_name=test.name,
            captures=[
                CaptureArtifact(name="home", step_index=1, screenshot_path=str(home_path)),
                CaptureArtifact(name="detail", step_index=2, screenshot_path=str(detail_path)),
            ],
        )

    return fake_run


def _approve_all(baselines_dir: Path, *, home_color, detail_color) -> None:
    _solid_png(baselines_dir / "home.png", home_color)
    _solid_png(baselines_dir / "detail.png", detail_color)


def test_check_passes_when_every_capture_matches_baselines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shots"
    baselines = tmp_path / "baselines"
    home, detail = (10, 20, 30), (200, 100, 50)
    monkeypatch.setattr(
        check_module,
        "_run_flow",
        _fake_flow_factory(home_color=home, detail_color=detail),
    )
    _approve_all(baselines, home_color=home, detail_color=detail)

    result = check_test(
        _web_test(),
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
        "_run_flow",
        _fake_flow_factory(home_color=home, detail_color=(200, 100, 50)),
    )
    _approve_all(baselines, home_color=home, detail_color=(0, 0, 0))

    result = check_test(
        _web_test(),
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
    monkeypatch.setattr(check_module, "_run_flow", _fake_flow_factory())

    result = check_test(
        _web_test(),
        out,
        report_dir=tmp_path / "report",
    )

    assert result.passed is False
    assert set(result.failing) == {"home", "detail"}
    assert {e.verdict for e in result.report.entries} == {"no-baseline"}


def test_check_forwards_viewport_headless_session_slow_mo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def spy(test, output_dir, *, viewport, headless, slow_mo_ms, session):
        captured["test_name"] = test.name
        captured["output_dir"] = Path(output_dir)
        captured["viewport"] = viewport
        captured["headless"] = headless
        captured["slow_mo_ms"] = slow_mo_ms
        captured["session"] = session
        return _fake_flow_factory()(
            test,
            output_dir,
            viewport=viewport,
            headless=headless,
            slow_mo_ms=slow_mo_ms,
            session=session,
        )

    monkeypatch.setattr(check_module, "_run_flow", spy)

    out = tmp_path / "shots"
    check_test(
        _web_test(),
        out,
        report_dir=tmp_path / "report",
        viewport=(414, 896),
        headless=False,
        slow_mo_ms=250,
        session="/tmp/session.json",
    )

    assert captured["test_name"] == "smoke"
    assert captured["output_dir"] == out
    assert captured["viewport"] == (414, 896)
    assert captured["headless"] is False
    assert captured["slow_mo_ms"] == 250
    assert captured["session"] == "/tmp/session.json"


def test_check_forwards_masks_to_render_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mask covering the differing region should let the otherwise-failing
    capture pass — proves the masks dict reaches `compare_images` via
    `render_report`."""
    out = tmp_path / "shots"
    baselines = tmp_path / "baselines"

    def fake_run(test, output_dir, *, viewport, headless, slow_mo_ms, session):
        target = Path(output_dir)
        cap = _solid_png(target / "home.png", (10, 20, 30), size=(40, 60))
        img = cv2.imread(str(cap))
        img[0:10, 0:10] = (255, 255, 255)
        cv2.imwrite(str(cap), img)
        return RunResult(
            test_name=test.name,
            captures=[
                CaptureArtifact(name="home", step_index=1, screenshot_path=str(cap)),
            ],
        )

    monkeypatch.setattr(check_module, "_run_flow", fake_run)
    _solid_png(baselines / "home.png", (10, 20, 30), size=(40, 60))

    test = parse_test(
        {
            "name": "masked",
            "flow": [
                {"kind": "visit", "url": "https://example.com"},
                {"kind": "capture", "name": "home"},
            ],
        }
    )

    unmasked = check_test(
        test, out / "u", report_dir=tmp_path / "report-u", baselines_dir=baselines
    )
    assert unmasked.passed is False

    masked = check_test(
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
    monkeypatch.setattr(check_module, "_run_flow", _fake_flow_factory())

    result = check_test(
        _web_test(),
        out,
        report_dir=report_dir,
    )

    assert Path(result.report.output_dir) == report_dir
    assert Path(result.report.index_path).parent == report_dir
    assert (report_dir / "images").is_dir()
