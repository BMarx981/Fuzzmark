"""Data models for the baseline-approval flow.

Pure: no I/O, no browser. Importable from anywhere.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


NEW = "new"
UPDATED = "updated"
ACTIONS = (NEW, UPDATED)


@dataclass(frozen=True)
class ApprovalItem:
    """One capture that would be promoted to a baseline."""

    capture_name: str
    source_path: str
    target_path: str
    action: str  # NEW or UPDATED

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SkippedApproval:
    """A capture excluded from the plan, with the reason."""

    capture_name: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApprovalPlan:
    """The list of approvals that would be performed, plus what was skipped."""

    test_name: str
    baselines_dir: str
    approvals: list[ApprovalItem] = field(default_factory=list)
    skipped: list[SkippedApproval] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "baselines_dir": self.baselines_dir,
            "approval_count": len(self.approvals),
            "skipped_count": len(self.skipped),
            "approvals": [a.to_dict() for a in self.approvals],
            "skipped": [s.to_dict() for s in self.skipped],
        }


@dataclass
class ApprovalResult:
    """The outcome of executing an `ApprovalPlan`."""

    test_name: str
    baselines_dir: str
    written: list[ApprovalItem] = field(default_factory=list)
    skipped: list[SkippedApproval] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "baselines_dir": self.baselines_dir,
            "dry_run": self.dry_run,
            "written_count": len(self.written),
            "skipped_count": len(self.skipped),
            "written": [a.to_dict() for a in self.written],
            "skipped": [s.to_dict() for s in self.skipped],
        }
