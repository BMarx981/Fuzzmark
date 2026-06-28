"""Browser-driven extractor coverage for the active reveal pass
(Phase 7 entry — interaction discovery).

Skipped unless `pytest --run-browser` is passed.
"""

from __future__ import annotations

import pytest

from fuzzmark.extractor import extract_fields

pytestmark = pytest.mark.browser


def _names(fields) -> list[str]:
    return [f.name for f in fields]


def test_passive_only_misses_hidden_fields(fixture_components_reveal_url: str) -> None:
    fields = extract_fields(fixture_components_reveal_url)
    assert _names(fields) == ["email"]


def test_reveal_surfaces_disclosed_and_details_fields(
    fixture_components_reveal_url: str,
) -> None:
    fields = extract_fields(fixture_components_reveal_url, reveal=16)
    # All fields should now be discovered. Order: passive-discovered first,
    # then new fields appended in the order their reveal-trigger fires.
    assert set(_names(fields)) == {
        "email",
        "cardname",
        "cardnumber",
        "address",
        "country",
        "referral",
        "coupon",
        "phone",
    }


def test_reveal_surfaces_dialog_opener_fields(
    fixture_components_reveal_url: str,
) -> None:
    # The coupon dialog has no aria-expanded; only aria-haspopup="dialog".
    # With a tight reveal cap, aria-expanded + details triggers come first.
    # A larger cap should still reach the dialog opener.
    fields = extract_fields(fixture_components_reveal_url, reveal=16)
    assert "coupon" in _names(fields)


def test_reveal_surfaces_text_pattern_trigger(
    fixture_components_reveal_url: str,
) -> None:
    # "Add another phone" is a text-pattern reveal — no aria attrs on it.
    fields = extract_fields(fixture_components_reveal_url, reveal=16)
    assert "phone" in _names(fields)


def test_reveal_pass_is_idempotent(fixture_components_reveal_url: str) -> None:
    first = extract_fields(fixture_components_reveal_url, reveal=8)
    second = extract_fields(fixture_components_reveal_url, reveal=8)
    assert [f.selector for f in first] == [f.selector for f in second]


def test_reveal_cap_bounds_clicks(fixture_components_reveal_url: str) -> None:
    # With reveal=1, only the first aria-expanded trigger fires (billing).
    fields = extract_fields(fixture_components_reveal_url, reveal=1)
    names = set(_names(fields))
    assert "email" in names
    assert {"cardname", "cardnumber"} <= names
    # Shipping, country, referral remain hidden.
    assert "address" not in names
    assert "country" not in names
    assert "referral" not in names


def test_reveal_zero_matches_passive_default(fixture_components_reveal_url: str) -> None:
    default = extract_fields(fixture_components_reveal_url)
    explicit_zero = extract_fields(fixture_components_reveal_url, reveal=0)
    assert _names(default) == _names(explicit_zero)


def test_negative_reveal_raises() -> None:
    with pytest.raises(ValueError):
        extract_fields("about:blank", reveal=-1)
