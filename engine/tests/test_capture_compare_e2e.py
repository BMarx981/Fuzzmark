"""End-to-end check: capture + compare on the static fixture.

The MVP diff DoD demands zero false positives across repeated identical captures.
This is a coarse, single-fixture proof; the full 20-trial gate belongs in a CI
suite, not the unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.capture import capture_page
from fuzzmark.compare import PASS, compare_images

pytestmark = pytest.mark.browser


def test_two_identical_captures_compare_pass(
    tmp_path: Path, fixture_form_url: str
) -> None:
    baseline = tmp_path / "baseline.png"
    candidate = tmp_path / "candidate.png"
    capture_page(fixture_form_url, baseline)
    capture_page(fixture_form_url, candidate)

    result = compare_images(baseline, candidate)
    assert result.verdict == PASS
    assert result.score >= 0.99
