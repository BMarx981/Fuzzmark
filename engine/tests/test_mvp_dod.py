"""MVP Definition-of-Done gates per spec §10.2 and CLAUDE.md.

Two contracts the diff engine must meet to ship the MVP:

  1. Zero false positives across 20 identical captures of an unchanged page.
  2. 100% catch on the deliberate-breakage fixture set.

Both gates use a single tunable threshold — the spec mandates that pattern.
This fixture set (a centered card on a mostly-empty 1280x800 viewport)
empirically separates stable (score ~= 1.000000) from changed (scores 0.91
to 0.998) at threshold 0.999. Different projects pick different thresholds;
the engine's job is to make that one knob sufficient. If a future fixture
slips past, the right move is the alignment/structural tiers (Phase 3), not
per-fixture tuning.

The false-positive gate runs all 21 captures in a single Playwright session
via the flow runner so the gate stays under ~15s.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.capture import capture_page
from fuzzmark.compare import CHANGE, PASS, compare_images
from fuzzmark.driver import CAPTURE, VISIT, FlowStep, Test, run_flow


DOD_THRESHOLD = 0.999

pytestmark = pytest.mark.browser


FALSE_POSITIVE_TRIALS = 20

_BREAKAGE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "breakage"

BREAKAGE_FIXTURES = [
    "text-change.html",
    "color-change.html",
    "moved-element.html",
    "added-element.html",
    "removed-element.html",
]


def test_zero_false_positives_across_20_identical_captures(
    tmp_path: Path, fixture_form_url: str
) -> None:
    flow = [FlowStep(kind=VISIT, url=fixture_form_url)] + [
        FlowStep(kind=CAPTURE, name=f"trial-{i:02d}")
        for i in range(FALSE_POSITIVE_TRIALS + 1)
    ]
    result = run_flow(Test(name="dod-false-positive", flow=flow), tmp_path)
    baseline = result.captures[0].screenshot_path

    failures: list[tuple[str, float]] = []
    for capture in result.captures[1:]:
        cmp = compare_images(baseline, capture.screenshot_path, threshold=DOD_THRESHOLD)
        if cmp.verdict != PASS:
            failures.append((capture.name, cmp.score))

    assert failures == [], (
        f"{len(failures)}/{FALSE_POSITIVE_TRIALS} identical captures failed "
        f"at threshold {DOD_THRESHOLD}: {failures}"
    )


@pytest.fixture(scope="module")
def baseline_capture(tmp_path_factory, fixture_form_url: str) -> Path:
    out = tmp_path_factory.mktemp("dod-baseline") / "baseline.png"
    capture_page(fixture_form_url, out)
    return out


@pytest.mark.parametrize("filename", BREAKAGE_FIXTURES)
def test_breakage_fixture_is_caught(
    filename: str, tmp_path: Path, baseline_capture: Path
) -> None:
    url = (_BREAKAGE_DIR / filename).as_uri()
    candidate = tmp_path / f"{filename}.png"
    capture_page(url, candidate)

    result = compare_images(baseline_capture, candidate, threshold=DOD_THRESHOLD)
    assert result.verdict == CHANGE, (
        f"{filename}: expected 'change' at threshold {DOD_THRESHOLD}, "
        f"got {result.verdict!r} (score {result.score:.6f})"
    )
