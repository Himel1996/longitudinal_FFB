"""Observation-level corpus and governance outputs."""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from ffb_webminer.config import AnalysisConfig
from ffb_webminer.extract.text_utils import normalize_analysis_text
from ffb_webminer.governance.extraction import extract_governance_metadata, json_list, merge_governance_texts
from ffb_webminer.pipeline.schemas import (
    BRANDING_CORPUS_OBSERVATION_COLUMNS,
    BRANDING_CORPUS_PAGE_COLUMNS,
    CRAWL_PRIORITY_SUMMARY_COLUMNS,
    DUPLICATE_SUMMARY_COLUMNS,
    GOVERNANCE_METADATA_OBSERVATION_COLUMNS,
    GOVERNANCE_METADATA_PAGE_COLUMNS,
    OBSERVATION_TEXT_SUMMARY_COLUMNS,
)
from ffb_webminer.quality.checks import as_bool, page_fetch_success


def build_governance_metadata_pages(pages: pd.DataFrame) -> pd.DataFrame:
    eligible = pages[pages["governance_metadata_eligible"].fillna(False).astype(bool)]
    rows = []
    for _, page in eligible.iterrows():
        g = extract_governance_metadata(page.get("extracted_text"))
        rows.append({
            "run_id": page["run_id"],
            "firm_id": page["firm_id"],
            "company": page["company"],
            "relative_timepoint": page["relative_timepoint"],
            "target_date": page["target_date"],
            "selected_capture_date": page["selected_capture_date"],
            "original_archived_url": page["original_archived_url"],
            "wayback_replay_url": page["wayback_replay_url"],
            "document_title": page.get("document_title"),
            "page_category": page.get("page_category"),
            "extracted_text": page.get("extracted_text"),
            "managing_directors_raw": g.managing_directors_raw,
            "legal_representatives_raw": g.legal_representatives_raw,
            "legal_entity_raw": g.legal_entity_raw,
            "parent_company_raw": g.parent_company_raw,
            "registered_address_raw": g.registered_address_raw,
            "registration_number_raw": g.registration_number_raw,
            "vat_id_raw": g.vat_id_raw,
            "extraction_confidence": g.extraction_confidence,
            "extraction_notes": g.extraction_notes,
            "governance_inclusion_reason": page.get("governance_inclusion_reason"),
            "governance_rule_id": page.get("governance_rule_id"),
            "governance_evidence_type": page.get("governance_evidence_type"),
        })
    df = pd.DataFrame(rows)
    for col in GOVERNANCE_METADATA_PAGE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[GOVERNANCE_METADATA_PAGE_COLUMNS]


def build_governance_metadata_observations(snapshots: pd.DataFrame, governance_pages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, snap in snapshots.iterrows():
        subset = governance_pages[
            (governance_pages["firm_id"].astype(str) == str(snap["firm_id"]))
            & (governance_pages["relative_timepoint"] == snap["relative_timepoint"])
        ]
        impressum_like = subset[subset["page_category"].isin(["impressum", "legal_notice"])]
        merged = merge_governance_texts(subset["extracted_text"].fillna("").tolist())
        reps = json_list(subset["legal_representatives_raw"].dropna().astype(str).tolist())
        entities = json_list(subset["legal_entity_raw"].dropna().astype(str).tolist())
        parents = json_list(subset["parent_company_raw"].dropna().astype(str).tolist())
        quality = "high" if len(subset) and merged else "moderate" if len(subset) else "low"
        rows.append({
            "run_id": snap["run_id"],
            "firm_id": snap["firm_id"],
            "company": snap["company"],
            "relative_timepoint": snap["relative_timepoint"],
            "target_date": snap["target_date"],
            "selected_capture_date": snap["selected_capture_date"],
            "impressum_available": bool(len(impressum_like)),
            "governance_metadata_text": merged,
            "detected_legal_representatives": reps,
            "detected_legal_entity": entities,
            "detected_parent_company": parents,
            "governance_metadata_quality": quality,
            "governance_metadata_source_urls": json_list(
                subset["original_archived_url"].dropna().astype(str).tolist()
            ),
        })
    df = pd.DataFrame(rows)
    for col in GOVERNANCE_METADATA_OBSERVATION_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[GOVERNANCE_METADATA_OBSERVATION_COLUMNS]


def _language_bucket(lang: str | None) -> str:
    code = (lang or "unknown").lower()
    if code == "de":
        return "de"
    if code == "en":
        return "en"
    if code in {"", "unknown"}:
        return "unknown"
    return "other"


def _language_stats(pages: pd.DataFrame) -> dict:
    counts = {"de": 0, "en": 0, "other": 0, "unknown": 0}
    tokens = {"de": 0, "en": 0, "other": 0, "unknown": 0}
    for _, page in pages.iterrows():
        bucket = _language_bucket(page.get("detected_language") or page.get("text_language"))
        counts[bucket] += 1
        tokens[bucket] += int(page.get("token_count") or 0)
    primary = max(tokens.items(), key=lambda kv: kv[1])[0] if any(tokens.values()) else "unknown"
    if not any(tokens.values()) and any(counts.values()):
        primary = max(counts.items(), key=lambda kv: kv[1])[0]
    return {
        "n_pages_de": counts["de"],
        "n_pages_en": counts["en"],
        "n_pages_other": counts["other"],
        "n_pages_unknown": counts["unknown"],
        "tokens_de": tokens["de"],
        "tokens_en": tokens["en"],
        "tokens_other": tokens["other"],
        "tokens_unknown": tokens["unknown"],
        "primary_language_by_tokens": primary,
    }


def build_observation_text_summary(
    snapshots: pd.DataFrame,
    pages: pd.DataFrame,
    governance_obs: pd.DataFrame,
    analysis_cfg: AnalysisConfig,
) -> pd.DataFrame:
    gov_lookup = {
        (str(r["firm_id"]), r["relative_timepoint"]): r for _, r in governance_obs.iterrows()
    }
    rows = []
    for _, snap in snapshots.iterrows():
        key = (str(snap["firm_id"]), snap["relative_timepoint"])
        subset = pages[
            (pages["firm_id"].astype(str) == key[0])
            & (pages["relative_timepoint"] == key[1])
        ].copy()
        fetch_success = sum(page_fetch_success(row.to_dict()) for _, row in subset.iterrows())
        attempted = len(subset)
        extraction_usable = int(subset["usable_for_analysis"].fillna(False).astype(bool).sum())
        branding_pages = subset[
            subset["branding_corpus_eligible"].fillna(False).astype(bool)
            & subset["usable_for_analysis"].fillna(False).astype(bool)
        ]
        german_branding = branding_pages[
            branding_pages["german_corpus_eligible"].fillna(False).astype(bool)
        ] if "german_corpus_eligible" in branding_pages.columns else branding_pages
        legal_technical = subset[subset["page_category"].isin([
            "privacy_policy",
            "terms_conditions",
            "cookie_notice",
            "legal_other",
            "technical_system",
            "search_archive",
            "impressum",
            "legal_notice",
        ])]
        duplicates = int(subset["duplicate_content_flag"].fillna(False).sum())
        dup_pages = subset[subset["duplicate_content_flag"].fillna(False).astype(bool)]
        dup_tokens = int(dup_pages["token_count"].fillna(0).sum())
        dup_words = int(dup_pages["word_count"].fillna(0).sum())
        usable_pages = subset[subset["usable_for_analysis"].fillna(False)]
        all_words = int(usable_pages["word_count"].fillna(0).sum())
        all_tokens = int(usable_pages["token_count"].fillna(0).sum())
        branding_words = int(branding_pages["word_count"].fillna(0).sum())
        branding_tokens = int(branding_pages["token_count"].fillna(0).sum())
        german_tokens = int(german_branding["token_count"].fillna(0).sum())
        gov = gov_lookup.get(key)
        gov_words = (
            len(normalize_analysis_text(gov.get("governance_metadata_text")).split())
            if gov is not None
            else 0
        )

        lang_counter: Counter[str] = Counter()
        unknown_lang = 0
        for _, page in branding_pages.iterrows():
            lang = page.get("detected_language") or page.get("text_language") or "unknown"
            tokens = int(page.get("token_count") or 0)
            if lang == "unknown":
                unknown_lang += 1
            lang_counter[lang] += tokens if tokens > 0 else 1
        primary_lang = max(lang_counter.items(), key=lambda kv: kv[1])[0] if lang_counter else "unknown"
        lang_stats = _language_stats(branding_pages)

        exclusion_reason = None
        eligible = as_bool(snap.get("analysis_eligible"))
        if snap.get("snapshot_status") != "selected":
            exclusion_reason = "no_valid_snapshot"
            eligible = False
        elif snap.get("observation_recommendation") == "exclude_duplicate_capture":
            exclusion_reason = "duplicate_capture"
            eligible = False
        elif not as_bool(snap.get("analysis_eligible")):
            exclusion_reason = "observation_excluded_temporally"
            eligible = False
        elif len(branding_pages) < analysis_cfg.min_branding_pages:
            exclusion_reason = "no_branding_pages"
            eligible = False
        elif branding_tokens < analysis_cfg.min_branding_tokens:
            exclusion_reason = "insufficient_branding_tokens"
            eligible = False

        german_exclusion = None
        german_eligible = eligible
        if not eligible:
            german_eligible = False
            german_exclusion = exclusion_reason
        elif len(german_branding) < analysis_cfg.min_branding_pages:
            german_eligible = False
            german_exclusion = "no_german_branding_pages"
        elif german_tokens < analysis_cfg.min_branding_tokens:
            german_eligible = False
            german_exclusion = "insufficient_german_branding_tokens"

        quality_band = "ineligible"
        if eligible:
            if branding_tokens >= analysis_cfg.preferred_branding_tokens:
                quality_band = "high"
            elif branding_tokens >= analysis_cfg.moderate_quality_token_threshold:
                quality_band = "moderate"
            else:
                quality_band = "low"

        rows.append({
            "run_id": snap["run_id"],
            "firm_id": snap["firm_id"],
            "company": snap["company"],
            "relative_timepoint": snap["relative_timepoint"],
            "target_date": snap["target_date"],
            "selected_capture_date": snap["selected_capture_date"],
            "snapshot_status": snap["snapshot_status"],
            "observation_recommendation": snap["observation_recommendation"],
            "analysis_eligible": snap["analysis_eligible"],
            "n_pages_total": attempted,
            "n_pages_fetch_success": fetch_success,
            "n_pages_extraction_usable": extraction_usable,
            "n_branding_pages_eligible": len(branding_pages),
            "n_branding_pages_excluded": max(extraction_usable - len(branding_pages), 0),
            "n_unique_branding_pages": len(branding_pages),
            "n_impressum_pages": int(subset["page_category"].isin(["impressum", "legal_notice"]).sum()),
            "n_legal_technical_pages": len(legal_technical),
            "n_duplicate_pages": duplicates,
            "n_duplicate_pages_within_observation": duplicates,
            "duplicate_tokens_removed": dup_tokens,
            "duplicate_words_removed": dup_words,
            "deduplication_applied": duplicates > 0 or bool(subset.get("normalized_content_hash") is not None),
            "total_word_count_all_usable_pages": all_words,
            "total_token_count_all_usable_pages": all_tokens,
            "branding_word_count": branding_words,
            "branding_token_count": branding_tokens,
            "governance_metadata_word_count": gov_words,
            "detected_primary_language": primary_lang,
            "language_distribution_json": (
                json.dumps(dict(lang_counter), ensure_ascii=False) if lang_counter else None
            ),
            "n_pages_language_unknown": unknown_lang,
            **lang_stats,
            "german_text_analysis_eligible": german_eligible,
            "german_text_analysis_exclusion_reason": german_exclusion,
            "text_analysis_eligible": eligible,
            "text_analysis_exclusion_reason": exclusion_reason,
            "text_analysis_quality_band": quality_band,
        })
    df = pd.DataFrame(rows)
    for col in OBSERVATION_TEXT_SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[OBSERVATION_TEXT_SUMMARY_COLUMNS]


def _banned_categories() -> set[str]:
    return {
        "impressum",
        "legal_notice",
        "privacy_policy",
        "terms_conditions",
        "cookie_notice",
        "legal_other",
    }


def build_branding_corpus_pages(
    pages: pd.DataFrame,
    observation_summary: pd.DataFrame,
    *,
    language_scope: str = "all",
    require_german_observation: bool = False,
) -> pd.DataFrame:
    """Page-level branding corpus for eligible observations only.

    language_scope: all | de | en | other
    """
    elig = {
        (str(r["firm_id"]), r["relative_timepoint"]): r
        for _, r in observation_summary.iterrows()
    }
    banned = _banned_categories()
    rows = []
    for _, page in pages.iterrows():
        key = (str(page["firm_id"]), page["relative_timepoint"])
        obs = elig.get(key)
        if obs is None:
            continue
        if require_german_observation:
            if not as_bool(obs.get("german_text_analysis_eligible")):
                continue
        elif not as_bool(obs.get("text_analysis_eligible")):
            continue
        if obs.get("observation_recommendation") not in {"include", "sensitivity_analysis"}:
            continue
        if as_bool(page.get("duplicate_content_flag")):
            continue
        if not (as_bool(page.get("branding_corpus_eligible")) and as_bool(page.get("usable_for_analysis"))):
            continue
        if page.get("page_category") in banned:
            continue

        bucket = _language_bucket(page.get("detected_language") or page.get("text_language"))
        if language_scope == "de":
            if not as_bool(page.get("german_corpus_eligible")):
                continue
        elif language_scope == "en":
            if bucket != "en":
                continue
        elif language_scope == "other":
            if bucket not in {"other", "unknown"}:
                continue
        # language_scope == "all": keep all languages

        row = page.to_dict()
        row["text_analysis_eligible"] = True
        row["text_analysis_quality_band"] = obs.get("text_analysis_quality_band")
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in BRANDING_CORPUS_PAGE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BRANDING_CORPUS_PAGE_COLUMNS] if not df.empty else pd.DataFrame(columns=BRANDING_CORPUS_PAGE_COLUMNS)


def build_branding_corpus_observations(
    observation_summary: pd.DataFrame,
    branding_pages: pd.DataFrame,
    primary_only: bool | None = None,
    *,
    corpus_language_scope: str = "all",
    use_german_eligibility: bool = False,
) -> pd.DataFrame:
    """
    Observation-level branding corpus.

    observation_text_summary.csv is authoritative for eligibility:
    - primary: recommendation == include AND text_analysis_eligible
      (or german_text_analysis_eligible when use_german_eligibility)
    - sensitivity: recommendation in {include, sensitivity_analysis} AND eligible
    """
    summary = observation_summary.copy()
    elig_col = "german_text_analysis_eligible" if use_german_eligibility else "text_analysis_eligible"
    summary = summary[summary[elig_col].fillna(False).astype(bool)]
    if primary_only is True:
        summary = summary[summary["observation_recommendation"] == "include"]
    else:
        summary = summary[
            summary["observation_recommendation"].isin(["include", "sensitivity_analysis"])
        ]

    rows = []
    for _, obs in summary.iterrows():
        subset = branding_pages[
            (branding_pages["firm_id"].astype(str) == str(obs["firm_id"]))
            & (branding_pages["relative_timepoint"] == obs["relative_timepoint"])
        ].sort_values(
            by=[c for c in ("page_category", "path") if c in branding_pages.columns]
        )
        # Never mix English into German primary denominators
        if corpus_language_scope == "de":
            if "german_corpus_eligible" in subset.columns:
                subset = subset[subset["german_corpus_eligible"].fillna(False).astype(bool)]
            elif "detected_language" in subset.columns:
                subset = subset[subset["detected_language"].fillna("").eq("de")]
            elif "text_language" in subset.columns:
                subset = subset[subset["text_language"].fillna("").eq("de")]
        elif corpus_language_scope == "en" and len(subset):
            langs = subset["detected_language"].fillna(subset.get("text_language")) if "detected_language" in subset.columns else subset["text_language"]
            subset = subset[langs.fillna("").map(_language_bucket).eq("en")]
        elif corpus_language_scope == "other" and len(subset):
            langs = subset["detected_language"].fillna(subset.get("text_language")) if "detected_language" in subset.columns else subset["text_language"]
            subset = subset[langs.fillna("").map(_language_bucket).isin(["other", "unknown"])]

        texts = [
            normalize_analysis_text(t)
            for t in subset["main_text"].fillna("").tolist()
            if normalize_analysis_text(t)
        ]
        lang_stats = _language_stats(subset) if len(subset) else {
            "n_pages_de": 0, "n_pages_en": 0, "n_pages_other": 0, "n_pages_unknown": 0,
            "tokens_de": 0, "tokens_en": 0, "tokens_other": 0, "tokens_unknown": 0,
            "primary_language_by_tokens": "unknown",
        }
        rows.append({
            "run_id": obs["run_id"],
            "firm_id": obs["firm_id"],
            "company": obs["company"],
            "relative_timepoint": obs["relative_timepoint"],
            "observation_recommendation": obs["observation_recommendation"],
            "branding_text": "\n\n".join(texts) if texts else None,
            "branding_word_count": int(subset["word_count"].fillna(0).sum()) if len(subset) else 0,
            "branding_token_count": int(subset["token_count"].fillna(0).sum()) if len(subset) else 0,
            "source_page_count": len(subset),
            "source_page_urls_json": json_list(
                subset["original_archived_url"].dropna().astype(str).tolist()
            ) if len(subset) else "[]",
            "source_page_categories_json": json_list(
                subset["page_category"].dropna().astype(str).tolist()
            ) if len(subset) else "[]",
            "n_duplicate_pages_within_observation": obs.get("n_duplicate_pages_within_observation"),
            "duplicate_tokens_removed": obs.get("duplicate_tokens_removed"),
            "duplicate_words_removed": obs.get("duplicate_words_removed"),
            "n_unique_branding_pages": obs.get("n_unique_branding_pages"),
            "deduplication_applied": obs.get("deduplication_applied"),
            **lang_stats,
            "german_text_analysis_eligible": obs.get("german_text_analysis_eligible"),
            "german_text_analysis_exclusion_reason": obs.get("german_text_analysis_exclusion_reason"),
            "corpus_language_scope": corpus_language_scope,
            "text_analysis_eligible": True,
            "text_analysis_quality_band": obs["text_analysis_quality_band"],
            "text_analysis_exclusion_reason": obs.get("text_analysis_exclusion_reason"),
        })
    df = pd.DataFrame(rows)
    for col in BRANDING_CORPUS_OBSERVATION_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BRANDING_CORPUS_OBSERVATION_COLUMNS] if not df.empty else pd.DataFrame(columns=BRANDING_CORPUS_OBSERVATION_COLUMNS)


def build_duplicate_summary(pages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dups = pages[pages["duplicate_content_flag"].fillna(False).astype(bool)]
    for _, page in dups.iterrows():
        rows.append({
            "run_id": page.get("run_id"),
            "firm_id": page.get("firm_id"),
            "company": page.get("company"),
            "relative_timepoint": page.get("relative_timepoint"),
            "duplicate_group_id": page.get("duplicate_group_id"),
            "duplicate_reason": page.get("duplicate_reason"),
            "canonical_page_url": page.get("duplicate_of_page_id"),
            "duplicate_page_url": page.get("original_archived_url"),
            "normalized_content_hash": page.get("normalized_content_hash"),
            "tokens_removed": page.get("token_count"),
            "words_removed": page.get("word_count"),
        })
    df = pd.DataFrame(rows)
    for col in DUPLICATE_SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[DUPLICATE_SUMMARY_COLUMNS] if not df.empty else pd.DataFrame(columns=DUPLICATE_SUMMARY_COLUMNS)


def build_crawl_priority_summary(
    snapshots: pd.DataFrame,
    crawl_summaries: list[dict],
) -> pd.DataFrame:
    by_capture = {
        (str(r["firm_id"]), str(r.get("archive_timestamp"))): r for r in crawl_summaries
    }
    rows = []
    for _, snap in snapshots.iterrows():
        key = (str(snap["firm_id"]), str(snap.get("archive_timestamp")))
        s = by_capture.get(key, {})
        rows.append({
            "run_id": snap.get("run_id"),
            "firm_id": snap.get("firm_id"),
            "company": snap.get("company"),
            "relative_timepoint": snap.get("relative_timepoint"),
            "archive_timestamp": snap.get("archive_timestamp"),
            "n_high_priority_pages_discovered": s.get("n_high_priority_pages_discovered", 0),
            "n_high_priority_pages_fetched": s.get("n_high_priority_pages_fetched", 0),
            "n_high_priority_pages_missing": s.get("n_high_priority_pages_missing", 0),
            "n_secondary_pages_fetched": s.get("n_secondary_pages_fetched", 0),
            "n_broad_pages_fetched": s.get("n_broad_pages_fetched", 0),
            "n_foreign_pages_deprioritized": s.get("n_foreign_pages_deprioritized", 0),
            "crawl_limit_reached": s.get("crawl_limit_reached", False),
            "unused_reserved_slots": s.get("unused_reserved_slots", 0),
            "pages_fetched": s.get("pages_fetched", 0),
        })
    df = pd.DataFrame(rows)
    for col in CRAWL_PRIORITY_SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CRAWL_PRIORITY_SUMMARY_COLUMNS]
