"""Automated quality checks."""

from __future__ import annotations

import json
from typing import Any

from ffb_webminer.archive.wayback_url import is_wayback_url, registrable_domain_from_url
from ffb_webminer.config import QualityConfig
from ffb_webminer.extract.text_utils import normalize_analysis_text


def as_bool(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and value != value:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def as_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, float) and value != value:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def has_fetch_error(page: dict[str, Any]) -> bool:
    error = page.get("fetch_error")
    if error is None:
        return False
    if isinstance(error, float) and error != error:
        return False
    return bool(str(error).strip())


def page_fetch_success(page: dict[str, Any]) -> bool:
    if has_fetch_error(page):
        return False
    status = page.get("http_status")
    if status is None or (isinstance(status, float) and status != status):
        return bool(page.get("content_hash") or page.get("raw_html_path"))
    try:
        return int(status) == 200
    except (TypeError, ValueError):
        return False


def check_page(
    page: dict[str, Any],
    expected_domain: str,
    config: QualityConfig,
) -> dict[str, Any]:
    flags: list[str] = []
    exclusion_reason = None
    usable = True

    text = normalize_analysis_text(page.get("extracted_text"))
    char_count = as_int(page.get("character_count"))

    if has_fetch_error(page):
        flags.append("fetch_error")
        usable = False
        exclusion_reason = page.get("fetch_error")

    status = page.get("http_status")
    if status is not None and not (isinstance(status, float) and status != status):
        try:
            if int(status) >= 400:
                flags.append("http_error")
                usable = False
                exclusion_reason = exclusion_reason or f"http_{status}"
        except (TypeError, ValueError):
            pass

    reg_domain = page.get("registrable_domain")
    if reg_domain and reg_domain != expected_domain:
        flags.append("wrong_domain")
        usable = False
        exclusion_reason = exclusion_reason or "wrong_registrable_domain"

    dist = page.get("temporal_distance_days")
    if dist is not None and float(dist) > config.max_temporal_distance_days:
        flags.append("distant_snapshot")

    if char_count < config.min_text_chars:
        flags.append("short_text")
        if char_count == 0:
            usable = False
            exclusion_reason = exclusion_reason or "empty_text"

    analysis_tokens = page.get("analysis_token_count")
    if analysis_tokens is None:
        analysis_tokens = page.get("token_count")
    try:
        analysis_tokens_n = int(float(analysis_tokens)) if analysis_tokens is not None and str(analysis_tokens) != "nan" else 0
    except (TypeError, ValueError):
        analysis_tokens_n = 0
    if char_count >= config.min_text_chars and analysis_tokens_n <= 0 and usable:
        flags.append("zero_analysis_tokens")
        usable = False
        exclusion_reason = exclusion_reason or "zero_analysis_tokens"

    if _soft_404(text, page.get("document_title")):
        flags.append("soft_404")
        usable = False
        exclusion_reason = exclusion_reason or "soft_404"

    if _navigation_only(text):
        flags.append("navigation_only")

    if page.get("archive_toolbar_removed_flag"):
        flags.append("toolbar_stripped")

    final_url = page.get("final_url") or ""
    if is_wayback_url(final_url) and registrable_domain_from_url(final_url) == "web.archive.org":
        # final_url may be wayback wrapper; check original
        orig_domain = page.get("registrable_domain")
        if orig_domain == "web.archive.org":
            flags.append("wayback_domain_leak")
            usable = False

    page["duplicate_content_flag"] = False
    page["soft_404_flag"] = "soft_404" in flags
    page["likely_navigation_only"] = "navigation_only" in flags
    page["usable_for_analysis"] = usable and char_count >= config.min_text_chars
    page["exclusion_reason"] = exclusion_reason
    return page


def _soft_404(text: str, title: str | None) -> bool:
    combined = f"{title or ''} {text}".lower()
    markers = ("404", "not found", "seite nicht gefunden", "page not found", "error 404")
    return any(m in combined for m in markers) and len(text) < 300


def _navigation_only(text: str) -> bool:
    if not text:
        return True
    words = text.split()
    if len(words) < 30:
        return True
    nav_terms = ("home", "kontakt", "contact", "impressum", "datenschutz", "privacy", "login")
    hits = sum(1 for w in words[:40] if w.lower().strip(".,;:") in nav_terms)
    return hits >= 6 and len(words) < 120


def summarize_snapshot_pages(
    pages: list[dict[str, Any]],
    run_id: str,
    firm_id: str,
    rank: int,
    company: str,
    relative_timepoint: str,
    target_year: int,
    snapshot_status: str,
) -> dict[str, Any]:
    attempted = len(pages)
    success = sum(1 for p in pages if page_fetch_success(p))
    fetch_failed = attempted - success
    usable = sum(1 for p in pages if as_bool(p.get("usable_for_analysis")))
    branding = sum(
        1
        for p in pages
        if as_bool(p.get("branding_corpus_eligible")) and as_bool(p.get("usable_for_analysis"))
    )
    governance = sum(1 for p in pages if p.get("governance_metadata_eligible"))
    legal_technical = sum(
        1
        for p in pages
        if p.get("page_category")
        in {"privacy_policy", "terms_conditions", "cookie_notice", "legal_other", "technical_system", "search_archive"}
    )
    duplicate = sum(1 for p in pages if p.get("duplicate_content_flag"))
    excluded = attempted - usable
    chars = [p.get("character_count") or 0 for p in pages if p.get("character_count")]
    avg_chars = sum(chars) / len(chars) if chars else 0
    all_flags: set[str] = set()
    for p in pages:
        for key in ("soft_404_flag", "likely_navigation_only", "duplicate_content_flag"):
            if p.get(key):
                all_flags.add(key)
    return {
        "run_id": run_id,
        "firm_id": firm_id,
        "rank": rank,
        "company": company,
        "relative_timepoint": relative_timepoint,
        "target_year": target_year,
        "snapshot_status": snapshot_status,
        "pages_attempted": attempted,
        "pages_fetch_success": success,
        "pages_fetch_failed": fetch_failed,
        "pages_extraction_usable": usable,
        "pages_branding_eligible": branding,
        "pages_governance_metadata": governance,
        "pages_excluded_legal_technical": legal_technical,
        "pages_duplicate": duplicate,
        "pages_excluded": excluded,
        "avg_text_chars": round(avg_chars, 1),
        "flags": json.dumps(sorted(all_flags)) if all_flags else None,
    }
