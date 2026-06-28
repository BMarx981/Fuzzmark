"""Crawl a target within bounds and produce a selectable site map."""

from .crawler import FetchResult, bfs_crawl, crawl
from .exclude import DEFAULT_EXCLUDE_RULES, ExcludeRule, is_excluded
from .models import CrawlBounds, Page, SiteMap, SkippedUrl
from .normalize import is_http_like, normalize_url, same_origin
from .robots import fetch_robots, is_allowed

__all__ = [
    "crawl",
    "bfs_crawl",
    "CrawlBounds",
    "Page",
    "SiteMap",
    "SkippedUrl",
    "FetchResult",
    "ExcludeRule",
    "DEFAULT_EXCLUDE_RULES",
    "is_excluded",
    "normalize_url",
    "same_origin",
    "is_http_like",
    "fetch_robots",
    "is_allowed",
]
