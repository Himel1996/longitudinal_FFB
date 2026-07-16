"""Observation-level corpus and governance outputs."""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from ffb_webminer.config import AnalysisConfig
from ffb_webminer.governance.extraction import extract_governance_metadata, json_list, merge_governance_texts
from ffb_webminer.pipeline.schemas import (
    BRANDING_CORPUS_OBSERVATION_COLUMNS,
    BRANDING_CORPUS_PAGE_COLUMNS,
    GOVERNANCE_METADATA_OBSERVATION_COLUMNS,
    GOVERNANCE_METADATA_PAGE_COLUMNS,
    OBSERVATION_TEXT_SUMMARY_COLUMNS,
)
from ffb_webminer.extract.text_utils import normalize_analysis_text
from ffb_webminer.quality.checks import as_bool, page_fetch_success


def build_governance_metadata_pages(pages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, page in pages[pages["governance_metadata_eligible"].fillna(False)].iterrows():
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
            "impressum_available": bool(len(subset)),
            "governance_metadata_text": merged,
            "detected_legal_representatives": reps,
            "detected_legal_entity": entities,
            "detected_parent_company": parents,
            "governance_metadata_quality": quality,
            "governance_metadata_source_urls": json_list(subset["original_archived_url"].dropna().astype(str).tolist()),
        })
    df = pd.DataFrame(rows)
    for col in GOVERNANCE_METADATA_OBSERVATION_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[GOVERNANCE_METADATA_OBSERVATION_COLUMNS]


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
        legal_technical = subset[subset["page_category"].isin([
            "privacy_policy", "terms_conditions", "cookie_notice", "legal_other", "technical_system", "search_archive"
        ])]
        duplicates = int(subset["duplicate_content_flag"].fillna(False).sum())
        usable_pages = subset[subset["usable_for_analysis"].fillna(False)]
        all_words = int(usable_pages["word_count"].fillna(0).sum())
        all_tokens = int(usable_pages["token_count"].fillna(0).sum())
        branding_words = int(branding_pages["word_count"].fillna(0).sum())
        branding_tokens = int(branding_pages["token_count"].fillna(0).sum())
        gov = gov_lookup.get(key)
        gov_words = len(normalize_analysis_text(gov.get("governance_metadata_text")).split()) if gov is not None else 0

        lang_counter = Counter()
        unknown_lang = 0
        for _, page in branding_pages.iterrows():
            lang = page.get("text_language") or "unknown"
            tokens = int(page.get("token_count") or 0)
            if lang == "unknown":
                unknown_lang += 1
            lang_counter[lang] += tokens if tokens > 0 else 1
        primary_lang = max(lang_counter.items(), key=lambda kv: kv[1])[0] if lang_counter else "unknown"

        exclusion_reason = None
        eligible = bool(snap.get("analysis_eligible"))
        if snap.get("snapshot_status") != "selected":
            exclusion_reason = "no_valid_snapshot"
            eligible = False
        elif snap.get("observation_recommendation") == "exclude_duplicate_capture":
            exclusion_reason = "duplicate_capture"
            eligible = False
        elif not snap.get("analysis_eligible"):
            exclusion_reason = "observation_excluded_temporally"
            eligible = False
        elif len(branding_pages) < analysis_cfg.min_branding_pages:
            exclusion_reason = "no_branding_pages"
            eligible = False
        elif branding_tokens < analysis_cfg.min_branding_tokens:
            exclusion_reason = "insufficient_branding_tokens"
            eligible = False

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
            "n_impressum_pages": int(subset["page_category"].eq("impressum").sum()),
            "n_legal_technical_pages": len(legal_technical),
            "n_duplicate_pages": duplicates,
            "total_word_count_all_usable_pages": all_words,
            "total_token_count_all_usable_pages": all_tokens,
            "branding_word_count": branding_words,
            "branding_token_count": branding_tokens,
            "governance_metadata_word_count": gov_words,
            "detected_primary_language": primary_lang,
            "language_distribution_json": json.dumps(dict(lang_counter), ensure_ascii=False) if lang_counter else None,
            "n_pages_language_unknown": unknown_lang,
            "text_analysis_eligible": eligible,
            "text_analysis_exclusion_reason": exclusion_reason,
            "text_analysis_quality_band": quality_band,
        })
    df = pd.DataFrame(rows)
    for col in OBSERVATION_TEXT_SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[OBSERVATION_TEXT_SUMMARY_COLUMNS]


def build_branding_corpus_pages(pages: pd.DataFrame, observation_summary: pd.DataFrame) -> pd.DataFrame:
    elig = {
        (str(r["firm_id"]), r["relative_timepoint"]): (
            r["text_analysis_eligible"],
            r["text_analysis_quality_band"],
            r["observation_recommendation"],
        )
        for _, r in observation_summary.iterrows()
    }
    rows = []
    for _, page in pages.iterrows():
        key = (str(page["firm_id"]), page["relative_timepoint"])
        text_eligible, quality_band, recommendation = elig.get(key, (False, "ineligible", None))
        if not (as_bool(page.get("branding_corpus_eligible")) and as_bool(page.get("usable_for_analysis"))):
            continue
        if recommendation not in {"include", "sensitivity_analysis"}:
            continue
        row = page.to_dict()
        row["text_analysis_eligible"] = text_eligible
        row["text_analysis_quality_band"] = quality_band
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in BRANDING_CORPUS_PAGE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BRANDING_CORPUS_PAGE_COLUMNS]


def build_branding_corpus_observations(
    observation_summary: pd.DataFrame,
    branding_pages: pd.DataFrame,
    primary_only: bool | None = None,
) -> pd.DataFrame:
    rows = []
    summary = observation_summary.copy()
    if primary_only is True:
        summary = summary[summary["observation_recommendation"] == "include"]
    elif primary_only is False:
        summary = summary[summary["observation_recommendation"].isin(["include", "sensitivity_analysis"])]
    for _, obs in summary.iterrows():
        subset = branding_pages[
            (branding_pages["firm_id"].astype(str) == str(obs["firm_id"]))
            & (branding_pages["relative_timepoint"] == obs["relative_timepoint"])
        ].sort_values(["page_category", "path"])
        texts = [normalize_analysis_text(t) for t in subset["main_text"].fillna("").tolist() if normalize_analysis_text(t)]
        rows.append({
            "run_id": obs["run_id"],
            "firm_id": obs["firm_id"],
            "company": obs["company"],
            "relative_timepoint": obs["relative_timepoint"],
            "branding_text": "\n\n".join(texts) if texts else None,
            "branding_word_count": int(subset["word_count"].fillna(0).sum()),
            "branding_token_count": int(subset["token_count"].fillna(0).sum()),
            "source_page_count": len(subset),
            "source_page_urls_json": json_list(subset["original_archived_url"].dropna().astype(str).tolist()),
            "source_page_categories_json": json_list(subset["page_category"].dropna().astype(str).tolist()),
            "text_analysis_eligible": obs["text_analysis_eligible"],
            "text_analysis_quality_band": obs["text_analysis_quality_band"],
        })
    df = pd.DataFrame(rows)
    for col in BRANDING_CORPUS_OBSERVATION_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BRANDING_CORPUS_OBSERVATION_COLUMNS]
