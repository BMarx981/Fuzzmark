"""Tests for the HTML report renderer.

Pure: synthesizes PNGs in `tmp_path` and feeds dicts directly, no browser.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from fuzzmark.compare import CHANGE, PASS
from fuzzmark.report import NO_BASELINE, render_report


def _solid(path: Path, color: tuple[int, int, int]) -> Path:
    img = np.full((40, 60, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def _run_result(
    captures_dir: Path,
    captures: list[tuple[str, int, tuple[int, int, int]]],
    *,
    test_name: str = "demo",
    console_errors: list[dict] | None = None,
    page_errors: list[str] | None = None,
    failed_requests: list[dict] | None = None,
) -> dict:
    captures_dir.mkdir(parents=True, exist_ok=True)
    return {
        "test_name": test_name,
        "captures": [
            {
                "name": name,
                "step_index": idx,
                "screenshot_path": str(_solid(captures_dir / f"{name}.png", color)),
            }
            for name, idx, color in captures
        ],
        "console_errors": console_errors or [],
        "page_errors": page_errors or [],
        "failed_requests": failed_requests or [],
    }


class TestNoBaselines:
    def test_each_capture_marked_no_baseline(self, tmp_path: Path) -> None:
        result = _run_result(
            tmp_path / "shots",
            [("a", 0, (0, 0, 0)), ("b", 1, (255, 255, 255))],
        )
        report = render_report(result, tmp_path / "report")
        assert {e.verdict for e in report.entries} == {NO_BASELINE}
        assert report.verdict_counts == {NO_BASELINE: 2}

    def test_writes_index_html_and_copies_captures(self, tmp_path: Path) -> None:
        result = _run_result(tmp_path / "shots", [("a", 0, (0, 0, 0))])
        report = render_report(result, tmp_path / "report")
        index = Path(report.index_path)
        assert index.exists()
        assert (tmp_path / "report" / "images" / "a.png").exists()
        html = index.read_text(encoding="utf-8")
        assert "<title>demo</title>" in html
        assert "no-baseline" in html


class TestWithBaselines:
    def test_matching_baseline_yields_pass(self, tmp_path: Path) -> None:
        result = _run_result(tmp_path / "shots", [("a", 0, (10, 20, 30))])
        baselines = tmp_path / "baselines"
        baselines.mkdir()
        _solid(baselines / "a.png", (10, 20, 30))

        report = render_report(result, tmp_path / "report", baselines_dir=baselines)
        entry = report.entries[0]
        assert entry.verdict == PASS
        assert entry.score == pytest.approx(1.0, abs=1e-9)
        assert (tmp_path / "report" / "images" / "a__baseline.png").exists()
        assert (tmp_path / "report" / "images" / "a__diff.png").exists()

    def test_different_baseline_yields_change(self, tmp_path: Path) -> None:
        result = _run_result(tmp_path / "shots", [("a", 0, (0, 0, 0))])
        baselines = tmp_path / "baselines"
        baselines.mkdir()
        _solid(baselines / "a.png", (255, 255, 255))

        report = render_report(result, tmp_path / "report", baselines_dir=baselines)
        assert report.entries[0].verdict == CHANGE
        assert report.verdict_counts == {CHANGE: 1}

    def test_missing_baseline_for_one_capture_falls_back_to_no_baseline(
        self, tmp_path: Path
    ) -> None:
        result = _run_result(
            tmp_path / "shots",
            [("present", 0, (50, 50, 50)), ("missing", 1, (50, 50, 50))],
        )
        baselines = tmp_path / "baselines"
        baselines.mkdir()
        _solid(baselines / "present.png", (50, 50, 50))

        report = render_report(result, tmp_path / "report", baselines_dir=baselines)
        verdicts = {e.name: e.verdict for e in report.entries}
        assert verdicts == {"present": PASS, "missing": NO_BASELINE}


class TestOrdering:
    def test_failures_render_before_passes(self, tmp_path: Path) -> None:
        result = _run_result(
            tmp_path / "shots",
            [
                ("pass-step", 0, (10, 10, 10)),
                ("change-step", 1, (10, 10, 10)),
            ],
        )
        baselines = tmp_path / "baselines"
        baselines.mkdir()
        _solid(baselines / "pass-step.png", (10, 10, 10))
        _solid(baselines / "change-step.png", (240, 240, 240))

        report = render_report(result, tmp_path / "report", baselines_dir=baselines)
        html = Path(report.index_path).read_text(encoding="utf-8")
        assert html.index("change-step") < html.index("pass-step")


class TestErrorPanel:
    def test_no_errors_shows_empty_message(self, tmp_path: Path) -> None:
        result = _run_result(tmp_path / "shots", [("a", 0, (0, 0, 0))])
        report = render_report(result, tmp_path / "report")
        html = Path(report.index_path).read_text(encoding="utf-8")
        assert "No errors collected." in html

    def test_console_page_and_request_errors_render(self, tmp_path: Path) -> None:
        result = _run_result(
            tmp_path / "shots",
            [("a", 0, (0, 0, 0))],
            console_errors=[{"level": "error", "text": "boom"}],
            page_errors=["TypeError: x"],
            failed_requests=[{"url": "http://x/y", "method": "GET", "status": 500}],
        )
        report = render_report(result, tmp_path / "report")
        html = Path(report.index_path).read_text(encoding="utf-8")
        assert "boom" in html
        assert "TypeError: x" in html
        assert "http://x/y" in html
        assert "500" in html

    def test_html_escapes_error_payloads(self, tmp_path: Path) -> None:
        result = _run_result(
            tmp_path / "shots",
            [("a", 0, (0, 0, 0))],
            page_errors=["<script>alert(1)</script>"],
        )
        report = render_report(result, tmp_path / "report")
        html = Path(report.index_path).read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestIdempotency:
    def test_rerender_overwrites_in_place(self, tmp_path: Path) -> None:
        result = _run_result(tmp_path / "shots", [("a", 0, (0, 0, 0))])
        first = render_report(result, tmp_path / "report")
        first_bytes = Path(first.index_path).read_bytes()
        second = render_report(result, tmp_path / "report")
        assert Path(second.index_path).read_bytes() == first_bytes


class TestPaths:
    def test_image_srcs_are_relative_to_output(self, tmp_path: Path) -> None:
        result = _run_result(tmp_path / "shots", [("a", 0, (0, 0, 0))])
        report = render_report(result, tmp_path / "report")
        html = Path(report.index_path).read_text(encoding="utf-8")
        assert 'src="images/a.png"' in html
        assert str(tmp_path) not in html
