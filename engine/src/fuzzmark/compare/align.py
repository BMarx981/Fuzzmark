"""Feature-match alignment pass: distinguish a benign global shift from a content change.

Spec §5.7 step 2: if a small translation, uniform scale, or sub-degree rotation
brings the candidate into register with the baseline, the verdict is
`size-shift`, not `change`. This catches the very common false positive where a
font-metric change, scrollbar gutter, or a one-pixel padding tweak shifts the
whole layout by a few pixels without anything actually changing on the page.

The fit is intentionally conservative — narrow gates on rotation, scale, and
RANSAC inlier ratio — so a real content regression that happens to admit a
loose feature match still reads as `change`.

Pure: numpy in, numpy out. Importable without a browser.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Alignment:
    """The partial-affine transform fit between baseline and candidate.

    Carries only the four interpretable parameters plus the RANSAC inlier
    ratio — enough to decide whether the fit qualifies as a small global shift
    and to surface "what moved" in the report.
    """

    tx: float
    ty: float
    rotation_deg: float
    scale: float
    inlier_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


# Gates for "a small global shift, not a layout rewrite."
# Above 2° or 10% scale, a screenshot diff almost never represents benign drift.
MAX_ROTATION_DEG = 2.0
MAX_SCALE_DELTA = 0.10
MIN_INLIER_RATIO = 0.30
# Floor on inlier count so a six-feature fluke can't squeak past the ratio gate.
MIN_INLIERS = 12
# ORB candidate budget. 2000 is comfortably above the inlier floor on
# screenshot-sized images without making the fit dominate runtime.
ORB_FEATURES = 2000


def try_align_to_baseline(
    baseline: np.ndarray, candidate: np.ndarray
) -> tuple[np.ndarray, Alignment] | None:
    """Warp candidate into baseline coordinate space iff a small global shift fits.

    Returns `(warped, alignment)` when the ORB+RANSAC fit is well-conditioned
    *and* clears the small-shift gates. Returns `None` when there are too few
    stable features, the fit fails, or the transform is too large to call
    benign — in all those cases the caller should keep the original
    `change` verdict.
    """
    alignment, matrix = _fit_partial_affine(baseline, candidate)
    if alignment is None or matrix is None:
        return None
    if not _is_small_global_shift(alignment):
        return None
    h, w = baseline.shape[:2]
    warped = cv2.warpAffine(
        candidate,
        matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return warped, alignment


def _fit_partial_affine(
    baseline: np.ndarray, candidate: np.ndarray
) -> tuple[Alignment | None, np.ndarray | None]:
    """ORB-feature RANSAC fit constrained to translation, rotation, uniform scale."""
    bg = cv2.cvtColor(baseline, cv2.COLOR_BGR2GRAY)
    cg = cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
    kp_b, des_b = orb.detectAndCompute(bg, None)
    kp_c, des_c = orb.detectAndCompute(cg, None)
    if des_b is None or des_c is None:
        return None, None
    if len(kp_b) < MIN_INLIERS or len(kp_c) < MIN_INLIERS:
        return None, None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des_b, des_c)
    if len(matches) < MIN_INLIERS:
        return None, None

    # estimateAffinePartial2D returns M such that dst ≈ M · src, so
    # passing (candidate_pts, baseline_pts) yields a candidate→baseline warp.
    src = np.float32([kp_c[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([kp_b[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    matrix, inliers = cv2.estimateAffinePartial2D(
        src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0
    )
    if matrix is None or inliers is None:
        return None, None

    inlier_count = int(inliers.sum())
    if inlier_count < MIN_INLIERS:
        return None, None

    scale = math.sqrt(matrix[0, 0] ** 2 + matrix[0, 1] ** 2)
    rotation_rad = math.atan2(matrix[1, 0], matrix[0, 0])
    alignment = Alignment(
        tx=float(matrix[0, 2]),
        ty=float(matrix[1, 2]),
        rotation_deg=math.degrees(rotation_rad),
        scale=float(scale),
        inlier_ratio=inlier_count / max(len(matches), 1),
    )
    return alignment, matrix


def _is_small_global_shift(alignment: Alignment) -> bool:
    return (
        abs(alignment.rotation_deg) <= MAX_ROTATION_DEG
        and abs(alignment.scale - 1.0) <= MAX_SCALE_DELTA
        and alignment.inlier_ratio >= MIN_INLIER_RATIO
    )
