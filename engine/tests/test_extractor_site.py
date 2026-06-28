"""Pure tests for the multi-page extractor composition.

The browser extractor is injected so these tests never touch Playwright.
"""

from __future__ import annotations

import pytest

from fuzzmark.extractor import Field, Option, Validation, extract_site, select_pages


def _field(selector: str, kind: str = "input", type_: str = "text") -> Field:
    return Field(
        selector=selector,
        kind=kind,
        type=type_,
        name=None,
        id=None,
        label=None,
        validation=Validation(),
        options=[],
    )


def _site_map(*urls: str) -> dict:
    return {
        "base_url": urls[0] if urls else "http://x/",
        "page_count": len(urls),
        "skipped_count": 0,
        "pages": [
            {"url": u, "depth": i, "parent_url": None, "title": f"T{i}", "links": [], "error": None}
            for i, u in enumerate(urls)
        ],
        "skipped": [],
    }


class TestSelectPages:
    def test_returns_all_pages_when_include_is_none(self) -> None:
        site = _site_map("http://x/a", "http://x/b")
        assert [p["url"] for p in select_pages(site)] == ["http://x/a", "http://x/b"]

    def test_include_filters_to_listed_urls(self) -> None:
        site = _site_map("http://x/a", "http://x/b", "http://x/c")
        out = select_pages(site, include=["http://x/b", "http://x/c"])
        assert [p["url"] for p in out] == ["http://x/b", "http://x/c"]

    def test_include_preserves_scan_order(self) -> None:
        site = _site_map("http://x/a", "http://x/b", "http://x/c")
        out = select_pages(site, include=["http://x/c", "http://x/a"])
        assert [p["url"] for p in out] == ["http://x/a", "http://x/c"]

    def test_unknown_urls_in_include_drop_silently(self) -> None:
        site = _site_map("http://x/a")
        assert select_pages(site, include=["http://x/missing"]) == []

    def test_missing_pages_field_yields_empty(self) -> None:
        assert select_pages({"base_url": "http://x/"}) == []


class TestExtractSite:
    def test_runs_extractor_per_page(self) -> None:
        site = _site_map("http://x/a", "http://x/b")
        calls: list[str] = []

        def fake(url: str) -> list[Field]:
            calls.append(url)
            return [_field(f"#input-{url[-1]}")]

        out = extract_site(site, extractor=fake)
        assert calls == ["http://x/a", "http://x/b"]
        assert out["base_url"] == "http://x/a"
        assert out["page_count"] == 2
        assert [p["url"] for p in out["pages"]] == ["http://x/a", "http://x/b"]
        assert [p["field_count"] for p in out["pages"]] == [1, 1]

    def test_include_narrows_extraction(self) -> None:
        site = _site_map("http://x/a", "http://x/b", "http://x/c")
        calls: list[str] = []

        def fake(url: str) -> list[Field]:
            calls.append(url)
            return []

        out = extract_site(site, extractor=fake, include=["http://x/b"])
        assert calls == ["http://x/b"]
        assert [p["url"] for p in out["pages"]] == ["http://x/b"]
        assert out["page_count"] == 1

    def test_empty_pages_still_appear(self) -> None:
        site = _site_map("http://x/a")
        out = extract_site(site, extractor=lambda _u: [])
        assert out["pages"][0]["field_count"] == 0
        assert out["pages"][0]["fields"] == []
        assert "error" not in out["pages"][0]

    def test_extractor_exception_is_captured_per_page(self) -> None:
        site = _site_map("http://x/a", "http://x/b")

        def fake(url: str) -> list[Field]:
            if url.endswith("a"):
                raise RuntimeError("bad page")
            return [_field("#ok")]

        out = extract_site(site, extractor=fake)
        a, b = out["pages"]
        assert a["error"] == "bad page"
        assert a["field_count"] == 0
        assert "error" not in b
        assert b["field_count"] == 1

    def test_field_dicts_round_trip_back_through_models(self) -> None:
        site = _site_map("http://x/a")
        field = Field(
            selector="#s",
            kind="select",
            type=None,
            name="s",
            id="s",
            label="State",
            validation=Validation(required=True),
            options=[Option(value="DE", label="Delaware")],
        )
        out = extract_site(site, extractor=lambda _u: [field])
        raw = out["pages"][0]["fields"][0]
        assert raw["selector"] == "#s"
        assert raw["validation"]["required"] is True
        assert raw["options"] == [{"value": "DE", "label": "Delaware"}]

    def test_non_string_url_is_skipped(self) -> None:
        site = {"base_url": "http://x/", "pages": [{"url": None}, {"url": "http://x/a"}]}
        out = extract_site(site, extractor=lambda _u: [])
        assert [p["url"] for p in out["pages"]] == ["http://x/a"]
