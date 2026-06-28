"""Unit tests for the structural classifier (spec §5.7 step 4).

Pure: synthesizes images in `tmp_path` and numpy in memory. No browser.

The classifier sits downstream of SSIM and alignment, so these tests drive
`compare_images` end-to-end on synthetic layouts where the structural
verdict is the only one in play. The DoD breakage fixtures get their own
browser-gated check in `test_compare_structure_browser.py`.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from fuzzmark.compare import (
    CONTENT_CHANGE,
    LAYOUT_BREAK,
    PASS,
    compare_images,
    compare_structure,
    detect_blocks,
    is_layout_intact,
)
from fuzzmark.compare.structure import (
    MATCH_THRESHOLD,
    Box,
    StructuralSummary,
)


_W, _H = 400, 300


def _blank(color: tuple[int, int, int] = (240, 240, 240)) -> np.ndarray:
    """Light-grey background — Canny finds no edges, so detect_blocks returns []."""
    return np.full((_H, _W, 3), color, dtype=np.uint8)


def _with_box(
    canvas: np.ndarray, xywh: tuple[int, int, int, int], color: tuple[int, int, int]
) -> np.ndarray:
    out = canvas.copy()
    x, y, w, h = xywh
    cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness=-1)
    return out


def _save(path: Path, img: np.ndarray) -> Path:
    cv2.imwrite(str(path), img)
    return path


class TestBox:
    def test_iou_identical_is_one(self) -> None:
        a = Box(10, 10, 30, 30)
        assert a.iou(a) == 1.0

    def test_iou_disjoint_is_zero(self) -> None:
        a = Box(0, 0, 10, 10)
        b = Box(100, 100, 10, 10)
        assert a.iou(b) == 0.0

    def test_iou_partial_overlap_between_0_and_1(self) -> None:
        a = Box(0, 0, 10, 10)
        b = Box(5, 5, 10, 10)
        assert 0.0 < a.iou(b) < 1.0


class TestDetectBlocks:
    def test_blank_image_returns_empty(self) -> None:
        assert detect_blocks(_blank()) == []

    def test_single_solid_rect_detected(self) -> None:
        img = _with_box(_blank(), (100, 80, 120, 60), (0, 0, 0))
        boxes = detect_blocks(img)
        assert len(boxes) == 1
        # Bounding box should roughly match the painted rect (dilation grows it).
        b = boxes[0]
        assert b.x <= 100 and b.y <= 80
        assert b.x + b.w >= 100 + 120
        assert b.y + b.h >= 80 + 60

    def test_widely_spaced_rects_yield_two_blocks(self) -> None:
        img = _with_box(_blank(), (20, 20, 60, 60), (0, 0, 0))
        img = _with_box(img, (250, 200, 60, 60), (0, 0, 0))
        boxes = detect_blocks(img)
        assert len(boxes) == 2


class TestCompareStructure:
    def test_identical_layout_scores_one(self) -> None:
        a = _with_box(_blank(), (50, 50, 80, 60), (0, 0, 0))
        summary = compare_structure(a, a)
        assert summary.match_score == 1.0
        assert summary.matched_boxes == summary.baseline_boxes

    def test_recolored_block_keeps_layout_intact(self) -> None:
        """Block in the same place, just a different fill: layout intact."""
        baseline = _with_box(_blank(), (50, 50, 80, 60), (40, 40, 40))
        candidate = _with_box(_blank(), (50, 50, 80, 60), (200, 50, 50))
        summary = compare_structure(baseline, candidate)
        assert is_layout_intact(summary)

    def test_moved_block_breaks_layout(self) -> None:
        baseline = _with_box(_blank(), (40, 40, 80, 60), (0, 0, 0))
        candidate = _with_box(_blank(), (260, 200, 80, 60), (0, 0, 0))
        summary = compare_structure(baseline, candidate)
        assert not is_layout_intact(summary)

    def test_added_block_breaks_layout(self) -> None:
        baseline = _with_box(_blank(), (40, 40, 80, 60), (0, 0, 0))
        candidate = _with_box(baseline, (260, 200, 80, 60), (0, 0, 0))
        summary = compare_structure(baseline, candidate)
        assert not is_layout_intact(summary)

    def test_removed_block_breaks_layout(self) -> None:
        baseline = _with_box(_blank(), (40, 40, 80, 60), (0, 0, 0))
        baseline = _with_box(baseline, (260, 200, 80, 60), (0, 0, 0))
        candidate = _with_box(_blank(), (40, 40, 80, 60), (0, 0, 0))
        summary = compare_structure(baseline, candidate)
        assert not is_layout_intact(summary)

    def test_both_empty_layouts_treated_as_intact(self) -> None:
        """Solid → solid: no blocks anywhere, so the topology vacuously matches."""
        summary = compare_structure(_blank(), _blank((50, 50, 50)))
        assert summary.match_score == 1.0
        assert is_layout_intact(summary)

    def test_one_side_empty_breaks_layout(self) -> None:
        baseline = _blank()
        candidate = _with_box(_blank(), (40, 40, 80, 60), (0, 0, 0))
        summary = compare_structure(baseline, candidate)
        assert summary.match_score == 0.0
        assert not is_layout_intact(summary)


class TestVerdictsEndToEnd:
    def test_color_change_inside_same_block_is_content_change(
        self, tmp_path: Path
    ) -> None:
        baseline = _save(
            tmp_path / "base.png", _with_box(_blank(), (50, 50, 200, 120), (50, 50, 50))
        )
        candidate = _save(
            tmp_path / "cand.png",
            _with_box(_blank(), (50, 50, 200, 120), (200, 50, 50)),
        )
        result = compare_images(baseline, candidate)
        assert result.verdict == CONTENT_CHANGE
        assert result.structure is not None
        assert result.structure["match_score"] >= MATCH_THRESHOLD

    def test_moved_block_is_layout_break(self, tmp_path: Path) -> None:
        baseline = _save(
            tmp_path / "base.png", _with_box(_blank(), (40, 40, 100, 60), (0, 0, 0))
        )
        candidate = _save(
            tmp_path / "cand.png",
            _with_box(_blank(), (260, 200, 100, 60), (0, 0, 0)),
        )
        result = compare_images(baseline, candidate)
        assert result.verdict == LAYOUT_BREAK
        assert result.structure is not None
        assert result.structure["match_score"] < MATCH_THRESHOLD

    def test_added_block_is_layout_break(self, tmp_path: Path) -> None:
        base_img = _with_box(_blank(), (40, 40, 80, 60), (0, 0, 0))
        cand_img = _with_box(base_img, (260, 200, 100, 60), (0, 0, 0))
        baseline = _save(tmp_path / "base.png", base_img)
        candidate = _save(tmp_path / "cand.png", cand_img)
        result = compare_images(baseline, candidate)
        assert result.verdict == LAYOUT_BREAK

    def test_identical_capture_stays_pass_and_skips_structure(
        self, tmp_path: Path
    ) -> None:
        img = _with_box(_blank(), (50, 50, 80, 60), (0, 0, 0))
        baseline = _save(tmp_path / "base.png", img)
        candidate = _save(tmp_path / "cand.png", img)
        result = compare_images(baseline, candidate)
        assert result.verdict == PASS
        assert result.structure is None


class TestSummarySerialisation:
    def test_to_dict_round_trip(self) -> None:
        s = StructuralSummary(
            baseline_boxes=3, candidate_boxes=4, matched_boxes=3, match_score=0.8
        )
        assert s.to_dict() == {
            "baseline_boxes": 3,
            "candidate_boxes": 4,
            "matched_boxes": 3,
            "match_score": 0.8,
        }
