"""Structural diff: tell `layout-break` from `content-change` via bounding-box analysis.

Spec §5.7 step 4. Runs after SSIM has flagged a difference and the alignment
pass has not rescued it as a benign global shift. The question this module
answers is *what kind* of regression we are looking at:

- High structural match → the boxes are still in the same places, only the
  pixels inside them changed (text edit, color swap) → `content-change`.
- Low match → boxes moved, appeared, or disappeared → `layout-break`.

Block extraction is intentionally cheap: Canny edges, dilate to glue strokes
into the block that contains them, then `findContours` for axis-aligned bounds.
Good enough to separate "same boxes, different pixels" from "the boxes moved"
without dragging in a DOM tree.

Pure: numpy in, summary out. Importable without a browser.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Box:
    """Axis-aligned bounding box in image-pixel coordinates."""

    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return self.w * self.h

    def iou(self, other: "Box") -> float:
        ax2, ay2 = self.x + self.w, self.y + self.h
        bx2, by2 = other.x + other.w, other.y + other.h
        ix1 = max(self.x, other.x)
        iy1 = max(self.y, other.y)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class StructuralSummary:
    """Aggregate "did the layout survive?" diagnostic for one comparison.

    Carries the headline match score plus raw box counts so the report can
    show *what kind* of structural drift fired the verdict.
    """

    baseline_boxes: int
    candidate_boxes: int
    matched_boxes: int
    match_score: float

    def to_dict(self) -> dict:
        return asdict(self)


# Layout-intact cutoff. Above this the layout is treated as preserved and
# any remaining SSIM gap is content-only. Calibrated against the breakage
# fixtures: text/color changes land near 1.0; moves/adds/removes drop well
# below 0.7. 0.75 sits comfortably in that gap.
MATCH_THRESHOLD = 0.75
# IoU at which two boxes are accepted as the same block. Lower would let a
# shifted button "match" its old self and mask a real layout break.
MIN_BOX_IOU = 0.5
# Minimum block area, as a fraction of total image area. Filters out
# single-character noise and stray cursor edges that would otherwise wobble
# the structural score across captures of an unchanged page.
MIN_BOX_AREA_FRAC = 0.0005
# Edge-dilation kernel. Big enough to glue adjacent strokes (an input border
# plus its label) into one block; small enough not to merge separate fields.
DILATE_KERNEL = (15, 15)


def detect_blocks(image: np.ndarray) -> list[Box]:
    """Extract content-block bounding boxes via edge density + morphological grouping."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, DILATE_KERNEL)
    dilated = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    h, w = gray.shape[:2]
    min_area = int(MIN_BOX_AREA_FRAC * h * w)
    boxes: list[Box] = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw * bh < min_area:
            continue
        boxes.append(Box(x=int(x), y=int(y), w=int(bw), h=int(bh)))
    return boxes


def compare_structure(
    baseline: np.ndarray, candidate: np.ndarray
) -> StructuralSummary:
    """Diagnose how much of the baseline's block topology survives in the candidate.

    Score is the IoU-matched count over the larger of the two block sets,
    multiplied by per-unmatched penalties on both sides. Counting (not
    area-weighting) is what catches a single small element moving across the
    page: that block contributes 1/N to the score whether it is 10 px tall
    or 200, and the penalty term doubles when the move leaves a hole *and*
    creates a new candidate block. Pure adds and removes already drop the
    score via the imbalance in `max(...)`; the penalties stack on top of
    that without re-counting the same block.
    """
    baseline_boxes = detect_blocks(baseline)
    candidate_boxes = detect_blocks(candidate)

    if not baseline_boxes and not candidate_boxes:
        return StructuralSummary(0, 0, 0, 1.0)
    if not baseline_boxes or not candidate_boxes:
        return StructuralSummary(
            len(baseline_boxes), len(candidate_boxes), 0, 0.0
        )

    matched = 0
    used: set[int] = set()
    for b in baseline_boxes:
        best_iou = 0.0
        best_idx = -1
        for i, c in enumerate(candidate_boxes):
            if i in used:
                continue
            iou = b.iou(c)
            if iou > best_iou:
                best_iou = iou
                best_idx = i
        if best_iou >= MIN_BOX_IOU and best_idx >= 0:
            matched += 1
            used.add(best_idx)

    nb = len(baseline_boxes)
    nc = len(candidate_boxes)
    score = matched / max(nb, nc)
    unmatched_b = nb - matched
    unmatched_c = nc - len(used)
    score *= max(0.0, 1.0 - unmatched_b / nb)
    score *= max(0.0, 1.0 - unmatched_c / nc)

    return StructuralSummary(
        baseline_boxes=nb,
        candidate_boxes=nc,
        matched_boxes=matched,
        match_score=float(score),
    )


def is_layout_intact(
    summary: StructuralSummary, threshold: float = MATCH_THRESHOLD
) -> bool:
    return summary.match_score >= threshold
