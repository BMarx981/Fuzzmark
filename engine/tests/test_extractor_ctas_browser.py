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


def test_extracts_onclick_div(fixture_ctas_url: str) -> None:
    """A styled <div class="btn" onclick> is detected as a button."""
    ctas = extract_ctas(fixture_ctas_url)
    onclick = _by_id(ctas, "div-onclick")
    assert onclick is not None
    assert onclick.kind == "button"
    assert onclick.label == "Save changes"
    assert onclick.href is None


def test_extracts_cursor_pointer_with_name(fixture_ctas_url: str) -> None:
    """A <span style="cursor:pointer"> with text is detected via the visual heuristic."""
    ctas = extract_ctas(fixture_ctas_url)
    span = _by_id(ctas, "span-pointer")
    assert span is not None
    assert span.kind == "button"
    assert span.label == "Toggle theme"


def test_heuristic_skips_decorative_unnamed_pointer(fixture_ctas_url: str) -> None:
    """A cursor:pointer element with no accessible name is not emitted."""
    ctas = extract_ctas(fixture_ctas_url)
    assert _by_id(ctas, "decorative") is None


def test_heuristic_suppresses_child_inside_recorded_wrapper(fixture_ctas_url: str) -> None:
    """When a wrapper is recorded via onclick, its cursor:pointer descendants are skipped."""
    ctas = extract_ctas(fixture_ctas_url)
    wrapper = _by_id(ctas, "wrapper-onclick")
    assert wrapper is not None
    assert wrapper.kind == "button"
    # The wrapper's accessible name is the concatenated descendant text.
    assert wrapper.label == "Open menu"
    # Inner span and icon must NOT be emitted as separate CTAs.
    assert _by_id(ctas, "wrapper-onclick-icon") is None
    assert _by_id(ctas, "wrapper-onclick-label") is None


def test_no_id_links_produce_unambiguous_selectors(tmp_path) -> None:
    """Regression: links without id/name must yield selectors that match
    exactly one element in document order so the driver can click them.

    Previously the extractor emitted `a:nth-of-type(N)` against a
    document-order index, which CSS interprets as position-among-siblings
    and so usually matched zero elements — Locator.click then timed out.
    """
    from playwright.sync_api import sync_playwright

    html = tmp_path / "nav.html"
    html.write_text(
        """<!doctype html>
        <html><body>
          <nav>
            <ul>
              <li><a href="/home">Home</a></li>
              <li><a href="/about">About | CareerMoves</a></li>
              <li><a href="/pricing">Pricing</a></li>
            </ul>
          </nav>
          <footer>
            <a href="/legal">Legal</a>
          </footer>
        </body></html>
        """,
        encoding="utf-8",
    )
    url = html.as_uri()

    ctas = extract_ctas(url)
    by_label = {c.label: c for c in ctas if c.kind == "link"}
    assert set(by_label) == {"Home", "About | CareerMoves", "Pricing", "Legal"}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(url, wait_until="domcontentloaded")
            for label, cta in by_label.items():
                locator = page.locator(cta.selector)
                assert locator.count() == 1, (
                    f"selector {cta.selector!r} for {label!r} matched "
                    f"{locator.count()} elements (expected exactly 1)"
                )
                assert (locator.text_content() or "").strip() == label
        finally:
            browser.close()
