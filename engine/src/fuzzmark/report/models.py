"""Data models for a rendered run report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from ..compare import CompareResult


NO_BASELINE = "no-baseline"


@dataclass(frozen=True)
class ReportEntry:
    """One row in the report: a capture, its baseline status, and the comparison."""

    name: str
    step_index: int
    capture_path: str
    verdict: str
    baseline_path: Optional[str] = None
    diff_path: Optional[str] = None
    score: Optional[float] = None
    threshold: Optional[float] = None

    @classmethod
    def from_compare(
        cls, *, name: str, step_index: int, capture_path: str, result: CompareResult
    ) -> "ReportEntry":
        return cls(
            name=name,
            step_index=step_index,
            capture_path=capture_path,
            verdict=result.verdict,
            baseline_path=result.baseline_path,
            diff_path=result.diff_path,
            score=result.score,
            threshold=result.threshold,
        )

    @classmethod
    def no_baseline(cls, *, name: str, step_index: int, capture_path: str) -> "ReportEntry":
        return cls(
            name=name,
            step_index=step_index,
            capture_path=capture_path,
            verdict=NO_BASELINE,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    """The aggregate of a single run: per-capture entries + run-wide errors."""

    test_name: str
    entries: list[ReportEntry] = field(default_factory=list)
    console_errors: list[dict] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[dict] = field(default_factory=list)
    output_dir: str = ""
    index_path: str = ""

    @property
    def verdict_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.verdict] = counts.get(e.verdict, 0) + 1
        return counts

    @property
    def has_errors(self) -> bool:
        return bool(self.console_errors or self.page_errors or self.failed_requests)

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "entries": [e.to_dict() for e in self.entries],
            "console_errors": list(self.console_errors),
            "page_errors": list(self.page_errors),
            "failed_requests": list(self.failed_requests),
            "verdict_counts": self.verdict_counts,
            "output_dir": self.output_dir,
            "index_path": self.index_path,
        }
