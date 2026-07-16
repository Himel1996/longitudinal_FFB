import pandas as pd

from ffb_webminer.config import AnalysisConfig
from ffb_webminer.pipeline.corpus_outputs import (
    build_branding_corpus_observations,
    build_branding_corpus_pages,
    build_governance_metadata_observations,
    build_governance_metadata_pages,
    build_observation_text_summary,
)
from ffb_webminer.quality.checks import summarize_snapshot_pages


def _snapshots():
    return pd.DataFrame([
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


def _pages():
    return pd.DataFrame([
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
            "governance_metadata_eligible": False,
            "page_category": "homepage",
            "duplicate_content_flag": False,
            "word_count": 120,
            "token_count": 120,
            "text_language": "de",
            "main_text": "familiengeführtes unternehmen mit werten und tradition",
            "original_archived_url": "https://example.com/",
            "path": "/",
            "page_priority_reason": "homepage",
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
            "branding_corpus_eligible": False,
            "governance_metadata_eligible": True,
            "page_category": "impressum",
            "duplicate_content_flag": False,
            "word_count": 40,
            "token_count": 40,
            "text_language": "de",
            "main_text": "Geschäftsführer Max Muster GmbH Musterstraße 1 12345 Bonn",
            "extracted_text": "Geschäftsführer Max Muster GmbH Musterstraße 1 12345 Bonn",
            "document_title": "Impressum",
            "wayback_replay_url": "https://web.archive.org/web/1/example",
            "original_archived_url": "https://example.com/impressum",
            "path": "/impressum",
            "page_priority_reason": "branding_score:1",
        },
    ])


def test_quality_summary_consistency():
    summary = summarize_snapshot_pages(_pages().to_dict("records"), "r1", "1", 1, "Firm A", "pre_event", 2022, "selected")
    assert summary["pages_attempted"] == 2
    assert summary["pages_fetch_success"] >= summary["pages_extraction_usable"]
    assert summary["pages_extraction_usable"] >= summary["pages_branding_eligible"]


def test_quality_summary_handles_nan_fetch_error():
    import math

    pages = pd.DataFrame([
        {
            "http_status": 200,
            "fetch_error": math.nan,
            "usable_for_analysis": True,
            "branding_corpus_eligible": True,
            "page_category": "homepage",
            "duplicate_content_flag": False,
            "character_count": 120,
        }
    ])
    summary = summarize_snapshot_pages(pages.to_dict("records"), "r1", "1", 1, "Firm A", "pre_event", 2022, "selected")
    assert summary["pages_fetch_success"] == 1
    assert summary["pages_extraction_usable"] == 1


def test_corpus_and_governance_outputs_traceable():
    snapshots = _snapshots()
    pages = _pages()
    gov_pages = build_governance_metadata_pages(pages)
    assert len(gov_pages) == 1
    assert gov_pages.iloc[0]["original_archived_url"] == "https://example.com/impressum"

    gov_obs = build_governance_metadata_observations(snapshots, gov_pages)
    obs = build_observation_text_summary(snapshots, pages, gov_obs, AnalysisConfig())
    branding_pages = build_branding_corpus_pages(pages, obs)
    assert len(branding_pages) == 1
    assert branding_pages.iloc[0]["page_category"] == "homepage"

    branding_obs = build_branding_corpus_observations(obs, branding_pages)
    assert len(branding_obs) == 1
    assert branding_obs.iloc[0]["branding_token_count"] == 120
