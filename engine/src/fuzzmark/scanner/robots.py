"""robots.txt awareness.

Thin wrapper around stdlib `urllib.robotparser` so the crawler can be tested
without network access by injecting a parser directly.
"""

from __future__ import annotations

from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


def robots_url_for(base_url: str) -> str:
    """Return the well-known robots.txt URL for a same-origin base."""
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


def fetch_robots(base_url: str, user_agent: str, timeout: float = 5.0) -> RobotFileParser | None:
    """Fetch and parse robots.txt for `base_url`. None on any failure.

    `file://` bases have no robots and return None — the crawler treats that
    as "allow all", which matches local-dev override behavior.
    """
    parts = urlsplit(base_url)
    if parts.scheme.lower() not in {"http", "https"}:
        return None
    url = robots_url_for(base_url)
    rp = RobotFileParser()
    rp.set_url(url)
    try:
        req = Request(url, headers={"User-Agent": user_agent})
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        rp.parse(text.splitlines())
    except (URLError, ValueError, TimeoutError):
        return None
    except Exception:
        return None
    return rp


def is_allowed(rp: RobotFileParser | None, url: str, user_agent: str) -> bool:
    """True when robots is missing/unreadable, or `url` is allowed for `user_agent`."""
    if rp is None:
        return True
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True
