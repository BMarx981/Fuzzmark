"""Phase 8 Mobile DoD — the simulator counterpart to `test_mvp_dod.py`.

Same two contracts the web diff engine must meet, now applied end-to-end to
the mobile pipeline via `check_mobile_test` against Mobile Safari:

  1. Zero false positives across N captures of the same Safari frame —
     run, then re-run against the first run's captures as baselines, and the
     gate must pass. The status_bar override from Phase 8 step 4 plus the
     check orchestrator from step 5 are exactly what make this possible.
  2. The gate catches a deliberate change — re-run the *different* page
     against the same baselines and the gate must fail.

Live-sim only (gated by `--run-sim`); macOS-only.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.simulator

if sys.platform != "darwin":
    pytest.skip("iOS Simulator is macOS-only", allow_module_level=True)

from fuzzmark.mobile import (  # noqa: E402
    MobileTest,
    check_mobile_test,
    parse_mobile_test,
    simctl_available,
)


SAFARI_BUNDLE_ID = "com.apple.mobilesafari"
DOD_THRESHOLD = 0.999

# Spread the false-positive captures across enough wall-clock seconds that the
# live clock minute boundary would cross at least once if the status_bar
# override were silently disabled — the gate catches the regression instead of
# the test flaking on timing.
FALSE_POSITIVE_TRIALS = 5
FP_GAP_SECONDS = 3.0


@pytest.fixture(scope="module")
def _simctl_present() -> None:
    if not simctl_available():
        pytest.skip("`xcrun simctl` not available on this host")


def _safari_visit(url: str, capture_names: list[str], gap_seconds: float = 1.0) -> MobileTest:
    """Build a MobileTest that opens `url` in Safari and captures it `len(capture_names)` times."""
    flow: list[dict] = [
        {"kind": "launch"},
        {"kind": "openurl", "url": url},
        {"kind": "wait", "seconds": 3.0},
    ]
    for i, name in enumerate(capture_names):
        if i > 0:
            flow.append({"kind": "wait", "seconds": gap_seconds})
        flow.append({"kind": "capture", "name": name})
    flow.append({"kind": "terminate"})
    return parse_mobile_test(
        {"name": "safari-dod", "bundle_id": SAFARI_BUNDLE_ID, "flow": flow}
    )


def _approve_run_to_baselines(run, baselines_dir: Path) -> None:
    """Mirror `fuzzmark approve` — copy every capture into the baseline store."""
    viewport = run.viewport
    assert viewport, "run must have a viewport tag"
    dst_dir = baselines_dir / viewport
    dst_dir.mkdir(parents=True, exist_ok=True)
    for cap in run.captures:
        shutil.copyfile(cap.screenshot_path, dst_dir / f"{cap.name}.png")


def test_zero_false_positives_across_repeated_safari_captures(
    _simctl_present: None, tmp_path: Path
) -> None:
    """Run Safari → example.com, capture N times spaced out over wall-clock,
    approve the first run as baselines, re-run the identical flow, gate passes
    at the strict DoD threshold."""
    names = [f"trial-{i:02d}" for i in range(FALSE_POSITIVE_TRIALS)]
    test = _safari_visit("https://example.com", names, gap_seconds=FP_GAP_SECONDS)

    baselines = tmp_path / "baselines"
    baselines.mkdir()

    first = check_mobile_test(
        test,
        tmp_path / "run-1",
        report_dir=tmp_path / "report-1",
        baselines_dir=baselines,
        threshold=DOD_THRESHOLD,
    )
    # Empty baselines on the first run → every capture is no-baseline.
    assert first.passed is False
    assert {e.verdict for e in first.report.entries} == {"no-baseline"}

    _approve_run_to_baselines(first.run, baselines)

    second = check_mobile_test(
        test,
        tmp_path / "run-2",
        report_dir=tmp_path / "report-2",
        baselines_dir=baselines,
        threshold=DOD_THRESHOLD,
    )
    assert second.passed is True, (
        f"expected zero false positives at threshold {DOD_THRESHOLD}; "
        f"failing={second.failing} entries="
        f"{[(e.name, e.verdict, e.score) for e in second.report.entries]}"
    )


def test_sim_check_catches_a_deliberately_changed_page(
    _simctl_present: None, tmp_path: Path
) -> None:
    """Baseline an example.com frame, then run a flow that loads example.org —
    sim-check must fail (catch, not classify per spec §10.2)."""
    base_test = _safari_visit("https://example.com", ["landing"])
    breakage_test = _safari_visit("https://example.org", ["landing"])

    baselines = tmp_path / "baselines"
    baselines.mkdir()

    baseline_run = check_mobile_test(
        base_test,
        tmp_path / "run-baseline",
        report_dir=tmp_path / "report-baseline",
        baselines_dir=baselines,
        threshold=DOD_THRESHOLD,
    )
    assert baseline_run.passed is False  # no-baseline initially
    _approve_run_to_baselines(baseline_run.run, baselines)

    breakage = check_mobile_test(
        breakage_test,
        tmp_path / "run-breakage",
        report_dir=tmp_path / "report-breakage",
        baselines_dir=baselines,
        threshold=DOD_THRESHOLD,
    )
    assert breakage.passed is False, (
        "expected the gate to catch a page swap; "
        f"entries={[(e.name, e.verdict, e.score) for e in breakage.report.entries]}"
    )
    # Single entry, and it must be a non-pass non-no-baseline verdict (the
    # baseline exists from the approve step) — that's the real "catch" signal.
    assert len(breakage.report.entries) == 1
    entry = breakage.report.entries[0]
    assert entry.verdict not in {"pass", "no-baseline"}, (
        f"expected a change verdict; got {entry.verdict!r} (score {entry.score})"
    )
