"""Unit tests for the SSIM-based comparison engine.

Pure: synthesize PNGs in `tmp_path`, no browser, no fixtures on disk.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from fuzzmark.compare import CHANGE, PASS, compare_images


def _solid(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> Path:
    """Write a solid-color BGR PNG."""
    h, w = size
    img = np.full((h, w, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def _checkerboard(path: Path, size: tuple[int, int] = (200, 200), tile: int = 20) -> Path:
    h, w = size
    img = np.zeros((h, w, 3), dtype=np.uint8)
    yi, xi = np.indices((h, w))
    mask = ((yi // tile) + (xi // tile)) % 2 == 0
    img[mask] = (255, 255, 255)
    cv2.imwrite(str(path), img)
    return path


class TestIdentical:
    def test_identical_images_pass_with_score_1(self, tmp_path: Path) -> None:
        a = _solid(tmp_path / "a.png", (200, 100, 50))
        b = _solid(tmp_path / "b.png", (200, 100, 50))
        result = compare_images(a, b)
        assert result.verdict == PASS
        assert result.score == pytest.approx(1.0, abs=1e-9)


class TestChange:
    def test_clearly_different_images_register_as_change(self, tmp_path: Path) -> None:
        baseline = _solid(tmp_path / "base.png", (0, 0, 0))
        candidate = _solid(tmp_path / "cand.png", (255, 255, 255))
        result = compare_images(baseline, candidate)
        assert result.verdict == CHANGE
        assert result.score < 0.99

    def test_structural_change_caught(self, tmp_path: Path) -> None:
        baseline = _solid(tmp_path / "base.png", (255, 255, 255))
        candidate = _checkerboard(tmp_path / "cand.png")
        result = compare_images(baseline, candidate)
        assert result.verdict == CHANGE


class TestThresholdTuning:
    def test_lower_threshold_can_flip_change_to_pass(self, tmp_path: Path) -> None:
        baseline = _solid(tmp_path / "base.png", (100, 100, 100))
        candidate = _solid(tmp_path / "cand.png", (110, 110, 110))
        strict = compare_images(baseline, candidate, threshold=0.999)
        lenient = compare_images(baseline, candidate, threshold=0.5)
        assert strict.score == lenient.score
        assert strict.verdict == CHANGE
        assert lenient.verdict == PASS


class TestSizeNormalization:
    def test_size_mismatch_does_not_error(self, tmp_path: Path) -> None:
        baseline = _solid(tmp_path / "base.png", (50, 100, 200), size=(200, 200))
        candidate = _solid(tmp_path / "cand.png", (50, 100, 200), size=(100, 100))
        result = compare_images(baseline, candidate)
        assert result.verdict == PASS


class TestHeatmap:
    def test_diff_path_writes_heatmap_png(self, tmp_path: Path) -> None:
        baseline = _solid(tmp_path / "base.png", (0, 0, 0))
        candidate = _checkerboard(tmp_path / "cand.png")
        out = tmp_path / "heat.png"
        result = compare_images(baseline, candidate, diff_path=out)
        assert result.diff_path == str(out)
        assert out.exists()
        assert out.stat().st_size > 0
        loaded = cv2.imread(str(out), cv2.IMREAD_COLOR)
        assert loaded is not None
        assert loaded.shape[:2] == (200, 200)


class TestMissingFile:
    def test_missing_baseline_raises(self, tmp_path: Path) -> None:
        existing = _solid(tmp_path / "ok.png", (0, 0, 0))
        with pytest.raises(FileNotFoundError):
            compare_images(tmp_path / "nope.png", existing)

    def test_missing_candidate_raises(self, tmp_path: Path) -> None:
        existing = _solid(tmp_path / "ok.png", (0, 0, 0))
        with pytest.raises(FileNotFoundError):
            compare_images(existing, tmp_path / "nope.png")


class TestSymmetry:
    def test_score_is_symmetric_within_tolerance(self, tmp_path: Path) -> None:
        a = _checkerboard(tmp_path / "a.png", tile=20)
        b = _checkerboard(tmp_path / "b.png", tile=40)
        forward = compare_images(a, b).score
        reverse = compare_images(b, a).score
        assert forward == pytest.approx(reverse, abs=1e-6)
