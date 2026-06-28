"""Browser-driven extractor coverage for ARIA widgets, contenteditable,
shadow DOM, and same-origin iframes (Phase 6 — component coverage).

Skipped unless `pytest --run-browser` is passed.
"""

from __future__ import annotations

import pytest

from fuzzmark.extractor import Field, extract_fields

pytestmark = pytest.mark.browser


def _by_id(fields: list[Field], element_id: str) -> Field | None:
    for f in fields:
        if f.id == element_id:
            return f
    return None


def _by_selector_suffix(fields: list[Field], suffix: str) -> Field | None:
    for f in fields:
        if f.selector.endswith(suffix):
            return f
    return None


def test_widens_to_aria_contenteditable_shadow_and_iframe(
    fixture_components_url: str,
) -> None:
    fields = extract_fields(fixture_components_url)

    # ARIA combobox with a controlled listbox → kind=select with options.
    country = _by_id(fields, "country")
    assert country is not None
    assert country.kind == "select"
    assert country.label == "Country"
    assert country.validation.required is True
    assert [o.value for o in country.options] == ["us", "ca", "mx"]
    assert [o.label for o in country.options] == ["United States", "Canada", "Mexico"]

    # ARIA listbox directly → kind=select with options.
    priority = _by_id(fields, "priority")
    assert priority is not None
    assert priority.kind == "select"
    assert [o.value for o in priority.options] == ["low", "med", "high"]

    # ARIA single-line textbox → kind=input, type=text. aria-required honored.
    displayname = _by_id(fields, "displayname")
    assert displayname is not None
    assert displayname.kind == "input"
    assert displayname.type == "text"
    assert displayname.validation.required is True

    # ARIA multiline textbox → kind=textarea.
    bio = _by_id(fields, "bio")
    assert bio is not None
    assert bio.kind == "textarea"
    assert bio.type is None

    # ARIA spinbutton → kind=input, type=number; aria-valuemin/max become min/max.
    qty = _by_id(fields, "qty")
    assert qty is not None
    assert qty.kind == "input"
    assert qty.type == "number"
    assert qty.validation.min == "1"
    assert qty.validation.max == "99"

    # ARIA checkbox / switch → input/checkbox.
    newsletter = _by_id(fields, "newsletter")
    assert newsletter is not None and newsletter.kind == "input" and newsletter.type == "checkbox"
    notifications = _by_id(fields, "notifications")
    assert notifications is not None and notifications.kind == "input" and notifications.type == "checkbox"

    # ARIA radios → input/radio.
    plan_free = _by_id(fields, "plan-free")
    plan_pro = _by_id(fields, "plan-pro")
    assert plan_free is not None and plan_free.kind == "input" and plan_free.type == "radio"
    assert plan_pro is not None and plan_pro.kind == "input" and plan_pro.type == "radio"

    # Plain contenteditable → kind=textarea.
    notes = _by_id(fields, "notes")
    assert notes is not None
    assert notes.kind == "textarea"
    assert notes.label == "Notes"

    # Shadow DOM child reached and selector carries a >>> hop.
    shadow_input = _by_id(fields, "shadow-input")
    assert shadow_input is not None
    assert shadow_input.kind == "input"
    assert shadow_input.type == "email"
    assert shadow_input.validation.required is True
    assert shadow_input.validation.maxlength == 60
    assert " >>> " in shadow_input.selector
    assert shadow_input.selector.startswith("#card1 >>> ")

    # Same-origin iframe children reached and selector carries a >>> hop.
    iemail = _by_id(fields, "iemail")
    iname = _by_id(fields, "iname")
    assert iemail is not None and iemail.type == "email" and iemail.validation.required is True
    assert iname is not None and iname.type == "text" and iname.validation.minlength == 2
    assert iemail.selector.startswith("#inner-frame >>> ")
    assert iname.selector.startswith("#inner-frame >>> ")


def test_native_form_still_extracts_six_fields(fixture_form_url: str) -> None:
    """Widening must not regress the MVP smoke fixture."""
    fields = extract_fields(fixture_form_url)
    names = [f.name for f in fields]
    assert names == ["email", "fullname", "zip", "age", "state", "message"]
