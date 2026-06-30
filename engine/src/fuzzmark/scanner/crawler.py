"""BFS crawl with bounds, robots, exclude rules, and a pluggable page fetcher.

Two layers:

- `bfs_crawl` is pure: it walks the frontier in breadth-first order using any
  callable that returns a `FetchResult`. Stub it in tests; no browser needed.
- `crawl` wires `bfs_crawl` to a Chromium-backed fetcher and fetches
  robots.txt up-front.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable
from urllib.robotparser import RobotFileParser

from ..extractor.ctas import _EXTRACT_CTAS_JS, _to_cta
from ..extractor.models import CTA
from .exclude import DEFAULT_EXCLUDE_RULES, ExcludeRule, is_excluded
from .models import CrawlBounds, Page, SiteMap, SkippedUrl
from .normalize import absolutize, is_http_like, normalize_url, same_origin
from .robots import fetch_robots, is_allowed


@dataclass
class FetchResult:
    """What a fetcher returns for one URL."""

    title: str | None = None
    links: list[str] = field(default_factory=list)
    ctas: list[CTA] = field(default_factory=list)
    error: str | None = None


FetchPage = Callable[[str], FetchResult]


def bfs_crawl(
    start_url: str,
    bounds: CrawlBounds,
    fetch_page: FetchPage,
    *,
    robots: RobotFileParser | None = None,
    exclude_rules: tuple[ExcludeRule, ...] = DEFAULT_EXCLUDE_RULES,
    sleep: Callable[[float], None] = time.sleep,
) -> SiteMap:
    """Walk `start_url` in BFS order subject to `bounds`.

    Returns a SiteMap with one Page per visited URL plus a SkippedUrl entry
    per URL the crawl reached but did not enter (with the reason).
    """
    start_norm = normalize_url(start_url)
    site = SiteMap(base_url=start_norm, bounds=bounds)

    frontier: deque[tuple[str, int, str | None]] = deque([(start_norm, 0, None)])
    seen: set[str] = {start_norm}
    visit_idx = 0

    while frontier:
        url, depth, parent = frontier.popleft()

        if len(site.pages) >= bounds.max_pages:
            site.skipped.append(SkippedUrl(url=url, reason="max-pages", parent_url=parent))
            continue

        if bounds.respect_robots and not is_allowed(robots, url, bounds.user_agent):
            site.skipped.append(SkippedUrl(url=url, reason="robots", parent_url=parent))
            continue

        excluded_by = is_excluded(url, exclude_rules)
        if excluded_by is not None:
            site.skipped.append(
                SkippedUrl(url=url, reason=f"exclude:{excluded_by}", parent_url=parent)
            )
            continue

        if visit_idx > 0 and bounds.rate_limit_seconds > 0:
            sleep(bounds.rate_limit_seconds)
        visit_idx += 1

        result = fetch_page(url)
        page = Page(
            url=url,
            depth=depth,
            parent_url=parent,
            title=result.title,
            ctas=list(result.ctas),
            error=result.error,
        )

        if depth < bounds.max_depth and result.error is None:
            child_links: list[str] = []
            for raw in result.links:
                child = _prepare_child(raw, url, start_norm, bounds)
                if child is None:
                    continue
                child_links.append(child)
                if child in seen:
                    continue
                seen.add(child)
                frontier.append((child, depth + 1, url))
            page.links = child_links

        site.pages.append(page)

    return site


def _prepare_child(
    href: str, parent_url: str, origin: str, bounds: CrawlBounds
) -> str | None:
    """Resolve, validate, and normalize a child href.

    Returns None when the href is unusable (non-HTTP scheme, foreign origin
    when `same_origin` is on, malformed URL).
    """
    if not href:
        return None
    try:
        absolute = absolutize(href, parent_url)
    except ValueError:
        return None
    if not is_http_like(absolute):
        return None
    try:
        normalized = normalize_url(absolute)
    except ValueError:
        return None
    if bounds.same_origin and not same_origin(normalized, origin):
        return None
    return normalized


_LINK_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href');
    if (!href) return;
    out.push(href);
  });
  return { title: document.title || null, links: out };
}
"""


def _browser_fetcher(
    timeout_ms: int, headless: bool, session: str | None = None
) -> FetchPage:
    """Build a Chromium-backed fetcher in its own Playwright context."""
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=session)

    def fetch(url: str) -> FetchResult:
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("load", timeout=3000)
            except PlaywrightTimeoutError:
                pass
            data = page.evaluate(_LINK_JS)
            raw_ctas = page.evaluate(_EXTRACT_CTAS_JS)
            return FetchResult(
                title=data.get("title"),
                links=list(data.get("links") or []),
                ctas=[_to_cta(item) for item in (raw_ctas or [])],
            )
        except Exception as exc:
            return FetchResult(error=str(exc))
        finally:
            page.close()

    def close() -> None:
        context.close()
        browser.close()
        pw.stop()

    fetch.close = close
    return fetch


def crawl(
    base_url: str,
    bounds: CrawlBounds | None = None,
    *,
    timeout_ms: int = 15000,
    headless: bool = True,
    robots: RobotFileParser | None = None,
    session: str | None = None,
) -> SiteMap:
    """Crawl `base_url` under `bounds` with a real Chromium browser.

    When `bounds.respect_robots` is on and no `robots` parser is supplied,
    robots.txt is fetched and parsed before the crawl begins. When `session`
    is a path to a Playwright storage_state file, the crawl runs authenticated.
    """
    bounds = bounds or CrawlBounds()
    if robots is None and bounds.respect_robots:
        robots = fetch_robots(base_url, bounds.user_agent)

    fetcher = _browser_fetcher(
        timeout_ms=timeout_ms, headless=headless, session=session
    )
    try:
        return bfs_crawl(base_url, bounds, fetcher, robots=robots)
    finally:
        fetcher.close()
