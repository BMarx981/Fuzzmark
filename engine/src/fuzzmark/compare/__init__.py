"""Tiered image comparison: normalize, align, perceptual diff, structural diff, masks.

SSIM is the perceptual diff; the alignment pass (spec §5.7 step 2) rescues
small global pixel shifts as `size-shift`; the structural classifier
(spec §5.7 step 4) splits the remaining gap into `content-change` (layout
intact) and `layout-break` (blocks moved, appeared, or disappeared).
"""

from .align import Alignment, try_align_to_baseline
from .diff import DEFAULT_THRESHOLD, compare_images
from .masks import MaskRegion, apply_masks, clamp_region, parse_mask_spec
from .result import (
    CONTENT_CHANGE,
    LAYOUT_BREAK,
    PASS,
    SIZE_SHIFT,
    VERDICTS,
    CompareResult,
)
from .structure import (
    Box,
    StructuralSummary,
    compare_structure,
    detect_blocks,
    is_layout_intact,
)

__all__ = [
    "compare_images",
    "CompareResult",
    "DEFAULT_THRESHOLD",
    "PASS",
    "CONTENT_CHANGE",
    "LAYOUT_BREAK",
    "SIZE_SHIFT",
    "VERDICTS",
    "MaskRegion",
    "apply_masks",
    "clamp_region",
    "parse_mask_spec",
    "Alignment",
    "try_align_to_baseline",
    "Box",
    "StructuralSummary",
    "compare_structure",
    "detect_blocks",
    "is_layout_intact",
]
