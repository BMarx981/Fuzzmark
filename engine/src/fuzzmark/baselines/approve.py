"""Build and execute approval plans against a `RunResult`.

The flow is two-phased so a caller can review what would change before any
files move:

1. `plan_approval` walks a run-result dict, applies the optional
   `capture_names` filter, and returns an `ApprovalPlan` listing each capture
   that would become a new or updated baseline.
2. `apply_approval` copies the source captures to their baseline targets and
   returns the `ApprovalResult`. `dry_run=True` skips all I/O.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from .models import (
    NEW,
    UPDATED,
    ApprovalItem,
    ApprovalPlan,
    ApprovalResult,
    SkippedApproval,
)
from .store import baseline_path, existing_baselines


def plan_approval(
    run_result: dict,
    baselines_dir: str | Path,
    *,
    capture_names: Iterable[str] | None = None,
) -> ApprovalPlan:
    """Build an `ApprovalPlan` from a run-result dict.

    Args:
        run_result: A `RunResult.to_dict()` shape — `test_name` and `captures`.
        baselines_dir: Destination directory for approved baselines.
        capture_names: Optional whitelist; when supplied, only those captures
            are approved. Names not present in `captures` show up under
            `skipped` with reason `unknown`.
    """
    base_dir = Path(baselines_dir)
    captures = run_result.get("captures", []) or []
    have = existing_baselines(base_dir)

    filter_set = set(capture_names) if capture_names is not None else None
    filtered_names: set[str] = set()

    plan = ApprovalPlan(
        test_name=run_result.get("test_name", "") or "",
        baselines_dir=str(base_dir),
    )

    for capture in captures:
        name = capture.get("name")
        if not name:
            continue
        if filter_set is not None and name not in filter_set:
            plan.skipped.append(SkippedApproval(capture_name=name, reason="not-selected"))
            continue
        filtered_names.add(name)

        src = capture.get("screenshot_path")
        if not src:
            plan.skipped.append(SkippedApproval(capture_name=name, reason="missing-source"))
            continue
        if not Path(src).is_file():
            plan.skipped.append(SkippedApproval(capture_name=name, reason="source-not-found"))
            continue

        target = baseline_path(base_dir, name)
        action = UPDATED if name in have else NEW
        plan.approvals.append(
            ApprovalItem(
                capture_name=name,
                source_path=str(src),
                target_path=str(target),
                action=action,
            )
        )

    if filter_set is not None:
        for unknown in sorted(filter_set - filtered_names):
            plan.skipped.append(SkippedApproval(capture_name=unknown, reason="unknown"))

    return plan


def apply_approval(plan: ApprovalPlan, *, dry_run: bool = False) -> ApprovalResult:
    """Execute `plan`, copying captures to their baseline targets.

    `dry_run=True` returns the same `written` list without touching disk so a
    caller can preview the operation safely.
    """
    base_dir = Path(plan.baselines_dir)
    if not dry_run:
        base_dir.mkdir(parents=True, exist_ok=True)

    written: list[ApprovalItem] = []
    for item in plan.approvals:
        target = Path(item.target_path)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item.source_path, target)
        written.append(item)

    return ApprovalResult(
        test_name=plan.test_name,
        baselines_dir=str(base_dir),
        written=written,
        skipped=list(plan.skipped),
        dry_run=dry_run,
    )
