"""URL normalization and same-origin checks.

Pure stdlib. Importable without a browser.
"""

from __future__ import annotations

from urllib.parse import (
    parse_qsl,
    urldefrag,
    urljoin,
    urlsplit,
    urlunsplit,
    urlencode,
)

# Common analytics / session params that should not produce distinct pages.
TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref",
        "ref_src",
        "yclid",
        "_ga",
        "_gl",
    }
)

DEFAULT_PORTS = {"http": "80", "https": "443"}


def absolutize(href: str, base_url: str) -> str:
    """Resolve `href` against `base_url`, returning an absolute URL."""
    return urljoin(base_url, href)


def normalize_url(url: str) -> str:
    """Canonicalize a URL for de-duplication.

    - lower-cases scheme and host
    - drops default ports
    - drops the fragment
    - drops known tracking params
    - sorts remaining query params for stable keys
    - collapses an empty path to "/"
    """
    no_fragment, _frag = urldefrag(url)
    parts = urlsplit(no_fragment)

    scheme = parts.scheme.lower()
    host = parts.hostname or ""
    host = host.lower()
    port = parts.port
    if port is not None and str(port) != DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"

    path = parts.path or "/"

    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    kept.sort()
    query = urlencode(kept, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def same_origin(a: str, b: str) -> bool:
    """True when scheme + host + port match between `a` and `b`."""
    pa, pb = urlsplit(a), urlsplit(b)
    if pa.scheme.lower() != pb.scheme.lower():
        return False
    if (pa.hostname or "").lower() != (pb.hostname or "").lower():
        return False
    pa_port = pa.port or int(DEFAULT_PORTS.get(pa.scheme.lower(), "0"))
    pb_port = pb.port or int(DEFAULT_PORTS.get(pb.scheme.lower(), "0"))
    return pa_port == pb_port


def is_http_like(url: str) -> bool:
    """True when the scheme is one we crawl (http, https, file)."""
    scheme = urlsplit(url).scheme.lower()
    return scheme in {"http", "https", "file"}
