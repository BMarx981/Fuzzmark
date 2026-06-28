"""Starter exclude list and matcher.

Spec section 5.1: skip session-destroying links (logout), destructive admin
actions, faceted-filter query params, and pagination beyond a small N. The
goal is non-destructive defaults — the user can disable any rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern
from urllib.parse import parse_qsl, urlsplit


@dataclass(frozen=True)
class ExcludeRule:
    """A named rule that matches against a parsed URL."""

    name: str
    description: str
    path_pattern: Pattern[str] | None = None
    query_keys: frozenset[str] = frozenset()
    pagination_param: str | None = None
    pagination_limit: int = 3

    def matches(self, url: str) -> bool:
        parts = urlsplit(url)
        path = parts.path or "/"
        if self.path_pattern is not None and self.path_pattern.search(path):
            return True
        if self.query_keys or self.pagination_param:
            qs = dict(parse_qsl(parts.query, keep_blank_values=True))
            for key in self.query_keys:
                if key in qs:
                    return True
            if self.pagination_param and self.pagination_param in qs:
                try:
                    if int(qs[self.pagination_param]) > self.pagination_limit:
                        return True
                except ValueError:
                    return False
        return False


# Conservative starter set. Patterns are case-insensitive on path.
DEFAULT_EXCLUDE_RULES: tuple[ExcludeRule, ...] = (
    ExcludeRule(
        name="logout",
        description="Session-destroying links",
        path_pattern=re.compile(r"(?i)(/logout\b|/signout\b|/log[-_]out\b)"),
    ),
    ExcludeRule(
        name="admin-destructive",
        description="Destructive admin actions (delete/edit/clone/remove)",
        path_pattern=re.compile(
            r"(?i)(/admin/.*?/(delete|remove|clone|edit)\b|/(delete|remove|destroy)/)"
        ),
    ),
    ExcludeRule(
        name="faceted-filters",
        description="Faceted-search and sort permutations",
        query_keys=frozenset(
            {"sort", "order", "facet", "filter", "f", "tags", "category_filter"}
        ),
    ),
    ExcludeRule(
        name="pagination",
        description="Pagination beyond a small N",
        pagination_param="page",
        pagination_limit=3,
    ),
)


def is_excluded(url: str, rules: tuple[ExcludeRule, ...] = DEFAULT_EXCLUDE_RULES) -> str | None:
    """Return the matching rule name, or None if no rule matches."""
    for rule in rules:
        if rule.matches(url):
            return rule.name
    return None
