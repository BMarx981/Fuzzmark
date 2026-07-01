"""Run a web Test, render its report, and reduce it to a pass/fail gate.

CI entrypoint: composes `driver.run_flow` + `report.render_report` and treats
any non-`pass` verdict (including `no-baseline`) as a failure. The `run_flow`
call goes through a module-level injection seam so tests exercise the
orchestrator without a browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .compare import DEFAULT_THRESHOLD, MaskRegion, PASS
from .driver import RunResult, Test, run_flow as _real_run_flow
from .report import Report, render_report


_run_flow = _real_run_flow


@dataclass(frozen=True)
class CheckResult:
    """The outcome of `check_test`: the run, the report, and the gate."""

    run: RunResult
    report: Report
    failing: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failing


def check_test(
    test: Test,
    out_dir: str | Path,
    *,
    report_dir: str | Path,
    baselines_dir: str | Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    masks: dict[str, list[MaskRegion]] | None = None,
    viewport: tuple[int, int] = (1280, 800),
    headless: bool = True,
    slow_mo_ms: int = 0,
    session: str | None = None,
) -> CheckResult:
    """Run `test`, render the HTML report, return the gate result.

    Args:
        test: A validated `Test`.
        out_dir: Where per-capture PNGs land (see `run_flow`).
        report_dir: Where the static HTML report (and copied images) lands.
        baselines_dir: Approved-baselines directory. Captures with no matching
            baseline produce a `no-baseline` verdict and fail the gate.
        threshold: SSIM threshold for `render_report`.
        masks: Per-capture-name mask regions blanked before scoring.
        viewport: Ignored when `test.viewports` is set; otherwise the size to
            render at.
        headless: Passed to `run_flow`.
        slow_mo_ms: Passed to `run_flow`.
        session: Playwright storage_state path; `test.session` still wins.

    Returns:
        A `CheckResult`. `passed` is True iff every report entry is `pass`.
        `failing` lists the names of non-pass captures in report order.
    """
    run = _run_flow(
        test,
        out_dir,
        viewport=viewport,
        headless=headless,
        slow_mo_ms=slow_mo_ms,
        session=session,
    )
    report = render_report(
        run.to_dict(),
        report_dir,
        baselines_dir=baselines_dir,
        threshold=threshold,
        masks=masks,
    )
    failing = tuple(e.name for e in report.entries if e.verdict != PASS)
    return CheckResult(run=run, report=report, failing=failing)
