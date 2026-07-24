"""Post-extraction language inclusion for German primary corpora."""

from __future__ import annotations

from typing import Any

from ffb_webminer.config import AnalysisConfig
from ffb_webminer.crawl.language_paths import infer_path_language
from ffb_webminer.quality.checks import as_bool


def annotate_language_inclusion(
    pages: list[dict[str, Any]],
    analysis_cfg: AnalysisConfig,
) -> list[dict[str, Any]]:
    """
    Annotate page-level German corpus eligibility.

    Path language is advisory; page-level text_language is authoritative.
    """
    out = []
    for row in pages:
        row = dict(row)
        url = row.get("original_archived_url") or row.get("normalized_url") or row.get("path")
        if not row.get("path_language_hint"):
            hint = infer_path_language(url)
            row["path_language_hint"] = hint.path_language_hint
            row["path_language_priority"] = hint.path_language_priority
            row["language_path_reason"] = hint.language_path_reason

        detected = (row.get("text_language") or "unknown").lower()
        confidence = float(row.get("text_language_confidence") or 0.0)
        row["detected_language"] = detected
        row["language_confidence"] = confidence

        path_hint = (row.get("path_language_hint") or "unknown").lower()
        if path_hint in {"unknown", "de"} and detected == "de":
            agreement = "agree_german"
        elif path_hint == detected and detected not in {"unknown", ""}:
            agreement = "agree"
        elif path_hint != "unknown" and detected not in {"unknown", ""} and path_hint != detected:
            agreement = "disagree"
        elif detected == "unknown":
            agreement = "detection_unknown"
        else:
            agreement = "partial"
        row["language_hint_detection_agreement"] = agreement

        german_eligible, reason = _german_eligible(row, analysis_cfg)
        row["german_corpus_eligible"] = german_eligible
        row["language_exclusion_reason"] = reason
        out.append(row)
    return out


def _german_eligible(row: dict[str, Any], analysis_cfg: AnalysisConfig) -> tuple[bool, str | None]:
    if not as_bool(row.get("usable_for_analysis")):
        return False, "not_usable_for_analysis"
    if as_bool(row.get("duplicate_content_flag")):
        return False, "duplicate_within_observation"

    detected = (row.get("text_language") or row.get("detected_language") or "unknown").lower()
    confidence = float(row.get("text_language_confidence") or row.get("language_confidence") or 0.0)
    threshold = float(analysis_cfg.language_confidence_threshold)
    german_share_min = float(getattr(analysis_cfg, "german_token_share_min", 0.70))
    chars = int(row.get("character_count") or 0)
    short_limit = int(analysis_cfg.short_text_language_chars)

    if detected == "de" and confidence >= threshold:
        return True, None
    if detected == "de" and confidence < threshold:
        # accept low-confidence German if text is not short and path prefers German
        if chars >= short_limit and (row.get("path_language_priority") == "preferred_german"):
            return True, None
        return False, "german_low_confidence"

    if detected in {"en", "fr", "es", "it", "pl", "ru", "zh", "nl", "pt"}:
        return False, f"non_german_detected:{detected}"

    if detected in {"unknown", "mixed", ""}:
        # Optional mixed-language German share if present
        share = row.get("german_token_share")
        if share is not None and float(share) >= german_share_min:
            return True, None
        if chars < short_limit:
            return False, "unknown_short_text"
        if analysis_cfg.allow_unknown_in_german_corpus:
            return True, None
        return False, "unknown_language_excluded"

    return False, f"non_german_detected:{detected}"
