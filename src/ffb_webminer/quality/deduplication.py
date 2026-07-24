"""Within firm × timepoint content deduplication."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from typing import Any

from ffb_webminer.crawl.url_canonical import canonicalize_page_url
from ffb_webminer.extract.text_utils import normalize_analysis_text
from ffb_webminer.quality.checks import as_bool, as_int

WAYBACK_NOISE = re.compile(
    r"(internet archive|wayback machine|building façade|web icon an illustration|"
    r"donate icon|upload search icon|captured\s+\d)",
    re.IGNORECASE,
)

CATEGORY_RANK = {
    "homepage": 0,
    "company_about": 1,
    "history_heritage": 2,
    "family_values": 3,
    "management_leadership": 4,
    "sustainability_responsibility": 5,
    "careers_employer": 6,
    "news_press": 7,
    "products_services": 8,
    "contact": 9,
}


def normalize_for_hash(text: str | None) -> str:
    normalized = normalize_analysis_text(text)
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = WAYBACK_NOISE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def content_hashes(text: str | None) -> tuple[str | None, str | None]:
    raw = normalize_analysis_text(text)
    if not raw:
        return None, None
    exact = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    norm = hashlib.sha256(normalize_for_hash(raw).encode("utf-8")).hexdigest()
    return exact, norm


def _retention_key(row: dict[str, Any], preferred_host: str | None) -> tuple:
    path = str(row.get("path") or row.get("canonical_page_url") or "")
    host = str(row.get("canonical_host") or "")
    category = str(row.get("page_category") or "unknown")
    germanish = 0 if any(tok in path.lower() for tok in ("/de", "ueber", "über", "unternehmen", "geschichte", "familie", "werte")) else 1
    preferred = 0 if preferred_host and host == preferred_host.replace("www.", "") else 1
    url = str(row.get("canonical_page_url") or row.get("original_archived_url") or "")
    crawl_pos = as_int(row.get("crawl_budget_position"), default=10_000)
    return (
        CATEGORY_RANK.get(category, 50),
        germanish,
        preferred,
        len(url),
        crawl_pos,
        url,
    )


def annotate_url_canonical_fields(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in pages:
        raw = row.get("original_archived_url") or row.get("normalized_url") or row.get("final_url")
        canon = canonicalize_page_url(raw)
        row = dict(row)
        row["raw_original_url"] = canon.raw_original_url or row.get("original_archived_url")
        row["canonical_page_url"] = canon.canonical_page_url
        row["canonical_host"] = canon.canonical_host
        row["url_variant_group_id"] = canon.url_variant_group_id
        exact, norm = content_hashes(row.get("main_text") or row.get("extracted_text"))
        row["exact_content_hash"] = exact
        row["normalized_content_hash"] = norm
        out.append(row)
    return out


def deduplicate_within_observations(
    pages: list[dict[str, Any]],
    preferred_hosts: dict[str, str] | None = None,
    near_duplicate_threshold: float = 0.98,
) -> list[dict[str, Any]]:
    """
    Deduplicate identical normalized content within firm_id × relative_timepoint only.
    Cross-timepoint duplicates are intentionally retained.
    """
    preferred_hosts = preferred_hosts or {}
    pages = annotate_url_canonical_fields(pages)

    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for idx, row in enumerate(pages):
        key = (str(row.get("firm_id")), str(row.get("relative_timepoint")))
        groups[key].append(idx)

    for (_firm, _tp), idxs in groups.items():
        # exact normalized content groups
        by_hash: dict[str, list[int]] = defaultdict(list)
        by_url_group: dict[str, list[int]] = defaultdict(list)
        for i in idxs:
            row = pages[i]
            nh = row.get("normalized_content_hash")
            if nh:
                by_hash[nh].append(i)
            ug = row.get("url_variant_group_id")
            if ug:
                by_url_group[ug].append(i)

        preferred = preferred_hosts.get(str(pages[idxs[0]].get("firm_id")))

        # Mark content duplicates
        for nh, members in by_hash.items():
            if len(members) < 2:
                continue
            ranked = sorted(members, key=lambda i: _retention_key(pages[i], preferred))
            winner = ranked[0]
            group_id = f"dup_{nh[:12]}"
            pages[winner]["duplicate_group_id"] = group_id
            pages[winner]["duplicate_content_flag"] = False
            pages[winner]["duplicate_of_page_id"] = None
            pages[winner]["duplicate_reason"] = None
            for loser in ranked[1:]:
                pages[loser]["duplicate_group_id"] = group_id
                pages[loser]["duplicate_content_flag"] = True
                pages[loser]["duplicate_of_page_id"] = pages[winner].get("original_archived_url")
                same_url_group = (
                    pages[loser].get("url_variant_group_id")
                    and pages[loser].get("url_variant_group_id") == pages[winner].get("url_variant_group_id")
                )
                reason = "duplicate_url_variant" if same_url_group else "duplicate_host_variant"
                # if hosts differ www/non-www already collapsed in canonical host, still mark host variant if raw hosts differ
                raw_hosts = {
                    str(pages[j].get("hostname") or "").lower().lstrip("www.")
                    for j in (winner, loser)
                }
                if len(raw_hosts) > 1:
                    reason = "duplicate_host_variant"
                pages[loser]["duplicate_reason"] = reason
                if as_bool(pages[loser].get("branding_corpus_eligible")):
                    pages[loser]["branding_corpus_eligible"] = False
                    pages[loser]["branding_corpus_exclusion_reason"] = "duplicate_within_observation"

        # URL-variant groups with empty text still get provenance IDs
        for ug, members in by_url_group.items():
            if len(members) < 2:
                continue
            for i in members:
                pages[i].setdefault("url_variant_group_id", ug)

        # Optional near-duplicate: only if high threshold and same token-normalized prefix
        # Conservative: require identical first 200 chars of normalized text and length ratio
        texts = []
        for i in idxs:
            text = normalize_for_hash(pages[i].get("main_text") or pages[i].get("extracted_text"))
            texts.append((i, text))
        for a, (i, ta) in enumerate(texts):
            if not ta or pages[i].get("duplicate_content_flag"):
                continue
            for j, tb in texts[a + 1 :]:
                if not tb or pages[j].get("duplicate_content_flag"):
                    continue
                if pages[i].get("normalized_content_hash") == pages[j].get("normalized_content_hash"):
                    continue
                shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
                if not longer:
                    continue
                ratio = len(shorter) / len(longer)
                if ratio < near_duplicate_threshold:
                    continue
                if shorter[:200] != longer[:200]:
                    continue
                # treat as near-duplicate of longer/shorter using retention priority
                ranked = sorted([i, j], key=lambda x: _retention_key(pages[x], preferred))
                winner, loser = ranked[0], ranked[1]
                group_id = pages[winner].get("duplicate_group_id") or f"near_{pages[winner].get('normalized_content_hash', 'x')[:12]}"
                pages[winner]["duplicate_group_id"] = group_id
                pages[winner]["near_duplicate_signature"] = shorter[:64]
                pages[loser]["duplicate_group_id"] = group_id
                pages[loser]["duplicate_content_flag"] = True
                pages[loser]["duplicate_of_page_id"] = pages[winner].get("original_archived_url")
                pages[loser]["duplicate_reason"] = "near_duplicate"
                pages[loser]["near_duplicate_signature"] = shorter[:64]
                if as_bool(pages[loser].get("branding_corpus_eligible")):
                    pages[loser]["branding_corpus_eligible"] = False
                    pages[loser]["branding_corpus_exclusion_reason"] = "duplicate_within_observation"

    for row in pages:
        row.setdefault("duplicate_content_flag", False)
        row.setdefault("duplicate_group_id", None)
        row.setdefault("duplicate_of_page_id", None)
        row.setdefault("duplicate_reason", None)
        row.setdefault("near_duplicate_signature", None)
    return pages
