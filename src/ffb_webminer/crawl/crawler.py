"""Focused archived site crawler with reserved-slot prioritization."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ffb_webminer.archive.wayback_url import parse_wayback_url, unwrap_wayback_url
from ffb_webminer.config import CrawlConfig
from ffb_webminer.crawl.fetcher import FetchResult, PageFetcher
from ffb_webminer.crawl.link_policy import normalize_url, should_follow
from ffb_webminer.crawl.priority import score_candidate
from ffb_webminer.crawl.url_canonical import canonicalize_page_url

logger = logging.getLogger(__name__)


@dataclass
class CrawlPage:
    original_url: str
    depth: int
    discovered_from_url: str | None
    priority_reason: str
    fetch: FetchResult | None = None
    crawl_priority_tier: int | None = None
    crawl_priority_score: int | None = None
    reserved_slot_category: str | None = None
    selected_under_reserved_slot: bool = False
    crawl_selection_reason: str | None = None
    crawl_budget_position: int | None = None
    path_language_hint: str | None = None
    path_language_priority: str | None = None
    language_path_reason: str | None = None


@dataclass
class CrawlSummary:
    n_high_priority_pages_discovered: int = 0
    n_high_priority_pages_fetched: int = 0
    n_high_priority_pages_missing: int = 0
    n_secondary_pages_fetched: int = 0
    n_broad_pages_fetched: int = 0
    n_foreign_pages_deprioritized: int = 0
    crawl_limit_reached: bool = False
    unused_reserved_slots: int = 0


@dataclass
class CrawlResult:
    seed_original_url: str
    archive_timestamp: str
    pages: list[CrawlPage] = field(default_factory=list)
    summary: CrawlSummary = field(default_factory=CrawlSummary)


def extract_links(html: bytes, base_original_url: str, archive_timestamp: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#"):
            continue
        if href.startswith("/web/"):
            parsed = parse_wayback_url(urljoin(f"https://web.archive.org/web/{archive_timestamp}/", href))
            if parsed:
                links.append(parsed[2])
            continue
        absolute = urljoin(base_original_url, href)
        links.append(unwrap_wayback_url(absolute))
    return links


def _default_reserved(config: CrawlConfig) -> dict[str, int]:
    if config.reserved_slots:
        return dict(config.reserved_slots)
    return {
        "homepage": 1,
        "company_about": 4,
        "history_heritage": 3,
        "family_owners": 3,
        "values_responsibility": 3,
        "management_leadership": 3,
    }


def crawl_snapshot(
    seed_original_url: str,
    archive_timestamp: str,
    registrable_domain: str,
    config: CrawlConfig,
    fetcher: PageFetcher,
) -> CrawlResult:
    result = CrawlResult(seed_original_url=seed_original_url, archive_timestamp=archive_timestamp)
    if config.mode == "homepage_only":
        max_pages = 1
    else:
        max_pages = config.max_pages_per_snapshot

    seed_norm = normalize_url(
        seed_original_url,
        strip_query=config.strip_query_strings,
        exclude_query_patterns=config.exclude_query_patterns,
    )
    seen_groups: set[str] = set()
    candidates: dict[str, dict] = {}

    def _add_candidate(url: str, depth: int, parent: str | None, is_homepage: bool = False) -> None:
        if depth > config.max_depth:
            return
        if not should_follow(url, registrable_domain, extract_pdf=config.extract_pdf):
            return
        norm = normalize_url(
            url,
            strip_query=config.strip_query_strings,
            exclude_query_patterns=config.exclude_query_patterns,
        )
        canon = canonicalize_page_url(norm)
        if not canon.canonical_page_url or canon.url_variant_group_id in seen_groups:
            return
        seen_groups.add(canon.url_variant_group_id)
        pri = score_candidate(norm, depth=depth, is_homepage=is_homepage)
        candidates[canon.url_variant_group_id] = {
            "url": norm,
            "depth": depth,
            "parent": parent,
            "priority": pri,
            "group_id": canon.url_variant_group_id,
        }
        if pri.crawl_priority_tier == 1:
            result.summary.n_high_priority_pages_discovered += 1
        if pri.path_language_priority == "foreign_language_deprioritized":
            result.summary.n_foreign_pages_deprioritized += 1

    # Stage 1: homepage
    _add_candidate(seed_norm, 0, None, is_homepage=True)

    # Fetch homepage first to discover links
    homepage_group = canonicalize_page_url(seed_norm).url_variant_group_id
    homepage = candidates.get(homepage_group)
    fetched = 0
    reserved_remaining = _default_reserved(config)
    flexible_secondary = int(config.flexible_slots.get("secondary_pages", 5))
    flexible_broad = int(config.flexible_slots.get("broad_context", 3))

    def _fetch_one(item: dict, under_reserved: bool, reason: str) -> None:
        nonlocal fetched
        if fetched >= max_pages:
            return
        pri = item["priority"]
        page = CrawlPage(
            original_url=item["url"],
            depth=item["depth"],
            discovered_from_url=item["parent"],
            priority_reason=reason,
            crawl_priority_tier=pri.crawl_priority_tier,
            crawl_priority_score=pri.crawl_priority_score,
            reserved_slot_category=pri.reserved_slot_category,
            selected_under_reserved_slot=under_reserved,
            crawl_selection_reason=reason,
            crawl_budget_position=fetched + 1,
            path_language_hint=pri.path_language_hint,
            path_language_priority=pri.path_language_priority,
            language_path_reason=pri.language_path_reason,
        )
        page.fetch = fetcher.fetch(item["url"], archive_timestamp=archive_timestamp)
        result.pages.append(page)
        fetched += 1
        if pri.crawl_priority_tier == 1:
            result.summary.n_high_priority_pages_fetched += 1
        elif pri.crawl_priority_tier == 2:
            result.summary.n_secondary_pages_fetched += 1
        else:
            result.summary.n_broad_pages_fetched += 1

        if page.fetch and page.fetch.content and page.fetch.http_status == 200 and item["depth"] < config.max_depth:
            for link in extract_links(page.fetch.content, item["url"], archive_timestamp):
                _add_candidate(link, item["depth"] + 1, item["url"], is_homepage=False)

    if homepage:
        _fetch_one(homepage, True, "homepage")
        if homepage["priority"].reserved_slot_category in reserved_remaining:
            reserved_remaining[homepage["priority"].reserved_slot_category] = max(
                0, reserved_remaining[homepage["priority"].reserved_slot_category] - 1
            )
        # remove homepage from remaining candidates
        candidates.pop(homepage_group, None)

    # Stage 2+: select by reserved slots then flexible
    def _sorted_candidates() -> list[dict]:
        return sorted(
            candidates.values(),
            key=lambda c: (
                c["priority"].crawl_priority_tier,
                -c["priority"].crawl_priority_score,
                c["depth"],
                c["url"],
            ),
        )

    # Reserved high-value pages (German preferred; foreign cannot consume reserved)
    for category, slots in list(reserved_remaining.items()):
        while slots > 0 and fetched < max_pages:
            pick = None
            for cand in _sorted_candidates():
                pri = cand["priority"]
                if pri.reserved_slot_category != category:
                    continue
                if pri.path_language_priority == "foreign_language_deprioritized":
                    continue
                pick = cand
                break
            if not pick:
                break
            candidates.pop(pick["group_id"], None)
            _fetch_one(pick, True, f"reserved_slot:{category}")
            slots -= 1
            reserved_remaining[category] = slots

    unused_reserved = sum(reserved_remaining.values())
    result.summary.unused_reserved_slots = unused_reserved

    # Flexible secondary
    while flexible_secondary > 0 and fetched < max_pages:
        pick = None
        for cand in _sorted_candidates():
            if cand["priority"].crawl_priority_tier == 2:
                pick = cand
                break
        if not pick:
            break
        candidates.pop(pick["group_id"], None)
        _fetch_one(pick, False, "flexible_secondary")
        flexible_secondary -= 1

    # Remaining capacity: overflow unused reserved into tier1 leftovers, then broad
    overflow = unused_reserved + flexible_broad
    while overflow > 0 and fetched < max_pages and candidates:
        pick = _sorted_candidates()[0]
        candidates.pop(pick["group_id"], None)
        reason = "overflow_unused_reserved" if unused_reserved > 0 else "flexible_broad"
        if pick["priority"].crawl_priority_tier == 1:
            reason = "overflow_unused_reserved_high_priority"
        _fetch_one(pick, False, reason)
        if unused_reserved > 0:
            unused_reserved -= 1
            result.summary.unused_reserved_slots = unused_reserved
        overflow -= 1

    # If still capacity, continue with best remaining
    while fetched < max_pages and candidates:
        pick = _sorted_candidates()[0]
        candidates.pop(pick["group_id"], None)
        _fetch_one(pick, False, "remaining_capacity")

    result.summary.crawl_limit_reached = fetched >= max_pages
    result.summary.n_high_priority_pages_missing = max(
        0,
        result.summary.n_high_priority_pages_discovered - result.summary.n_high_priority_pages_fetched,
    )
    return result
