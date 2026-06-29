"""Live-sim test for `mobile.check.check_mobile_test` against Mobile Safari.

Verifies the gate's pass/fail semantics end-to-end on a real iOS Simulator:

  1. First run against an empty baselines dir → every capture is `no-baseline`
     and the gate fails.
  2. Copy the captures into the baselines dir (mirrors `fuzzmark approve`),
     re-run → every capture matches → gate passes.

Two-step deterministic match is exactly what Phase 8 step 4's status-bar
override unlocks; without it consecutive Safari frames would drift on the live
clock and fail the second run.
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
    check_mobile_test,
    parse_mobile_test,
    simctl_available,
)


SAFARI_BUNDLE_ID = "com.apple.mobilesafari"


@pytest.fixture(scope="module")
def _simctl_present() -> None:
    if not simctl_available():
        pytest.skip("`xcrun simctl` not available on this host")


def _safari_test():
    return parse_mobile_test(
        {
            "name": "safari-check",
            "bundle_id": SAFARI_BUNDLE_ID,
            "flow": [
                {"kind": "launch"},
                {"kind": "wait", "seconds": 1.0},
                {"kind": "capture", "name": "launched"},
                {"kind": "terminate"},
            ],
        }
    )


def test_sim_check_fails_with_no_baselines_then_passes_after_approval(
    _simctl_present: None, tmp_path: Path
) -> None:
    out_first = tmp_path / "run-1"
    baselines = tmp_path / "baselines"
    baselines.mkdir()

    first = check_mobile_test(
        _safari_test(),
        out_first,
        report_dir=tmp_path / "report-1",
        baselines_dir=baselines,
    )
    assert first.passed is False
    assert set(first.failing) == {"launched"}
    assert {e.verdict for e in first.report.entries} == {"no-baseline"}

    # Approve: copy the captures into the baselines dir under their viewport.
    viewport = first.run.viewport
    assert viewport
    src = Path(first.run.captures[0].screenshot_path)
    dst_dir = baselines / viewport
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst_dir / "launched.png")

    out_second = tmp_path / "run-2"
    second = check_mobile_test(
        _safari_test(),
        out_second,
        report_dir=tmp_path / "report-2",
        baselines_dir=baselines,
    )
    assert second.passed is True, (
        f"expected gate to pass after approval; failing={second.failing} "
        f"entries={[(e.name, e.verdict, e.score) for e in second.report.entries]}"
    )
