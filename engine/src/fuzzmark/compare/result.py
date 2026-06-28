"""Data models for image comparison output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


PASS = "pass"
CHANGE = "change"
SIZE_SHIFT = "size-shift"

VERDICTS = (PASS, SIZE_SHIFT, CHANGE)


@dataclass(frozen=True)
class CompareResult:
    """Outcome of comparing a candidate capture against a baseline.

    `score` is always the pre-alignment SSIM between the (masked) input images,
    so the user sees how visually different the raw captures were. When the
    alignment pass rescues an otherwise-failing comparison, `verdict` flips to
    `size-shift` and `alignment` carries the fitted transform — including the
    post-warp SSIM that justified the rescue.
    """

    baseline_path: str
    candidate_path: str
    score: float
    threshold: float
    verdict: str
    diff_path: Optional[str] = None
    alignment: Optional[dict] = field(default=None)

    def to_dict(self) -> dict:
        return asdict(self)
