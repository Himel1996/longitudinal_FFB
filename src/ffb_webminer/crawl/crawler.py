"""Focused archived site crawler."""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ffb_webminer.archive.wayback_url import build_replay_url, parse_wayback_url, unwrap_wayback_url
from ffb_webminer.config import CrawlConfig
from ffb_webminer.crawl.fetcher import FetchResult, PageFetcher
from ffb_webminer.crawl.link_policy import (
    is_excluded_url,
    normalize_url,
    priority_key,
    should_follow,
)
from ffb_webminer.extract.domain import parse_domain

logger = logging.getLogger(__name__)

HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


@dataclass
class CrawlPage:
    original_url: str
    depth: int
    discovered_from_url: str | None
    priority_reason: str
    fetch: FetchResult | None = None


@dataclass
class CrawlResult:
    seed_original_url: str
    archive_timestamp: str
    pages: list[CrawlPage] = field(default_factory=list)


def extract_links(html: bytes, base_original_url: str, archive_timestamp: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#"):
            continue
        # Resolve relative to original URL context
        if href.startswith("/web/"):
            parsed = parse_wayback_url(urljoin(f"https://web.archive.org/web/{archive_timestamp}/", href))
            if parsed:
                links.append(parsed[2])
            continue
        absolute = urljoin(base_original_url, href)
        unwrapped = unwrap_wayback_url(absolute)
        links.append(unwrapped)
    return links


def crawl_snapshot(
    seed_original_url: str,
    archive_timestamp: str,
    registrable_domain: str,
    config: CrawlConfig,
    fetcher: PageFetcher,
) -> CrawlResult:
    result = CrawlResult(seed_original_url=seed_original_url, archive_timestamp=archive_timestamp)
    seen: set[str] = set()
    queue: deque[tuple[str, int, str | None, str]] = deque()

    seed_norm = normalize_url(
        seed_original_url,
        strip_query=config.strip_query_strings,
        exclude_query_patterns=config.exclude_query_patterns,
    )
    queue.append((seed_norm, 0, None, "homepage"))
    seen.add(seed_norm)

    if config.mode == "homepage_only":
        max_pages = 1
    else:
        max_pages = config.max_pages_per_snapshot

    fetched = 0
    pending: list[tuple[str, int, str | None, str]] = []

    while queue and fetched < max_pages:
        original, depth, parent, reason = queue.popleft()
        if depth > config.max_depth:
            continue
        if not should_follow(original, registrable_domain, extract_pdf=config.extract_pdf):
            continue

        page = CrawlPage(
            original_url=original,
            depth=depth,
            discovered_from_url=parent,
            priority_reason=reason,
        )
        page.fetch = fetcher.fetch(original, archive_timestamp=archive_timestamp)
        result.pages.append(page)
        fetched += 1

        if not page.fetch or not page.fetch.content or page.fetch.http_status != 200:
            continue
        if config.mode == "homepage_only":
            break

        for link in extract_links(page.fetch.content, original, archive_timestamp):
            norm = normalize_url(
                link,
                strip_query=config.strip_query_strings,
                exclude_query_patterns=config.exclude_query_patterns,
            )
            if norm in seen:
                continue
            if not should_follow(norm, registrable_domain, extract_pdf=config.extract_pdf):
                continue
            if depth + 1 > config.max_depth:
                continue
            seen.add(norm)
            score = priority_key(
                norm,
                depth + 1,
                is_homepage=False,
                patterns=config.branding_path_patterns,
                prefer_german=config.prefer_german_paths,
            )
            pending.append((norm, depth + 1, original, f"branding_score:{-score[2]}"))

        pending.sort(key=lambda item: priority_key(
            item[0], item[1], False, config.branding_path_patterns, config.prefer_german_paths
        ))
        while pending and fetched < max_pages:
            queue.append(pending.pop(0))

    return result
