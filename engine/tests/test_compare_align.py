"""Unit tests for the alignment pass (spec §5.7 step 2).

Synthesizes textured images in `tmp_path`. No browser, no fixtures on disk.
The fixtures use a textured pattern rather than solid color so ORB has
something to match against.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from fuzzmark.compare import PASS, SIZE_SHIFT, compare_images
from fuzzmark.compare.align import (
    Alignment,
    MAX_ROTATION_DEG,
    MAX_SCALE_DELTA,
    MIN_INLIER_RATIO,
    _is_small_global_shift,
    try_align_to_baseline,
)


_MARGIN = 24
# Tests run below the runtime default (0.99): warpAffine + sub-pixel ORB
# localization on a synthetic texture lands post-warp SSIM around 0.97–0.99,
# whereas a real screenshot (mostly uniform background) sits closer to 1.0.
# 0.95 stays comfortably above the no-alignment baseline (~0.5) so it still
# exercises the rescue path, just without flaking on stochastic fit error.
_TEST_THRESHOLD = 0.95


def _textured(
    path: Path,
    *,
    size: tuple[int, int] = (300, 400),
    shift: tuple[int, int] = (0, 0),
    seed: int = 0,
) -> Path:
    """Write a textured BGR PNG; `shift=(dy, dx)` slides the crop window.

    The texture is rendered on a canvas larger than `size` (by `_MARGIN` on
    each side) and the output is a slice into that canvas, so a shifted
    candidate contains real neighbouring content — no warpAffine border
    replication noise that would degrade the post-warp SSIM the alignment
    pass is supposed to rescue.
    """
    h, w = size
    H, W = h + 2 * _MARGIN, w + 2 * _MARGIN
    canvas = np.full((H, W, 3), 16, dtype=np.uint8)
    rng = np.random.default_rng(seed)
    for _ in range(160):
        x = int(rng.integers(0, W - 20))
        y = int(rng.integers(0, H - 20))
        bw = int(rng.integers(8, 30))
        bh = int(rng.integers(8, 30))
        color = tuple(int(c) for c in rng.integers(80, 255, size=3))
        cv2.rectangle(canvas, (x, y), (x + bw, y + bh), color, thickness=-1)

    dy, dx = shift
    img = canvas[_MARGIN + dy : _MARGIN + dy + h, _MARGIN + dx : _MARGIN + dx + w]
    cv2.imwrite(str(path), img)
    return path


class TestSizeShiftVerdict:
    def test_small_translation_classifies_as_size_shift(self, tmp_path: Path) -> None:
        baseline = _textured(tmp_path / "base.png", seed=1)
        candidate = _textured(tmp_path / "cand.png", shift=(4, 6), seed=1)
        result = compare_images(baseline, candidate, threshold=_TEST_THRESHOLD)
        assert result.verdict == SIZE_SHIFT
        assert result.alignment is not None
        assert result.alignment["post_warp_score"] >= _TEST_THRESHOLD
        # Pre-warp score must still reflect the raw diff so the user sees the
        # magnitude of the shift, not the rescued post-warp number.
        assert result.score < _TEST_THRESHOLD

    def test_alignment_summary_reports_translation(self, tmp_path: Path) -> None:
        baseline = _textured(tmp_path / "base.png", seed=2)
        # shift=(dy=3, dx=5): the candidate crop slides right-5, down-3 within
        # the larger canvas, so the recovered candidate→baseline warp is +5 in x
        # and +3 in y. Tolerance is wide because ORB localizes sub-pixel.
        candidate = _textured(tmp_path / "cand.png", shift=(3, 5), seed=2)
        result = compare_images(baseline, candidate, threshold=_TEST_THRESHOLD)
        assert result.verdict == SIZE_SHIFT
        assert result.alignment["tx"] == pytest.approx(5.0, abs=1.5)
        assert result.alignment["ty"] == pytest.approx(3.0, abs=1.5)
        assert abs(result.alignment["scale"] - 1.0) < MAX_SCALE_DELTA
        assert abs(result.alignment["rotation_deg"]) < MAX_ROTATION_DEG


class TestUntouched:
    def test_identical_images_stay_pass_and_skip_alignment(self, tmp_path: Path) -> None:
        baseline = _textured(tmp_path / "base.png", seed=3)
        candidate = _textured(tmp_path / "cand.png", seed=3)
        result = compare_images(baseline, candidate, threshold=_TEST_THRESHOLD)
        assert result.verdict == PASS
        assert result.alignment is None

    def test_real_content_change_is_not_rescued_as_size_shift(
        self, tmp_path: Path
    ) -> None:
        """The alignment pass must not flip a real content regression to size-shift.

        Whether the structural classifier then calls it content-change or
        layout-break depends on whether the noise dilates into the same hull
        — that's the structural module's contract, not the alignment pass's."""
        baseline = _textured(tmp_path / "base.png", seed=4)
        candidate = _textured(tmp_path / "cand.png", seed=99)
        result = compare_images(baseline, candidate, threshold=_TEST_THRESHOLD)
        assert result.verdict not in (PASS, SIZE_SHIFT)
        assert result.alignment is None


class TestGateInternals:
    def test_small_shift_passes_gates(self) -> None:
        assert _is_small_global_shift(
            Alignment(tx=4.0, ty=2.0, rotation_deg=0.1, scale=1.0, inlier_ratio=0.8)
        )

    def test_large_rotation_fails_gates(self) -> None:
        assert not _is_small_global_shift(
            Alignment(
                tx=0.0,
                ty=0.0,
                rotation_deg=MAX_ROTATION_DEG + 0.5,
                scale=1.0,
                inlier_ratio=0.8,
            )
        )

    def test_large_scale_change_fails_gates(self) -> None:
        assert not _is_small_global_shift(
            Alignment(
                tx=0.0,
                ty=0.0,
                rotation_deg=0.0,
                scale=1.0 + MAX_SCALE_DELTA + 0.05,
                inlier_ratio=0.8,
            )
        )

    def test_low_inlier_ratio_fails_gates(self) -> None:
        assert not _is_small_global_shift(
            Alignment(
                tx=0.0,
                ty=0.0,
                rotation_deg=0.0,
                scale=1.0,
                inlier_ratio=MIN_INLIER_RATIO - 0.05,
            )
        )


class TestTooFewFeatures:
    def test_solid_color_images_cannot_align(self, tmp_path: Path) -> None:
        """A featureless pair should return None — not pretend to align."""
        h, w = 200, 200
        flat = np.full((h, w, 3), 128, dtype=np.uint8)
        assert try_align_to_baseline(flat, flat) is None
