"""Data models for the scanner: crawl bounds, discovered pages, site map."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CrawlBounds:
    """Trap-aware defaults per spec section 5.1."""

    max_depth: int = 3
    max_pages: int = 50
    same_origin: bool = True
    respect_robots: bool = True
    rate_limit_seconds: float = 0.0
    user_agent: str = "fuzzmark/0.1"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Page:
    """A page reached during the crawl."""

    url: str
    depth: int
    parent_url: Optional[str]
    title: Optional[str] = None
    links: list[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkippedUrl:
    """A URL the crawl reached but did not visit, with the reason."""

    url: str
    reason: str
    parent_url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SiteMap:
    """Result of a single scan: visited pages and skipped URLs."""

    base_url: str
    bounds: CrawlBounds
    pages: list[Page] = field(default_factory=list)
    skipped: list[SkippedUrl] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "bounds": self.bounds.to_dict(),
            "page_count": len(self.pages),
            "skipped_count": len(self.skipped),
            "pages": [p.to_dict() for p in self.pages],
            "skipped": [s.to_dict() for s in self.skipped],
        }
