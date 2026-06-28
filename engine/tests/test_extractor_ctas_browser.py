"""Browser-driven coverage for CTA extraction
(Phase 7 — first-class CTA/button modeling).

Skipped unless `pytest --run-browser` is passed.
"""

from __future__ import annotations

import pytest

from fuzzmark.extractor import CTA, extract_ctas

pytestmark = pytest.mark.browser


def _by_id(ctas: list[CTA], element_id: str) -> CTA | None:
    sel = "#" + element_id
    for c in ctas:
        if c.selector == sel:
            return c
    return None


def test_extracts_native_buttons_and_inputs(fixture_ctas_url: str) -> None:
    ctas = extract_ctas(fixture_ctas_url)

    submit = _by_id(ctas, "btn-submit")
    assert submit is not None
    assert submit.kind == "button"
    assert submit.label == "Send message"
    assert submit.disabled is False
    assert submit.href is None

    cancel = _by_id(ctas, "btn-cancel")
    assert cancel is not None and cancel.kind == "button" and cancel.label == "Cancel"

    disabled = _by_id(ctas, "btn-disabled")
    assert disabled is not None and disabled.disabled is True

    input_submit = _by_id(ctas, "input-submit")
    assert input_submit is not None
    assert input_submit.kind == "button"
    assert input_submit.label == "Submit form"

    input_button = _by_id(ctas, "input-button")
    assert input_button is not None
    assert input_button.kind == "button"
    assert input_button.label == "Reset filters"


def test_extracts_role_button_widgets(fixture_ctas_url: str) -> None:
    ctas = extract_ctas(fixture_ctas_url)

    role1 = _by_id(ctas, "role-btn-1")
    assert role1 is not None and role1.kind == "button" and role1.label == "Open dialog"
    assert role1.disabled is False

    role2 = _by_id(ctas, "role-btn-2")
    # aria-label wins over textContent ('×')
    assert role2 is not None and role2.label == "Close"

    role3 = _by_id(ctas, "role-btn-3")
    # aria-disabled flips disabled
    assert role3 is not None and role3.disabled is True


def test_extracts_links_and_skips_anchorless(fixture_ctas_url: str) -> None:
    ctas = extract_ctas(fixture_ctas_url)

    pricing = _by_id(ctas, "link-pricing")
    assert pricing is not None
    assert pricing.kind == "link"
    assert pricing.href == "/pricing"
    assert pricing.label == "See pricing"

    docs = _by_id(ctas, "link-docs")
    assert docs is not None and docs.href == "https://example.com/docs"

    # Anchor with empty href and anchor without href are skipped.
    assert _by_id(ctas, "link-noop") is None
    assert _by_id(ctas, "link-anchorless") is None


def test_accessible_name_fallbacks(fixture_ctas_url: str) -> None:
    ctas = extract_ctas(fixture_ctas_url)

    # aria-labelledby resolves through to the referenced element's text.
    labelledby = _by_id(ctas, "btn-labelledby")
    assert labelledby is not None and labelledby.label == "Purchase"

    # title is the lowest-priority fallback (after aria-label, value, text).
    title = _by_id(ctas, "btn-title")
    assert title is not None and title.label == "Settings"


def test_native_form_fixture_has_one_submit_cta(fixture_form_url: str) -> None:
    """Regression check against the MVP form fixture: only the Send button."""
    ctas = extract_ctas(fixture_form_url)
    assert len(ctas) == 1
    assert ctas[0].kind == "button"
    assert ctas[0].label == "Send"
