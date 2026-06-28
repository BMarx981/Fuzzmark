"""Tests for region-based masks in the comparison engine.

Pure: synthesize PNGs and numpy arrays in `tmp_path`. No browser.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from fuzzmark.compare import (
    CHANGE,
    PASS,
    MaskRegion,
    apply_masks,
    clamp_region,
    compare_images,
    parse_mask_spec,
)


def _solid(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> Path:
    h, w = size
    img = np.full((h, w, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def _solid_with_patch(
    path: Path,
    base: tuple[int, int, int],
    patch: tuple[int, int, int],
    patch_xywh: tuple[int, int, int, int] = (40, 40, 60, 60),
    size: tuple[int, int] = (200, 200),
) -> Path:
    h, w = size
    img = np.full((h, w, 3), base, dtype=np.uint8)
    x, y, pw, ph = patch_xywh
    img[y : y + ph, x : x + pw] = patch
    cv2.imwrite(str(path), img)
    return path


class TestParseMaskSpec:
    def test_four_part_spec_parses(self):
        m = parse_mask_spec("10,20,30,40")
        assert m == MaskRegion(10, 20, 30, 40, source="region")

    def test_five_part_spec_carries_source(self):
        m = parse_mask_spec("0,0,5,5,#clock")
        assert m.source == "#clock"

    def test_handles_whitespace(self):
        m = parse_mask_spec(" 1 , 2 , 3 , 4 ")
        assert m == MaskRegion(1, 2, 3, 4, source="region")

    def test_rejects_wrong_arity(self):
        with pytest.raises(ValueError):
            parse_mask_spec("1,2,3")

    def test_rejects_non_integer_coords(self):
        with pytest.raises(ValueError):
            parse_mask_spec("a,b,c,d")

    def test_rejects_zero_or_negative_dims(self):
        with pytest.raises(ValueError):
            parse_mask_spec("0,0,0,10")
        with pytest.raises(ValueError):
            parse_mask_spec("0,0,10,-1")


class TestClamp:
    def test_inside_region_passes_through(self):
        m = MaskRegion(5, 5, 10, 10)
        assert clamp_region(m, (50, 50, 3)) == m

    def test_overhang_is_clamped_to_bounds(self):
        m = MaskRegion(40, 40, 30, 30)
        clamped = clamp_region(m, (50, 50, 3))
        assert clamped == MaskRegion(40, 40, 10, 10)

    def test_fully_outside_returns_none(self):
        m = MaskRegion(60, 60, 10, 10)
        assert clamp_region(m, (50, 50, 3)) is None

    def test_negative_origin_is_clamped(self):
        m = MaskRegion(-5, -5, 20, 20)
        clamped = clamp_region(m, (50, 50, 3))
        assert clamped == MaskRegion(0, 0, 15, 15)


class TestApplyMasks:
    def test_empty_region_list_returns_original_image(self):
        img = np.full((10, 10, 3), 200, dtype=np.uint8)
        out = apply_masks(img, [])
        assert out is img  # short-circuit, not a copy

    def test_blanks_specified_region(self):
        img = np.full((10, 10, 3), 200, dtype=np.uint8)
        out = apply_masks(img, [MaskRegion(2, 2, 4, 4)])
        assert (out[2:6, 2:6] == 0).all()
        assert out[0, 0].tolist() == [200, 200, 200]

    def test_does_not_mutate_input(self):
        img = np.full((10, 10, 3), 200, dtype=np.uint8)
        apply_masks(img, [MaskRegion(0, 0, 5, 5)])
        assert (img == 200).all()

    def test_fill_color_respected(self):
        img = np.full((10, 10, 3), 200, dtype=np.uint8)
        out = apply_masks(img, [MaskRegion(0, 0, 3, 3)], fill=(10, 20, 30))
        assert out[0, 0].tolist() == [10, 20, 30]

    def test_out_of_bounds_region_skipped(self):
        img = np.full((10, 10, 3), 200, dtype=np.uint8)
        out = apply_masks(img, [MaskRegion(100, 100, 5, 5)])
        assert (out == 200).all()


class TestCompareWithMasks:
    def test_mask_over_only_difference_lifts_score_to_pass(self, tmp_path: Path):
        base = _solid(tmp_path / "base.png", (200, 100, 50))
        cand = _solid_with_patch(
            tmp_path / "cand.png",
            base=(200, 100, 50),
            patch=(0, 255, 0),
            patch_xywh=(40, 40, 60, 60),
        )
        unmasked = compare_images(base, cand, threshold=0.99)
        masked = compare_images(
            base, cand, threshold=0.99, masks=[MaskRegion(40, 40, 60, 60)]
        )
        assert unmasked.verdict == CHANGE
        assert masked.verdict == PASS
        assert masked.score > unmasked.score

    def test_mask_on_identical_pair_stays_pass(self, tmp_path: Path):
        base = _solid(tmp_path / "base.png", (50, 50, 50))
        cand = _solid(tmp_path / "cand.png", (50, 50, 50))
        result = compare_images(
            base, cand, threshold=0.99, masks=[MaskRegion(10, 10, 30, 30)]
        )
        assert result.verdict == PASS

    def test_partial_mask_does_not_fully_hide_diff(self, tmp_path: Path):
        base = _solid(tmp_path / "base.png", (200, 100, 50))
        cand = _solid_with_patch(
            tmp_path / "cand.png",
            base=(200, 100, 50),
            patch=(0, 255, 0),
            patch_xywh=(40, 40, 60, 60),
        )
        result = compare_images(
            base, cand, threshold=0.99, masks=[MaskRegion(40, 40, 30, 30)]
        )
        assert result.verdict == CHANGE

    def test_out_of_bounds_mask_does_not_raise(self, tmp_path: Path):
        base = _solid(tmp_path / "base.png", (200, 100, 50))
        cand = _solid(tmp_path / "cand.png", (200, 100, 50))
        result = compare_images(
            base, cand, threshold=0.99, masks=[MaskRegion(500, 500, 100, 100)]
        )
        assert result.verdict == PASS
