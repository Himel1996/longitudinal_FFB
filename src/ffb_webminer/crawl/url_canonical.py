"""Canonical page URL identity for within-observation deduplication."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from ffb_webminer.archive.wayback_url import unwrap_wayback_url

INDEX_BASENAMES = frozenset({"index.html", "index.htm", "index.php", "default.html", "default.htm", "home.html"})
DEFAULT_PORTS = {("http", "80"), ("https", "443")}


@dataclass
class CanonicalUrl:
    raw_original_url: str
    canonical_page_url: str
    canonical_host: str
    url_variant_group_id: str


def _collapse_slashes(path: str) -> str:
    return re.sub(r"/{2,}", "/", path or "/")


def canonicalize_page_url(url: str | None, preferred_scheme: str = "https") -> CanonicalUrl:
    raw = str(url or "").strip()
    unwrapped = unwrap_wayback_url(raw) if raw else ""
    if not unwrapped:
        empty_id = hashlib.sha1(b"empty").hexdigest()[:16]
        return CanonicalUrl(raw, "", "", empty_id)

    parsed = urlparse(unwrapped)
    # Normalize HTTP/HTTPS to preferred scheme so equivalent archives share identity
    scheme = preferred_scheme.lower() if preferred_scheme else "https"
    if scheme not in {"http", "https"}:
        scheme = "https"

    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    port = parsed.port
    netloc = host
    # Drop default ports; keep non-default ports on netloc
    if port is not None and str(port) not in {"80", "443"}:
        netloc = f"{host}:{port}"

    path = _collapse_slashes(parsed.path or "/")
    # drop trailing slash except root
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # collapse index pages to directory / root
    basename = path.rsplit("/", 1)[-1].lower()
    if basename in INDEX_BASENAMES:
        parent = path[: -(len(basename))]
        path = parent.rstrip("/") or "/"

    # drop empty/default query noise
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {
        k: v
        for k, v in params.items()
        if k and any(str(item).strip() for item in v)
    }
    query = urlencode(sorted((k, item) for k, vals in filtered.items() for item in vals), doseq=True)

    canonical = urlunparse((scheme, netloc, path, "", query, ""))
    group_id = hashlib.sha1(f"{host}|{path}|{query}".encode("utf-8")).hexdigest()[:16]
    return CanonicalUrl(
        raw_original_url=raw,
        canonical_page_url=canonical,
        canonical_host=host,
        url_variant_group_id=group_id,
    )
