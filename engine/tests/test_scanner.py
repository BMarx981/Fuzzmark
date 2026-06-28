"""Pure unit tests for the scanner: normalize, exclude, robots, BFS.

No browser, no network. The BFS is exercised with a stub fetcher.
"""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

import pytest

from fuzzmark.scanner import (
    CrawlBounds,
    DEFAULT_EXCLUDE_RULES,
    FetchResult,
    bfs_crawl,
    is_allowed,
    is_excluded,
    normalize_url,
    same_origin,
)


class TestNormalize:
    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTP://Example.COM/Path") == "http://example.com/Path"

    def test_strips_default_port(self):
        assert normalize_url("http://example.com:80/x") == "http://example.com/x"
        assert normalize_url("https://example.com:443/x") == "https://example.com/x"

    def test_keeps_nondefault_port(self):
        assert normalize_url("http://example.com:8080/") == "http://example.com:8080/"

    def test_drops_fragment(self):
        assert normalize_url("http://x/y#section") == "http://x/y"

    def test_drops_tracking_params_and_sorts_rest(self):
        out = normalize_url("http://x/y?utm_source=ml&b=2&a=1&fbclid=xx")
        assert out == "http://x/y?a=1&b=2"

    def test_collapses_empty_path(self):
        assert normalize_url("http://x") == "http://x/"

    def test_same_origin(self):
        assert same_origin("http://a/x", "http://a/y")
        assert not same_origin("http://a/x", "http://b/x")
        assert not same_origin("http://a/x", "https://a/x")
        assert same_origin("http://a:80/x", "http://a/x")


class TestExclude:
    def test_logout_excluded(self):
        assert is_excluded("http://x/logout") == "logout"
        assert is_excluded("http://x/users/signout") == "logout"

    def test_admin_destructive_excluded(self):
        assert is_excluded("http://x/admin/posts/42/delete") == "admin-destructive"
        assert is_excluded("http://x/delete/42") == "admin-destructive"

    def test_faceted_filters_excluded(self):
        assert is_excluded("http://x/search?sort=asc") == "faceted-filters"
        assert is_excluded("http://x/list?facet=tag&q=hi") == "faceted-filters"

    def test_pagination_within_limit_allowed(self):
        assert is_excluded("http://x/list?page=2") is None

    def test_pagination_beyond_limit_excluded(self):
        assert is_excluded("http://x/list?page=99") == "pagination"

    def test_plain_url_not_excluded(self):
        assert is_excluded("http://x/about") is None


class TestRobots:
    def _parser(self, body: str) -> RobotFileParser:
        rp = RobotFileParser()
        rp.parse(body.splitlines())
        return rp

    def test_missing_parser_allows_everything(self):
        assert is_allowed(None, "http://x/anything", "ua")

    def test_disallow_blocks_matching_path(self):
        rp = self._parser("User-agent: *\nDisallow: /admin")
        assert not is_allowed(rp, "http://x/admin/users", "ua")
        assert is_allowed(rp, "http://x/about", "ua")


class _StubFetcher:
    def __init__(self, pages: dict[str, FetchResult]):
        self.pages = pages
        self.visited: list[str] = []

    def __call__(self, url: str) -> FetchResult:
        self.visited.append(url)
        return self.pages.get(url, FetchResult(error="404"))


def _r(*links: str, title: str = "T") -> FetchResult:
    return FetchResult(title=title, links=list(links))


class TestBfsCrawl:
    def test_walks_breadth_first_and_dedups(self):
        pages = {
            "http://x/": _r("/a", "/b", "/a"),
            "http://x/a": _r("/c"),
            "http://x/b": _r("/c"),
            "http://x/c": _r(),
        }
        fetcher = _StubFetcher(pages)
        site = bfs_crawl("http://x/", CrawlBounds(max_depth=5, max_pages=50), fetcher)
        urls = [p.url for p in site.pages]
        assert urls == ["http://x/", "http://x/a", "http://x/b", "http://x/c"]

    def test_respects_max_depth(self):
        pages = {
            "http://x/": _r("/a"),
            "http://x/a": _r("/b"),
            "http://x/b": _r("/c"),
            "http://x/c": _r(),
        }
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=1, max_pages=50), _StubFetcher(pages)
        )
        urls = [p.url for p in site.pages]
        assert urls == ["http://x/", "http://x/a"]

    def test_respects_max_pages(self):
        pages = {
            "http://x/": _r("/a", "/b", "/c"),
            "http://x/a": _r(),
            "http://x/b": _r(),
            "http://x/c": _r(),
        }
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=5, max_pages=2), _StubFetcher(pages)
        )
        assert len(site.pages) == 2
        reasons = {s.reason for s in site.skipped}
        assert "max-pages" in reasons

    def test_same_origin_filter(self):
        pages = {
            "http://x/": _r("http://other/a", "/b"),
            "http://x/b": _r(),
        }
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=5, max_pages=50), _StubFetcher(pages)
        )
        urls = [p.url for p in site.pages]
        assert "http://other/a" not in urls
        assert urls == ["http://x/", "http://x/b"]

    def test_cross_origin_allowed_when_disabled(self):
        pages = {
            "http://x/": _r("http://other/a"),
            "http://other/a": _r(),
        }
        site = bfs_crawl(
            "http://x/",
            CrawlBounds(max_depth=5, max_pages=50, same_origin=False),
            _StubFetcher(pages),
        )
        urls = [p.url for p in site.pages]
        assert "http://other/a" in urls

    def test_normalizes_links_and_dedups_across_variants(self):
        pages = {
            "http://x/": _r("/a", "/a?utm_source=ml", "/a#frag"),
            "http://x/a": _r(),
        }
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=5, max_pages=50), _StubFetcher(pages)
        )
        urls = [p.url for p in site.pages]
        assert urls == ["http://x/", "http://x/a"]

    def test_skips_excluded_urls(self):
        pages = {
            "http://x/": _r("/about", "/logout", "/list?page=99"),
            "http://x/about": _r(),
        }
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=5, max_pages=50), _StubFetcher(pages)
        )
        urls = [p.url for p in site.pages]
        assert urls == ["http://x/", "http://x/about"]
        reasons = sorted(s.reason for s in site.skipped)
        assert "exclude:logout" in reasons
        assert "exclude:pagination" in reasons

    def test_skips_non_http_schemes(self):
        pages = {"http://x/": _r("mailto:a@b", "javascript:void(0)", "/a"), "http://x/a": _r()}
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=5, max_pages=50), _StubFetcher(pages)
        )
        urls = [p.url for p in site.pages]
        assert urls == ["http://x/", "http://x/a"]

    def test_robots_disallow_skips(self):
        rp = RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /private"])
        pages = {
            "http://x/": _r("/private", "/public"),
            "http://x/public": _r(),
        }
        site = bfs_crawl(
            "http://x/",
            CrawlBounds(max_depth=5, max_pages=50),
            _StubFetcher(pages),
            robots=rp,
        )
        urls = [p.url for p in site.pages]
        assert "http://x/private" not in urls
        assert any(s.reason == "robots" for s in site.skipped)

    def test_records_fetch_error(self):
        pages = {"http://x/": FetchResult(error="boom")}
        site = bfs_crawl(
            "http://x/", CrawlBounds(max_depth=5, max_pages=50), _StubFetcher(pages)
        )
        assert site.pages[0].error == "boom"
        assert site.pages[0].links == []

    def test_rate_limit_sleeps_between_visits(self):
        pages = {"http://x/": _r("/a"), "http://x/a": _r()}
        sleeps: list[float] = []
        bfs_crawl(
            "http://x/",
            CrawlBounds(max_depth=5, max_pages=50, rate_limit_seconds=0.25),
            _StubFetcher(pages),
            sleep=sleeps.append,
        )
        assert sleeps == [0.25]
