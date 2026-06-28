"""Browser-driven tests for the driver/flow runner.

Skipped unless `pytest --run-browser` is passed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.driver import (
    CAPTURE,
    FILL,
    INTERACT,
    SUBMIT,
    VISIT,
    FlowStep,
    Test,
    Viewport,
    run_flow,
)

pytestmark = pytest.mark.browser


def _flow_fixture(url: str) -> Test:
    return Test(
        name="fill-and-submit",
        flow=[
            FlowStep(kind=VISIT, url=url),
            FlowStep(kind=CAPTURE, name="before-fill"),
            FlowStep(kind=FILL, selector="#email", value="user@example.com"),
            FlowStep(kind=FILL, selector="input[name='fullname']", value="Ada"),
            FlowStep(kind=FILL, selector="input[name='zip']", value="19711"),
            FlowStep(kind=FILL, selector="input[name='age']", value="30"),
            FlowStep(
                kind=INTERACT,
                selector="#state",
                action="select_option",
                value="DE",
            ),
            FlowStep(kind=FILL, selector="#msg", value="hello"),
            FlowStep(kind=CAPTURE, name="after-fill"),
        ],
    )


def test_run_writes_one_screenshot_per_capture(
    tmp_path: Path, fixture_form_url: str
) -> None:
    out = tmp_path / "captures"
    result = run_flow(_flow_fixture(fixture_form_url), out)

    assert [c.name for c in result.captures] == ["before-fill", "after-fill"]
    for c in result.captures:
        path = Path(c.screenshot_path)
        assert path.exists()
        assert path.stat().st_size > 0
        assert path.parent == out


def test_run_collects_no_errors_on_clean_fixture(
    tmp_path: Path, fixture_form_url: str
) -> None:
    result = run_flow(_flow_fixture(fixture_form_url), tmp_path / "captures")
    assert result.has_errors is False
    assert result.console_errors == []
    assert result.page_errors == []


def test_filled_state_visibly_differs_from_blank_state(
    tmp_path: Path, fixture_form_url: str
) -> None:
    """Fills must change rendered pixels — proves the fill steps actually landed."""
    out = tmp_path / "captures"
    result = run_flow(_flow_fixture(fixture_form_url), out)
    before = next(c for c in result.captures if c.name == "before-fill")
    after = next(c for c in result.captures if c.name == "after-fill")

    assert Path(before.screenshot_path).read_bytes() != Path(after.screenshot_path).read_bytes()


def test_run_returns_test_name(tmp_path: Path, fixture_form_url: str) -> None:
    result = run_flow(_flow_fixture(fixture_form_url), tmp_path / "captures")
    assert result.test_name == "fill-and-submit"


def test_selector_masks_resolve_to_bounding_boxes(
    tmp_path: Path, fixture_form_url: str
) -> None:
    """A `mask_selectors` entry on a capture step becomes a MaskRegion on the artifact."""
    flow = Test(
        name="masked-capture",
        flow=[
            FlowStep(kind=VISIT, url=fixture_form_url),
            FlowStep(
                kind=CAPTURE,
                name="snap",
                mask_selectors=("h1", "#email"),
            ),
        ],
    )
    result = run_flow(flow, tmp_path / "captures")
    [art] = result.captures
    sources = [m.source for m in art.masks]
    assert "h1" in sources
    assert "#email" in sources
    for m in art.masks:
        assert m.width > 0 and m.height > 0
        assert m.x >= 0 and m.y >= 0


def test_missing_selector_masks_are_silently_skipped(
    tmp_path: Path, fixture_form_url: str
) -> None:
    flow = Test(
        name="missing-selector",
        flow=[
            FlowStep(kind=VISIT, url=fixture_form_url),
            FlowStep(
                kind=CAPTURE,
                name="snap",
                mask_selectors=("#does-not-exist",),
            ),
        ],
    )
    result = run_flow(flow, tmp_path / "captures")
    assert result.captures[0].masks == ()


def test_submit_does_not_raise_on_form_without_handler(
    tmp_path: Path, fixture_form_url: str
) -> None:
    """The fixture form has no action; submit shouldn't hang or error."""
    flow = Test(
        name="submit-only",
        flow=[
            FlowStep(kind=VISIT, url=fixture_form_url),
            FlowStep(kind=FILL, selector="#email", value="a@b.c"),
            FlowStep(kind=FILL, selector="input[name='zip']", value="12345"),
            FlowStep(kind=SUBMIT, selector="button[type='submit']"),
            FlowStep(kind=CAPTURE, name="after-submit"),
        ],
    )
    result = run_flow(flow, tmp_path / "captures")
    assert len(result.captures) == 1


def test_viewport_matrix_writes_one_capture_per_viewport(
    tmp_path: Path, fixture_form_url: str
) -> None:
    """A test with two viewports runs the flow twice and tags each capture."""
    flow = Test(
        name="matrix",
        viewports=(
            Viewport(name="desktop", width=1280, height=800),
            Viewport(name="mobile", width=390, height=844),
        ),
        flow=[
            FlowStep(kind=VISIT, url=fixture_form_url),
            FlowStep(kind=CAPTURE, name="home"),
        ],
    )
    out = tmp_path / "captures"
    result = run_flow(flow, out)

    by_vp = {(c.viewport, c.name) for c in result.captures}
    assert by_vp == {("desktop", "home"), ("mobile", "home")}
    desktop = next(c for c in result.captures if c.viewport == "desktop")
    mobile = next(c for c in result.captures if c.viewport == "mobile")
    assert Path(desktop.screenshot_path).parent == out / "desktop"
    assert Path(mobile.screenshot_path).parent == out / "mobile"
    # Different viewport widths must yield different pixel content.
    assert (
        Path(desktop.screenshot_path).read_bytes()
        != Path(mobile.screenshot_path).read_bytes()
    )
