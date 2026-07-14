"""Wayback Machine URL parsing and construction."""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse, urlunparse

WAYBACK_HOSTS = frozenset({"web.archive.org", "web.archive.org."})
WAYBACK_PREFIX_RE = re.compile(
    r"^https?://web\.archive\.org/web/(\d{14})([a-z_]*)/(.+)$",
    re.IGNORECASE,
)


def is_wayback_url(url: str) -> bool:
    try:
        return urlparse(url).netloc.lower().rstrip(".") in WAYBACK_HOSTS
    except Exception:
        return False


def parse_wayback_url(url: str) -> tuple[str, str, str] | None:
    """Return (timestamp, modifier, original_url) or None."""
    m = WAYBACK_PREFIX_RE.match(url.strip())
    if not m:
        return None
    ts, modifier, original = m.group(1), m.group(2) or "", m.group(3)
    return ts, modifier, unquote(original)


def unwrap_wayback_url(url: str) -> str:
    parsed = parse_wayback_url(url)
    if parsed:
        return parsed[2]
    return url


def build_replay_url(original_url: str, timestamp: str, modifier: str = "id_") -> str:
    """Build a Wayback replay URL pinned to a snapshot timestamp."""
    original = original_url.strip()
    if not original.startswith(("http://", "https://")):
        original = f"https://{original}"
    encoded = quote(original, safe=":/?=&%+#")
    return f"https://web.archive.org/web/{timestamp}{modifier}/{encoded}"


def normalize_original_url(url: str) -> str:
    """Normalize a live or archived URL to canonical original form."""
    url = unwrap_wayback_url(url.strip())
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    # Remove default ports
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_canonical_from_cdx(original: str) -> tuple[str, str]:
    """Return (canonical_original_url, cdx_original_url)."""
    cdx_original = original
    canonical = normalize_original_url(original)
    return canonical, cdx_original


def is_homepage_path(url: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(unwrap_wayback_url(url))
    path = parsed.path or "/"
    return path in ("/", "")


def strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def registrable_domain_from_url(url: str) -> str:
    from ffb_webminer.extract.domain import parse_domain

    return parse_domain(unwrap_wayback_url(url)).registrable_domain
