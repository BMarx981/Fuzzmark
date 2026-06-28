"""End-to-end structural-classification check on the breakage fixtures.

The MVP DoD gate (`test_mvp_dod.py`) only asserts "non-pass" on the breakage
set — catch, not classify. With the structural classifier landed (spec §5.7
step 4) the engine now picks `content-change` vs `layout-break`; this file
pins which fixture goes which way so a regression in block detection or
scoring is caught quickly. Browser-gated because the fixtures are HTML.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.capture import capture_page
from fuzzmark.compare import CONTENT_CHANGE, LAYOUT_BREAK, compare_images


pytestmark = pytest.mark.browser


_BREAKAGE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "breakage"


# (fixture filename, expected structural verdict). Splits along the line the
# spec draws: text/color edits leave the boxes alone (content-change); moves,
# adds, and removes shift the box topology (layout-break).
STRUCTURAL_CASES = [
    ("text-change.html", CONTENT_CHANGE),
    ("color-change.html", CONTENT_CHANGE),
    ("moved-element.html", LAYOUT_BREAK),
    ("added-element.html", LAYOUT_BREAK),
    ("removed-element.html", LAYOUT_BREAK),
]


@pytest.fixture(scope="module")
def baseline_capture(tmp_path_factory, fixture_form_url: str) -> Path:
    out = tmp_path_factory.mktemp("structural-baseline") / "baseline.png"
    capture_page(fixture_form_url, out)
    return out


@pytest.mark.parametrize("filename,expected", STRUCTURAL_CASES)
def test_breakage_fixture_structural_verdict(
    filename: str, expected: str, tmp_path: Path, baseline_capture: Path
) -> None:
    url = (_BREAKAGE_DIR / filename).as_uri()
    candidate = tmp_path / f"{filename}.png"
    capture_page(url, candidate)

    result = compare_images(baseline_capture, candidate, threshold=0.999)
    assert result.verdict == expected, (
        f"{filename}: expected {expected!r}, got {result.verdict!r} "
        f"(SSIM {result.score:.4f}, structure {result.structure})"
    )
    assert result.structure is not None
