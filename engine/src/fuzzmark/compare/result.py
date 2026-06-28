"""Data models for image comparison output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


PASS = "pass"
SIZE_SHIFT = "size-shift"
CONTENT_CHANGE = "content-change"
LAYOUT_BREAK = "layout-break"

VERDICTS = (PASS, SIZE_SHIFT, CONTENT_CHANGE, LAYOUT_BREAK)


@dataclass(frozen=True)
class CompareResult:
    """Outcome of comparing a candidate capture against a baseline.

    `score` is always the pre-alignment SSIM between the (masked) input images,
    so the user sees how visually different the raw captures were. When the
    alignment pass rescues an otherwise-failing comparison, `verdict` flips to
    `size-shift` and `alignment` carries the fitted transform. When alignment
    does not rescue, the structural classifier picks between `content-change`
    (layout intact, only pixels inside the boxes moved) and `layout-break`
    (boxes themselves moved, appeared, or disappeared); `structure` carries
    that diagnostic in either case.
    """

    baseline_path: str
    candidate_path: str
    score: float
    threshold: float
    verdict: str
    diff_path: Optional[str] = None
    alignment: Optional[dict] = field(default=None)
    structure: Optional[dict] = field(default=None)

    def to_dict(self) -> dict:
        return asdict(self)
