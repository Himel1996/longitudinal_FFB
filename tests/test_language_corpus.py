"""Tests for hybrid language path prioritization and corpus inclusion."""

import pandas as pd

from ffb_webminer.config import AnalysisConfig
from ffb_webminer.crawl.language_paths import infer_path_language
from ffb_webminer.pipeline.corpus_outputs import (
    build_branding_corpus_observations,
    build_branding_corpus_pages,
    build_observation_text_summary,
)
from ffb_webminer.quality.language_inclusion import annotate_language_inclusion


def test_german_path_hint():
    h = infer_path_language("https://example.com/de/unternehmen")
    assert h.path_language_hint == "de"
    assert h.path_language_priority == "preferred_german"


def test_english_path_deprioritized():
    h = infer_path_language("https://example.com/en/about")
    assert h.path_language_hint == "en"
    assert h.path_language_priority == "foreign_language_deprioritized"


def test_root_preferred_german():
    h = infer_path_language("https://example.com/")
    assert h.path_language_priority == "preferred_german"


def test_language_inclusion_cases():
    cfg = AnalysisConfig()
    pages = annotate_language_inclusion(
        [
            {
                "original_archived_url": "https://example.com/de/ueber-uns",
                "usable_for_analysis": True,
                "text_language": "de",
                "text_language_confidence": 0.95,
                "character_count": 200,
                "main_text": "Familienunternehmen",
            },
            {
                "original_archived_url": "https://example.com/en/about",
                "usable_for_analysis": True,
                "text_language": "en",
                "text_language_confidence": 0.99,
                "character_count": 200,
                "main_text": "Family business",
            },
            {
                "original_archived_url": "https://example.com/en/about",
                "usable_for_analysis": True,
                "text_language": "de",
                "text_language_confidence": 0.9,
                "character_count": 200,
                "main_text": "Trotz englischem Pfad deutscher Text",
            },
            {
                "original_archived_url": "https://example.com/",
                "usable_for_analysis": True,
                "text_language": "de",
                "text_language_confidence": 0.9,
                "character_count": 200,
            },
            {
                "original_archived_url": "https://example.com/x",
                "usable_for_analysis": True,
                "text_language": "unknown",
                "text_language_confidence": 0.1,
                "character_count": 20,
            },
            {
                "original_archived_url": "https://example.com/mixed",
                "usable_for_analysis": True,
                "text_language": "mixed",
                "text_language_confidence": 0.5,
                "character_count": 300,
                "german_token_share": 0.8,
            },
        ],
        cfg,
    )
    assert pages[0]["german_corpus_eligible"] is True
    assert pages[1]["german_corpus_eligible"] is False
    assert pages[1]["language_exclusion_reason"].startswith("non_german")
    assert pages[2]["german_corpus_eligible"] is True  # misleading path, German text
    assert pages[3]["german_corpus_eligible"] is True
    assert pages[4]["german_corpus_eligible"] is False
    assert pages[4]["language_exclusion_reason"] == "unknown_short_text"
    assert pages[5]["german_corpus_eligible"] is True


def test_language_corpora_separation():
    snapshots = pd.DataFrame([
        {
            "run_id": "r1",
            "firm_id": "1",
            "company": "Firm A",
            "relative_timepoint": "pre_event",
            "target_date": "2022-07-01",
            "selected_capture_date": "2022-07-07",
            "snapshot_status": "selected",
            "observation_recommendation": "include",
            "analysis_eligible": True,
        }
    ])
    pages = pd.DataFrame([
        {
            "run_id": "r1",
            "firm_id": "1",
            "company": "Firm A",
            "relative_timepoint": "pre_event",
            "target_date": "2022-07-01",
            "selected_capture_date": "2022-07-07",
            "http_status": 200,
            "fetch_error": None,
            "usable_for_analysis": True,
            "branding_corpus_eligible": True,
            "german_corpus_eligible": True,
            "governance_metadata_eligible": False,
            "page_category": "homepage",
            "duplicate_content_flag": False,
            "word_count": 120,
            "token_count": 120,
            "text_language": "de",
            "detected_language": "de",
            "main_text": "familiengeführtes unternehmen mit werten und tradition",
            "original_archived_url": "https://example.com/",
            "path": "/",
        },
        {
            "run_id": "r1",
            "firm_id": "1",
            "company": "Firm A",
            "relative_timepoint": "pre_event",
            "target_date": "2022-07-01",
            "selected_capture_date": "2022-07-07",
            "http_status": 200,
            "fetch_error": None,
            "usable_for_analysis": True,
            "branding_corpus_eligible": True,
            "german_corpus_eligible": False,
            "language_exclusion_reason": "non_german_detected:en",
            "governance_metadata_eligible": False,
            "page_category": "company_about",
            "duplicate_content_flag": False,
            "word_count": 80,
            "token_count": 80,
            "text_language": "en",
            "detected_language": "en",
            "main_text": "family owned company values",
            "original_archived_url": "https://example.com/en/about",
            "path": "/en/about",
        },
    ])
    gov_obs = pd.DataFrame([
        {
            "run_id": "r1",
            "firm_id": "1",
            "company": "Firm A",
            "relative_timepoint": "pre_event",
            "target_date": "2022-07-01",
            "selected_capture_date": "2022-07-07",
            "impressum_available": False,
            "governance_metadata_text": None,
            "detected_legal_representatives": None,
            "detected_legal_entity": None,
            "detected_parent_company": None,
            "governance_metadata_quality": "low",
            "governance_metadata_source_urls": None,
        }
    ])
    summary = build_observation_text_summary(snapshots, pages, gov_obs, AnalysisConfig())
    assert summary.iloc[0]["n_pages_de"] == 1
    assert summary.iloc[0]["n_pages_en"] == 1
    assert summary.iloc[0]["tokens_de"] == 120
    assert summary.iloc[0]["tokens_en"] == 80

    all_pages = build_branding_corpus_pages(pages, summary, language_scope="all")
    de_pages = build_branding_corpus_pages(
        pages, summary, language_scope="de", require_german_observation=True
    )
    assert len(all_pages) == 2
    assert len(de_pages) == 1
    assert de_pages.iloc[0]["detected_language"] == "de"

    primary = build_branding_corpus_observations(
        summary,
        de_pages,
        primary_only=True,
        corpus_language_scope="de",
        use_german_eligibility=True,
    )
    assert len(primary) == 1
    assert primary.iloc[0]["branding_token_count"] == 120
    assert "family owned" not in (primary.iloc[0]["branding_text"] or "")
