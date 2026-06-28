"""SSIM-based image comparison: catch, not classify (MVP scope per spec §10.2).

SSIM runs on the BGR image with channel_axis=-1 so a color change to an
otherwise-identical region (e.g. a button background swap) registers as a real
difference. Grayscale SSIM would discard chroma and miss equiluminant swaps.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity

from .masks import MaskRegion, apply_masks
from .result import CHANGE, PASS, CompareResult


DEFAULT_THRESHOLD = 0.99


def _load_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"could not read image: {path}")
    return img


def _normalize_dims(baseline: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    if candidate.shape == baseline.shape:
        return candidate
    h, w = baseline.shape[:2]
    return cv2.resize(candidate, (w, h), interpolation=cv2.INTER_AREA)


def _write_heatmap(ssim_map: np.ndarray, out_path: Path) -> None:
    """Render the SSIM map as a hot colormap: bright = highly different."""
    inv = (1.0 - ssim_map) * 255.0
    inv_u8 = np.clip(inv, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(inv_u8, cv2.COLORMAP_HOT)
    cv2.imwrite(str(out_path), heat)


def compare_images(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    diff_path: str | Path | None = None,
    masks: list[MaskRegion] | None = None,
) -> CompareResult:
    """Compare a candidate screenshot against a baseline using SSIM.

    Args:
        baseline_path: Approved reference image.
        candidate_path: New capture under test.
        threshold: SSIM score at or above which the candidate is considered a pass.
        diff_path: Optional path to write a colormap heatmap visualizing the diff.
        masks: Optional axis-aligned regions blanked on both images before
            scoring. Use to exclude legitimately dynamic UI (clocks, ads,
            carousels) per spec §5.7.

    Returns:
        A `CompareResult` carrying the score, threshold, verdict, and (if requested)
        the heatmap path.
    """
    baseline_path = Path(baseline_path)
    candidate_path = Path(candidate_path)

    baseline = _load_bgr(baseline_path)
    candidate = _normalize_dims(baseline, _load_bgr(candidate_path))

    if masks:
        baseline = apply_masks(baseline, masks)
        candidate = apply_masks(candidate, masks)

    score, ssim_map = structural_similarity(
        baseline, candidate, channel_axis=-1, full=True
    )
    if ssim_map.ndim == 3:
        ssim_map = ssim_map.mean(axis=-1)

    written_diff: str | None = None
    if diff_path is not None:
        out = Path(diff_path)
        _write_heatmap(ssim_map, out)
        written_diff = str(out)

    verdict = PASS if score >= threshold else CHANGE
    return CompareResult(
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        score=float(score),
        threshold=float(threshold),
        verdict=verdict,
        diff_path=written_diff,
    )
