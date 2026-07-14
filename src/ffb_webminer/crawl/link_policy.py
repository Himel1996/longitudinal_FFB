"""URL normalization, deduplication, and crawl policy."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from ffb_webminer.archive.wayback_url import strip_fragment, unwrap_wayback_url
from ffb_webminer.extract.domain import parse_domain, same_registrable_domain

EXCLUDED_EXTENSIONS = frozenset(
    {
        "jpg", "jpeg", "png", "gif", "svg", "webp", "ico", "css", "js",
        "pdf", "zip", "rar", "mp3", "mp4", "avi", "mov", "wmv", "doc", "docx",
        "xls", "xlsx", "ppt", "pptx", "xml", "rss", "atom",
    }
)

EXCLUDED_PATH_PATTERNS = re.compile(
    r"(/wp-json/|/feed/?$|/search|/login|/logout|/cart|/tag/|/category/|"
    r"/calendar|/trackback|/cgi-bin/|\.php\?|/media/|/assets/)",
    re.IGNORECASE,
)


def normalize_url(
    url: str,
    strip_query: bool = False,
    exclude_query_patterns: list[str] | None = None,
) -> str:
    original = unwrap_wayback_url(url)
    parsed = urlparse(original)
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = parsed.query
    if strip_query:
        query = ""
    elif exclude_query_patterns and query:
        params = parse_qs(query, keep_blank_values=True)
        filtered = {
            k: v for k, v in params.items()
            if not any(p in k for p in exclude_query_patterns)
        }
        query = urlencode(filtered, doseq=True)
    normalized = urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", query, ""))
    return strip_fragment(normalized)


def is_excluded_url(url: str, extract_pdf: bool = False) -> bool:
    original = unwrap_wayback_url(url)
    parsed = urlparse(original)
    path_lower = (parsed.path or "").lower()
    if EXCLUDED_PATH_PATTERNS.search(path_lower):
        return True
    if parsed.scheme in ("mailto", "tel", "javascript"):
        return True
    ext = path_lower.rsplit(".", 1)[-1] if "." in path_lower else ""
    if ext in EXCLUDED_EXTENSIONS:
        if ext == "pdf" and extract_pdf:
            return False
        return True
    return False


def branding_score(url: str, patterns: dict[str, list[str]], prefer_german: bool) -> int:
    path = urlparse(unwrap_wayback_url(url)).path.lower()
    score = 0
    for i, pattern in enumerate(patterns.get("de", [])):
        if pattern.lower() in path:
            score += 100 - i + (10 if prefer_german else 0)
    for i, pattern in enumerate(patterns.get("en", [])):
        if pattern.lower() in path:
            score += 50 - i
    score += max(0, 30 - len(path))
    return score


def should_follow(
    url: str,
    seed_registrable_domain: str,
    extract_pdf: bool = False,
) -> bool:
    if is_excluded_url(url, extract_pdf=extract_pdf):
        return False
    info = parse_domain(url)
    if info.registrable_domain != seed_registrable_domain:
        return False
    return True


def priority_key(
    url: str,
    depth: int,
    is_homepage: bool,
    patterns: dict[str, list[str]],
    prefer_german: bool,
) -> tuple:
    return (
        0 if is_homepage else 1,
        depth,
        -branding_score(url, patterns, prefer_german),
        len(urlparse(unwrap_wayback_url(url)).path),
    )
