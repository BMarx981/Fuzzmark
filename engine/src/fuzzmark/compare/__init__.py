"""Tiered image comparison: normalize, align, perceptual diff, masks.

SSIM is the perceptual diff; the alignment pass (spec §5.7 step 2) rescues
small global pixel shifts as `size-shift` rather than `change`. Structural
diff and the smart layout-break classification are later Phase 3 work.
"""

from .align import Alignment, try_align_to_baseline
from .diff import DEFAULT_THRESHOLD, compare_images
from .masks import MaskRegion, apply_masks, clamp_region, parse_mask_spec
from .result import CHANGE, PASS, SIZE_SHIFT, VERDICTS, CompareResult

__all__ = [
    "compare_images",
    "CompareResult",
    "DEFAULT_THRESHOLD",
    "PASS",
    "CHANGE",
    "SIZE_SHIFT",
    "VERDICTS",
    "MaskRegion",
    "apply_masks",
    "clamp_region",
    "parse_mask_spec",
    "Alignment",
    "try_align_to_baseline",
]
