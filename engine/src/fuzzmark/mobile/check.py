"""Run a MobileTest, render its report, and reduce it to a pass/fail gate.

Phase 8 CI entrypoint: composes `run_mobile_flow` + `render_report` and treats
any non-`pass` verdict (including `no-baseline`) as a failure. The
`run_mobile_flow` call goes through a module-level injection seam so tests
exercise the orchestrator without an iOS Simulator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..compare import DEFAULT_THRESHOLD, MaskRegion, PASS
from ..report import Report, render_report
from .driver import run_mobile_flow as _real_run_mobile_flow
from .flow import MobileRunResult, MobileTest


_run_mobile_flow = _real_run_mobile_flow


@dataclass(frozen=True)
class MobileCheckResult:
    """The outcome of `check_mobile_test`: the run, the report, and the gate."""

    run: MobileRunResult
    report: Report
    failing: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failing


def check_mobile_test(
    test: MobileTest,
    out_dir: str | Path,
    *,
    report_dir: str | Path,
    baselines_dir: str | Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    masks: dict[str, list[MaskRegion]] | None = None,
    launch_settle_seconds: float = 1.5,
    stabilize_status_bar: bool = True,
) -> MobileCheckResult:
    """Run `test`, render the HTML report, return the gate result.

    Args:
        test: A validated `MobileTest`.
        out_dir: Where per-capture PNGs land (see `run_mobile_flow`).
        report_dir: Where the static HTML report (and copied images) lands.
        baselines_dir: Approved-baselines directory. Captures with no matching
            baseline produce a `no-baseline` verdict and fail the gate.
        threshold: SSIM threshold for `render_report`.
        masks: Per-capture-name mask regions blanked before scoring.
        launch_settle_seconds: Passed to `run_mobile_flow`.
        stabilize_status_bar: Passed to `run_mobile_flow`.

    Returns:
        A `MobileCheckResult`. `passed` is True iff every report entry is
        `pass`. `failing` lists the names of non-pass captures in report order.
    """
    run = _run_mobile_flow(
        test,
        out_dir,
        launch_settle_seconds=launch_settle_seconds,
        stabilize_status_bar=stabilize_status_bar,
    )
    report = render_report(
        run.to_dict(),
        report_dir,
        baselines_dir=baselines_dir,
        threshold=threshold,
        masks=masks,
    )
    failing = tuple(e.name for e in report.entries if e.verdict != PASS)
    return MobileCheckResult(run=run, report=report, failing=failing)
