"""Pure tests for the per-page suggestion decorator."""

from __future__ import annotations

from fuzzmark.extractor import Field, Validation, extract_site
from fuzzmark.suggestions import suggest, suggest_site


def _site_map(*urls: str) -> dict:
    return {
        "base_url": urls[0],
        "pages": [{"url": u, "depth": 0, "title": None, "links": []} for u in urls],
    }


def _email_field() -> Field:
    return Field(
        selector="#email",
        kind="input",
        type="email",
        name="email",
        id="email",
        label="Email",
        validation=Validation(required=True, maxlength=120),
        options=[],
    )


def test_suggest_site_attaches_suggestions_to_each_field() -> None:
    site = _site_map("http://x/a", "http://x/b")
    extract = extract_site(site, extractor=lambda _u: [_email_field()])
    out = suggest_site(extract)

    assert out["base_url"] == "http://x/a"
    assert [p["url"] for p in out["pages"]] == ["http://x/a", "http://x/b"]
    for page in out["pages"]:
        [field] = page["fields"]
        assert field["selector"] == "#email"
        assert field["suggestion_count"] > 0
        assert field["suggestion_count"] == len(field["suggestions"])


def test_suggest_site_matches_direct_suggest_for_a_field() -> None:
    site = _site_map("http://x/a")
    extract = extract_site(site, extractor=lambda _u: [_email_field()])
    out = suggest_site(extract)

    direct = [s.to_dict() for s in suggest(_email_field())]
    assert out["pages"][0]["fields"][0]["suggestions"] == direct


def test_suggest_site_preserves_unrelated_keys() -> None:
    extract = {
        "base_url": "http://x/a",
        "page_count": 1,
        "pages": [
            {
                "url": "http://x/a",
                "title": "T",
                "depth": 0,
                "field_count": 0,
                "fields": [],
                "error": "boom",
            }
        ],
    }
    out = suggest_site(extract)
    assert out["page_count"] == 1
    assert out["pages"][0]["error"] == "boom"
    assert out["pages"][0]["fields"] == []


def test_suggest_site_handles_pages_with_no_fields() -> None:
    site = _site_map("http://x/a")
    extract = extract_site(site, extractor=lambda _u: [])
    out = suggest_site(extract)
    assert out["pages"][0]["fields"] == []
