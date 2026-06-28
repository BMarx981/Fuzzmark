"""Data models for image comparison output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


PASS = "pass"
CHANGE = "change"

MVP_VERDICTS = (PASS, CHANGE)


@dataclass(frozen=True)
class CompareResult:
    """Outcome of comparing a candidate capture against a baseline.

    MVP scope: a single similarity `score` against a single `threshold` yields
    `pass` / `change`. The richer classifications in spec §5.7 are Phase 3.
    """

    baseline_path: str
    candidate_path: str
    score: float
    threshold: float
    verdict: str
    diff_path: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
