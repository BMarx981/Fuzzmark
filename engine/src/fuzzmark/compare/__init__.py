"""Tiered image comparison: normalize, align, perceptual diff, structural diff, masks.

MVP: single-threshold SSIM verdict (pass / change). The align / structural / masks
tiers from spec §5.7 come later.
"""

from .diff import DEFAULT_THRESHOLD, compare_images
from .result import CHANGE, MVP_VERDICTS, PASS, CompareResult

__all__ = [
    "compare_images",
    "CompareResult",
    "DEFAULT_THRESHOLD",
    "PASS",
    "CHANGE",
    "MVP_VERDICTS",
]
