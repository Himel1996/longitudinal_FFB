"""Domain and subdomain parsing."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import tldextract

from ffb_webminer.archive.wayback_url import unwrap_wayback_url


@dataclass(frozen=True)
class DomainInfo:
    scheme: str
    hostname: str
    subdomain: str
    registrable_domain: str
    suffix: str
    normalized_url: str
    path: str
    query: str


def parse_domain(url: str) -> DomainInfo:
    original = unwrap_wayback_url(url)
    parsed = urlparse(original)
    ext = tldextract.extract(original)
    registrable = ext.registered_domain or parsed.netloc.lower()
    subdomain = ext.subdomain or ""
    hostname = parsed.netloc.lower()
    path = parsed.path or "/"
    return DomainInfo(
        scheme=parsed.scheme or "https",
        hostname=hostname,
        subdomain=subdomain,
        registrable_domain=registrable,
        suffix=ext.suffix or "",
        normalized_url=original.split("#")[0],
        path=path,
        query=parsed.query,
    )


def same_registrable_domain(url_a: str, url_b: str) -> bool:
    return parse_domain(url_a).registrable_domain == parse_domain(url_b).registrable_domain
