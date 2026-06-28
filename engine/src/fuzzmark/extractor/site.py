"""Per-page extraction across a scanner SiteMap.

A scan (spec section 5.1) discovers pages; the field extractor (5.2) operates on
one page at a time. This module composes the two: take a `SiteMap.to_dict()`,
optionally filter by an explicit include list, and run the extractor on each
selected page. The extractor is injectable so the composition is testable
without a browser.

The browser dependency is isolated to the default extractor (`extract_fields`),
so any caller that injects its own extractor can import this module without
Playwright.
"""

from __future__ import annotations

from typing import Callable, Iterable

from .fields import extract_fields
from .models import Field


Extractor = Callable[[str], list[Field]]


def select_pages(
    site_map: dict, *, include: Iterable[str] | None = None
) -> list[dict]:
    """Return the page dicts to extract from.

    With `include=None` every visited page from the scan is returned. With an
    explicit iterable of URLs, only pages whose URL is in that set survive, in
    the order they appeared in the scan.
    """
    pages = site_map.get("pages") or []
    if include is None:
        return list(pages)
    wanted = set(include)
    return [p for p in pages if p.get("url") in wanted]


def extract_site(
    site_map: dict,
    *,
    extractor: Extractor = extract_fields,
    include: Iterable[str] | None = None,
) -> dict:
    """Run `extractor` on each selected page and emit a multi-page payload.

    Pages that yield no fields are still listed so callers can see "I asked for
    this page but it had no form." An extractor exception is caught per-page
    and surfaced as `error` on that page entry; the rest of the scan continues.
    """
    selected = select_pages(site_map, include=include)
    out_pages: list[dict] = []
    for page in selected:
        url = page.get("url")
        if not isinstance(url, str):
            continue
        error: str | None = None
        fields: list[Field] = []
        try:
            fields = extractor(url)
        except Exception as exc:
            error = str(exc)
        entry = {
            "url": url,
            "title": page.get("title"),
            "depth": page.get("depth"),
            "field_count": len(fields),
            "fields": [f.to_dict() for f in fields],
        }
        if error is not None:
            entry["error"] = error
        out_pages.append(entry)
    return {
        "base_url": site_map.get("base_url"),
        "page_count": len(out_pages),
        "pages": out_pages,
    }
