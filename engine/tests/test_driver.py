"""Pure-Python tests for the Test JSON loader and validator.

No browser. Exercises every validation rule the runner relies on so the runner
itself can trust its inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fuzzmark.compare import MaskRegion
from fuzzmark.driver import (
    CAPTURE,
    FILL,
    INTERACT,
    SUBMIT,
    VISIT,
    FlowStep,
    Test,
    Viewport,
    load_test,
    parse_test,
)


def _minimal_valid() -> dict:
    return {
        "name": "demo",
        "flow": [
            {"kind": "visit", "url": "about:blank"},
            {"kind": "capture", "name": "shot"},
        ],
    }


class TestParseHappyPath:
    def test_returns_test_with_steps(self):
        test = parse_test(_minimal_valid())
        assert test.name == "demo"
        assert [s.kind for s in test.flow] == [VISIT, CAPTURE]

    def test_round_trip_through_to_dict(self):
        test = parse_test(_minimal_valid())
        assert parse_test(test.to_dict()).to_dict() == test.to_dict()

    def test_load_from_disk(self, tmp_path: Path):
        p = tmp_path / "t.json"
        p.write_text(json.dumps(_minimal_valid()), encoding="utf-8")
        test = load_test(p)
        assert test.name == "demo"


class TestTopLevel:
    def test_name_required(self):
        raw = _minimal_valid()
        raw.pop("name")
        with pytest.raises(ValueError, match="name"):
            parse_test(raw)

    def test_name_must_be_non_empty(self):
        raw = _minimal_valid()
        raw["name"] = "   "
        with pytest.raises(ValueError, match="name"):
            parse_test(raw)

    def test_flow_required_and_non_empty(self):
        with pytest.raises(ValueError, match="flow"):
            parse_test({"name": "x", "flow": []})

    def test_root_must_be_object(self):
        with pytest.raises(ValueError):
            parse_test([])  # type: ignore[arg-type]


class TestFlowShape:
    def test_must_start_with_visit(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "capture", "name": "c"},
                {"kind": "visit", "url": "about:blank"},
            ],
        }
        with pytest.raises(ValueError, match="visit"):
            parse_test(raw)

    def test_must_contain_capture(self):
        raw = {"name": "x", "flow": [{"kind": "visit", "url": "about:blank"}]}
        with pytest.raises(ValueError, match="capture"):
            parse_test(raw)

    def test_capture_names_must_be_unique(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "capture", "name": "a"},
                {"kind": "capture", "name": "a"},
            ],
        }
        with pytest.raises(ValueError, match="unique"):
            parse_test(raw)


class TestStepValidation:
    def test_unknown_kind_raises(self):
        raw = {"name": "x", "flow": [{"kind": "nope"}]}
        with pytest.raises(ValueError, match="unknown kind"):
            parse_test(raw)

    def test_fill_requires_selector_and_value(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "fill", "selector": "#a"},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="value"):
            parse_test(raw)

    def test_interact_requires_selector_and_action(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "interact", "selector": "#a"},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="action"):
            parse_test(raw)

    def test_unknown_interact_action_raises(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "interact", "selector": "#a", "action": "kick"},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="unknown action"):
            parse_test(raw)

    def test_select_option_requires_value(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "interact", "selector": "#a", "action": "select_option"},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="select_option"):
            parse_test(raw)

    def test_submit_requires_selector(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "submit"},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="selector"):
            parse_test(raw)

    def test_visit_requires_url(self):
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit"},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="url"):
            parse_test(raw)


class TestFlowStepSerialization:
    def test_to_dict_drops_none_fields(self):
        step = FlowStep(kind=VISIT, url="about:blank")
        assert step.to_dict() == {"kind": "visit", "url": "about:blank"}

    def test_capture_includes_full_page_only_when_false(self):
        on = FlowStep(kind=CAPTURE, name="a")
        off = FlowStep(kind=CAPTURE, name="b", full_page=False)
        assert "full_page" not in on.to_dict()
        assert off.to_dict()["full_page"] is False

    def test_fill_round_trip(self):
        step = FlowStep(kind=FILL, selector="#email", value="x@y.z")
        assert step.to_dict() == {
            "kind": "fill",
            "selector": "#email",
            "value": "x@y.z",
        }

    def test_interact_select_option_round_trip(self):
        step = FlowStep(
            kind=INTERACT, selector="#state", action="select_option", value="DE"
        )
        assert step.to_dict() == {
            "kind": "interact",
            "selector": "#state",
            "value": "DE",
            "action": "select_option",
        }

    def test_submit_round_trip(self):
        step = FlowStep(kind=SUBMIT, selector="button[type='submit']")
        assert step.to_dict() == {
            "kind": "submit",
            "selector": "button[type='submit']",
        }


class TestCaptureMasks:
    def test_selectors_and_regions_round_trip(self) -> None:
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {
                    "kind": "capture",
                    "name": "c",
                    "mask_selectors": ["#clock", ".ad"],
                    "mask_regions": [
                        {"x": 10, "y": 20, "width": 30, "height": 40, "source": "logo"}
                    ],
                },
            ],
        }
        test = parse_test(raw)
        cap = test.flow[-1]
        assert cap.mask_selectors == ("#clock", ".ad")
        assert cap.mask_regions == (
            MaskRegion(x=10, y=20, width=30, height=40, source="logo"),
        )
        assert parse_test(test.to_dict()).to_dict() == test.to_dict()

    def test_selectors_strip_whitespace(self) -> None:
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "capture", "name": "c", "mask_selectors": ["  #clock  "]},
            ],
        }
        assert parse_test(raw).flow[-1].mask_selectors == ("#clock",)

    def test_selectors_must_be_non_empty_strings(self) -> None:
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {"kind": "capture", "name": "c", "mask_selectors": ["   "]},
            ],
        }
        with pytest.raises(ValueError, match="mask_selectors"):
            parse_test(raw)

    def test_regions_require_positive_size(self) -> None:
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank"},
                {
                    "kind": "capture",
                    "name": "c",
                    "mask_regions": [{"x": 0, "y": 0, "width": 0, "height": 10}],
                },
            ],
        }
        with pytest.raises(ValueError, match="positive"):
            parse_test(raw)

    def test_masks_rejected_on_non_capture_steps(self) -> None:
        raw = {
            "name": "x",
            "flow": [
                {"kind": "visit", "url": "about:blank", "mask_selectors": ["#x"]},
                {"kind": "capture", "name": "c"},
            ],
        }
        with pytest.raises(ValueError, match="only valid on capture"):
            parse_test(raw)

    def test_omitted_masks_default_to_empty_tuples(self) -> None:
        cap = FlowStep(kind=CAPTURE, name="c")
        assert cap.mask_selectors == ()
        assert cap.mask_regions == ()
        assert "mask_selectors" not in cap.to_dict()
        assert "mask_regions" not in cap.to_dict()


class TestEnvelope:
    def test_test_to_dict_round_trips(self):
        test = Test(
            name="t",
            flow=[
                FlowStep(kind=VISIT, url="about:blank"),
                FlowStep(kind=CAPTURE, name="c"),
            ],
        )
        assert parse_test(test.to_dict()).to_dict() == test.to_dict()


class TestViewports:
    def _with_viewports(self, viewports: list[dict]) -> dict:
        raw = _minimal_valid()
        raw["viewports"] = viewports
        return raw

    def test_omitted_yields_empty_tuple(self) -> None:
        assert parse_test(_minimal_valid()).viewports == ()

    def test_to_dict_omits_viewports_when_empty(self) -> None:
        out = parse_test(_minimal_valid()).to_dict()
        assert "viewports" not in out

    def test_round_trip_with_viewports(self) -> None:
        raw = self._with_viewports(
            [
                {"name": "desktop", "width": 1280, "height": 800},
                {"name": "mobile", "width": 390, "height": 844},
            ]
        )
        test = parse_test(raw)
        assert test.viewports == (
            Viewport(name="desktop", width=1280, height=800),
            Viewport(name="mobile", width=390, height=844),
        )
        assert parse_test(test.to_dict()).to_dict() == test.to_dict()

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValueError, match="viewports"):
            parse_test(self._with_viewports([]))

    def test_duplicate_names_rejected(self) -> None:
        raw = self._with_viewports(
            [
                {"name": "x", "width": 100, "height": 100},
                {"name": "x", "width": 200, "height": 200},
            ]
        )
        with pytest.raises(ValueError, match="unique"):
            parse_test(raw)

    def test_positive_dimensions_required(self) -> None:
        raw = self._with_viewports([{"name": "x", "width": 0, "height": 100}])
        with pytest.raises(ValueError, match="positive"):
            parse_test(raw)

    def test_name_must_match_identifier(self) -> None:
        raw = self._with_viewports(
            [{"name": "bad/name", "width": 100, "height": 100}]
        )
        with pytest.raises(ValueError, match="name"):
            parse_test(raw)

    def test_dimensions_must_be_integers(self) -> None:
        raw = self._with_viewports(
            [{"name": "x", "width": "wide", "height": 100}]
        )
        with pytest.raises(ValueError, match="integers"):
            parse_test(raw)
