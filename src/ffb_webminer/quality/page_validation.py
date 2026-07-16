"""Page-level validation against snapshot eligibility rules."""

from __future__ import annotations

from typing import Any

from ffb_webminer.config import QualityConfig
from ffb_webminer.quality.checks import as_bool, as_int, has_fetch_error


def validate_page_for_analysis(
    page: dict[str, Any],
    expected_domain: str,
    config: QualityConfig,
    max_temporal_distance: int = 548,
) -> dict[str, Any]:
    flags: list[str] = []
    exclusion_reason = page.get("exclusion_reason")
    usable = as_bool(page.get("usable_for_analysis"))

    status = page.get("http_status")
    if status is not None and not (isinstance(status, float) and status != status):
        try:
            if int(status) >= 400:
                usable = False
                exclusion_reason = exclusion_reason or f"http_{status}"
        except (TypeError, ValueError):
            pass

    if not as_bool(page.get("analysis_eligible")):
        usable = False
        exclusion_reason = exclusion_reason or "observation_not_analysis_eligible"

    if page.get("snapshot_status") != "selected":
        usable = False
        exclusion_reason = exclusion_reason or page.get("snapshot_status")

    dist = page.get("temporal_distance_days")
    if dist is not None and float(dist) > max_temporal_distance:
        flags.append("beyond_temporal_tolerance")
        usable = False
        exclusion_reason = exclusion_reason or "beyond_temporal_tolerance"

    if has_fetch_error(page):
        usable = False
        exclusion_reason = exclusion_reason or str(page.get("fetch_error"))

    if page.get("registrable_domain") and page["registrable_domain"] != expected_domain:
        flags.append("wrong_domain")
        usable = False
        exclusion_reason = exclusion_reason or "wrong_registrable_domain"

    char_count = as_int(page.get("character_count"))
    if char_count < config.min_text_chars:
        flags.append("short_text")
        if char_count == 0:
            usable = False
            exclusion_reason = exclusion_reason or "empty_main_text"

    page["usable_for_analysis"] = usable and as_bool(page.get("analysis_eligible"))
    page["exclusion_reason"] = exclusion_reason
    return page
