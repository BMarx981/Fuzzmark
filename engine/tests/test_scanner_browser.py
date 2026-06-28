"""Browser-driven end-to-end test for the scanner over a static fixture site.

Skipped unless `pytest --run-browser` is passed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.scanner import CrawlBounds, crawl

pytestmark = pytest.mark.browser


def _names(urls: list[str]) -> set[str]:
    return {Path(u).name for u in urls}


def test_crawl_walks_same_origin_fixture_site(fixture_site_url: str) -> None:
    site = crawl(
        fixture_site_url,
        CrawlBounds(max_depth=3, max_pages=50, respect_robots=False),
    )

    visited = _names([p.url for p in site.pages])
    assert {"index.html", "about.html", "contact.html", "level2.html", "level3.html"} <= visited

    skipped_reasons = {s.reason for s in site.skipped}
    assert any(r.startswith("exclude:") for r in skipped_reasons), skipped_reasons

    external = [p for p in site.pages if "example.com" in p.url]
    assert external == []


def test_crawl_respects_max_depth(fixture_site_url: str) -> None:
    site = crawl(
        fixture_site_url,
        CrawlBounds(max_depth=1, max_pages=50, respect_robots=False),
    )
    visited = _names([p.url for p in site.pages])
    assert "level3.html" not in visited
    assert "index.html" in visited
    assert "about.html" in visited


def test_crawl_collects_page_titles(fixture_site_url: str) -> None:
    site = crawl(
        fixture_site_url,
        CrawlBounds(max_depth=3, max_pages=50, respect_robots=False),
    )
    titles = {p.title for p in site.pages if p.title}
    assert "Site Index" in titles
    assert "About" in titles
