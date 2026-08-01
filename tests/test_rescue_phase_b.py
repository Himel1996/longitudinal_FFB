"""Tests for Phase B rescue orchestration (no network / no core-rule changes)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ffb_webminer.rescue.audit import assert_parent_unchanged, audit_non_targeted_immutability, guard_release_destination
from ffb_webminer.rescue.candidates import (
    PERIOD_TO_TIMEPOINTS,
    build_alias_map,
    expand_seed_variants,
    load_raw_candidates,
    normalize_candidates,
)
from ffb_webminer.rescue.compare import decide_rescue
from ffb_webminer.rescue.paths import PARENT_RELEASE_NAME, rescue_layout
from ffb_webminer.rescue.special_cases import entity_change_firm_ids, force_sensitivity_firm_ids
from ffb_webminer.rescue.timestamps import normalize_archive_timestamp
from ffb_webminer.rescue.transport import TRANSPORT_FAILURE_RESUMABLE, classify_fetch_error


ROOT = Path(__file__).resolve().parents[1]


def test_period_mappings_cover_pre_post_all():
    assert "pre_event" in PERIOD_TO_TIMEPOINTS["pre"]
    assert "post_event" in PERIOD_TO_TIMEPOINTS["post"]
    assert "event" in PERIOD_TO_TIMEPOINTS["all"]


def test_expand_seed_variants_scheme_and_www():
    variants = expand_seed_variants("https://www.example.de/de/")
    assert "https://www.example.de/de/" in variants
    assert any(v.startswith("http://") for v in variants)
    assert any("://example.de/" in v for v in variants)


def test_normalize_rejects_unknown_firm():
    raw = pd.DataFrame(
        [
            {
                "firm_id": "999",
                "company": "X",
                "period": "all",
                "seed_url": "https://example.de/",
                "priority": "1",
                "rescue_status": "strong",
                "assessment": "t",
                "archive_evidence": "e",
            }
        ]
    )
    _, report = normalize_candidates(raw, nonready_firm_ids={"999"}, known_firm_ids={"1"})
    assert report["safe_to_execute"] is False
    assert "999" in report["unknown_firm_ids"]


def test_normalize_rejects_ambiguous_period():
    raw = pd.DataFrame(
        [
            {
                "firm_id": "2",
                "company": "X",
                "period": "sometime",
                "seed_url": "https://example.de/",
                "priority": "1",
                "rescue_status": "strong",
                "assessment": "t",
                "archive_evidence": "e",
            }
        ]
    )
    _, report = normalize_candidates(raw, nonready_firm_ids={"2"}, known_firm_ids={"2"})
    assert report["safe_to_execute"] is False
    assert report["ambiguous_period_mappings"]


def test_normalize_rejects_invalid_url():
    raw = pd.DataFrame(
        [
            {
                "firm_id": "2",
                "company": "X",
                "period": "all",
                "seed_url": "not-a-url",
                "priority": "1",
                "rescue_status": "strong",
                "assessment": "t",
                "archive_evidence": "e",
            }
        ]
    )
    _, report = normalize_candidates(raw, nonready_firm_ids={"2"}, known_firm_ids={"2"})
    assert report["safe_to_execute"] is False
    assert report["invalid_urls"]


def test_aliases_restricted_to_period_timepoints():
    raw = pd.DataFrame(
        [
            {
                "firm_id": "2",
                "company": "X",
                "period": "pre",
                "seed_url": "https://example.de/",
                "priority": "1",
                "rescue_status": "strong",
                "assessment": "historical domain migration",
                "archive_evidence": "e",
            }
        ]
    )
    cands, report = normalize_candidates(raw, nonready_firm_ids={"2"}, known_firm_ids={"2"})
    assert report["safe_to_execute"] is True
    alias = build_alias_map(cands)
    assert ("2", "pre_event") in alias
    assert ("2", "post_event") not in alias
    assert all(c.firm_id == "2" for lst in alias.values() for c in lst)


def test_historical_and_locale_classification():
    raw = pd.DataFrame(
        [
            {
                "firm_id": "2",
                "company": "X",
                "period": "all",
                "seed_url": "https://www.peter-lacke.com/",
                "priority": "1",
                "rescue_status": "strong",
                "assessment": "Domain migration from peter-lacke.de",
                "archive_evidence": "e",
            },
            {
                "firm_id": "10",
                "company": "Y",
                "period": "all",
                "seed_url": "https://www.bbraun.de/de.html",
                "priority": "1",
                "rescue_status": "strong",
                "assessment": "German locale seed",
                "archive_evidence": "e",
            },
        ]
    )
    cands, report = normalize_candidates(
        raw, nonready_firm_ids={"2", "10"}, known_firm_ids={"2", "10"}
    )
    assert report["safe_to_execute"] is True
    types = {c.firm_id: c.candidate_type for c in cands}
    assert types["2"] in {"historical_domain", "migrated_domain"}
    assert types["10"] == "locale_path"


def test_real_candidate_csv_validates():
    path = ROOT / "data/input/full_sample_url_rescue_candidates.csv"
    parent = ROOT / "data/releases/full_sample_v1/data"
    known = set(pd.read_csv(parent / "firms.csv", dtype=str)["firm_id"].astype(str))
    cov = pd.read_csv(parent / "firm_longitudinal_coverage.csv", dtype=str)
    ready = set(
        cov.loc[cov["german_longitudinal_ready"].astype(str).str.upper() == "TRUE", "firm_id"].astype(str)
    )
    nonready = known - ready
    raw = load_raw_candidates(path)
    cands, report = normalize_candidates(raw, nonready_firm_ids=nonready, known_firm_ids=known)
    assert report["safe_to_execute"] is True
    assert len(report["firms_represented"]) == 19
    assert len(cands) > 0


def test_original_full_sample_config_unchanged():
    text = (ROOT / "config/full_sample.yaml").read_text(encoding="utf-8")
    assert "tolerance_days: 548" in text
    assert "min_branding_tokens: 100" in text


def test_parent_release_protection():
    layout = rescue_layout(ROOT)
    assert layout["parent_release"].name == PARENT_RELEASE_NAME
    with pytest.raises(RuntimeError):
        guard_release_destination(layout["parent_release"], ROOT)
    assert_parent_unchanged(layout["parent_data"])


def test_non_targeted_immutability_detects_drift():
    parent = pd.DataFrame(
        [
            {
                "firm_id": "1",
                "relative_timepoint": "pre_event",
                "observation_id": "a",
                "archive_timestamp": "1",
                "tokens_de": "10",
            }
        ]
    )
    rescue = parent.copy()
    rescue.loc[0, "tokens_de"] = "99"
    with pytest.raises(RuntimeError):
        audit_non_targeted_immutability(parent_obs=parent, rescue_obs=rescue, targeted_firm_ids={"2"})


def test_replacement_policy_better_german():
    original_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "tokens_de": 50,
            "n_pages_de": 1,
            "observation_recommendation": "include",
        }
    )
    rescue_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "tokens_de": 400,
            "n_pages_de": 3,
            "observation_recommendation": "include",
            "branding_token_count": 400,
        }
    )
    original_snap = pd.Series(
        {"snapshot_status": "selected", "temporal_fit_quality": "high", "temporal_distance_days": 10}
    )
    rescue_snap = pd.Series(
        {
            "snapshot_status": "selected",
            "temporal_fit_quality": "high",
            "temporal_distance_days": 12,
            "canonical_original_url": "https://example.de/",
        }
    )
    out = decide_rescue(
        firm_id="10",
        original_obs=original_obs,
        rescue_obs=rescue_obs,
        original_snap=original_snap,
        rescue_snap=rescue_snap,
        entity_change_flag=False,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
    )
    assert out["rescue_decision"] == "replace_with_rescue"


def test_weaker_temporal_becomes_sensitivity():
    original_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "tokens_de": 200,
            "n_pages_de": 2,
            "observation_recommendation": "include",
        }
    )
    rescue_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "tokens_de": 500,
            "n_pages_de": 4,
            "observation_recommendation": "include",
            "branding_token_count": 500,
        }
    )
    original_snap = pd.Series(
        {"snapshot_status": "selected", "temporal_fit_quality": "high", "temporal_distance_days": 5}
    )
    rescue_snap = pd.Series(
        {"snapshot_status": "selected", "temporal_fit_quality": "low", "temporal_distance_days": 200}
    )
    out = decide_rescue(
        firm_id="10",
        original_obs=original_obs,
        rescue_obs=rescue_obs,
        original_snap=original_snap,
        rescue_snap=rescue_snap,
        entity_change_flag=False,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
    )
    assert out["rescue_decision"] == "add_as_sensitivity_alternative"


def test_msf_threshold_not_auto_promoted_below():
    rescue_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "tokens_de": 80,
            "n_pages_de": 2,
            "observation_recommendation": "include",
            "branding_token_count": 80,
            "german_text_analysis_exclusion_reason": "",
        }
    )
    rescue_snap = pd.Series(
        {"snapshot_status": "selected", "temporal_fit_quality": "moderate", "temporal_distance_days": 30}
    )
    out = decide_rescue(
        firm_id="5",
        original_obs=None,
        rescue_obs=rescue_obs,
        original_snap=None,
        rescue_snap=rescue_snap,
        entity_change_flag=False,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
    )
    assert out["rescue_decision"] in {"rejected_insufficient_text", "remain_unavailable", "retain_original"}


def test_freudenberg_stihl_force_sensitivity_ids():
    assert "21" in force_sensitivity_firm_ids()
    assert "22" in force_sensitivity_firm_ids()


def test_viessmann_oetker_entity_metadata():
    assert "24" in entity_change_firm_ids()
    assert "30" in entity_change_firm_ids()
    rescue_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "tokens_de": 400,
            "n_pages_de": 3,
            "observation_recommendation": "include",
            "branding_token_count": 400,
        }
    )
    rescue_snap = pd.Series(
        {
            "snapshot_status": "selected",
            "temporal_fit_quality": "high",
            "temporal_distance_days": 20,
            "canonical_original_url": "https://www.viessmann.family/",
            "rescue_domain": "viessmann.family",
        }
    )
    out = decide_rescue(
        firm_id="24",
        original_obs=None,
        rescue_obs=rescue_obs,
        original_snap=None,
        rescue_snap=rescue_snap,
        entity_change_flag=True,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
    )
    assert out["entity_change_flag"] is True
    assert out["rescue_decision"] in {"add_as_sensitivity_alternative", "manual_review_required"}


def test_transport_failure_classification():
    assert classify_fetch_error("SSL: UNEXPECTED_EOF_WHILE_READING") == TRANSPORT_FAILURE_RESUMABLE
    assert classify_fetch_error("boom", http_status=429) == TRANSPORT_FAILURE_RESUMABLE
    assert classify_fetch_error("page not in archive") is None
    out = decide_rescue(
        firm_id="10",
        original_obs=None,
        rescue_obs=None,
        original_snap=None,
        rescue_snap=None,
        entity_change_flag=False,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
        transport_failure=True,
    )
    assert out["rescue_decision"] == TRANSPORT_FAILURE_RESUMABLE


def test_timestamp_float_artifact_normalized_in_rescue_helper():
    assert normalize_archive_timestamp("20190704175027.0") == "20190704175027"
    assert normalize_archive_timestamp(20190704175027.0) == "20190704175027"


def test_coverage_definitions_semantics():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_full_sample_rescue", ROOT / "scripts/run_full_sample_rescue.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    firms = pd.DataFrame([{"firm_id": "1", "company": "A", "event_year": "2010", "event_type": "x"}])
    obs = pd.DataFrame(
        [
            {
                "firm_id": "1",
                "relative_timepoint": "pre_event",
                "german_text_analysis_eligible": True,
                "text_analysis_eligible": True,
            },
            {
                "firm_id": "1",
                "relative_timepoint": "post_event",
                "german_text_analysis_eligible": True,
                "text_analysis_eligible": True,
            },
        ]
    )
    primary = pd.DataFrame(
        [{"firm_id": "1", "relative_timepoint": "pre_event"}, {"firm_id": "1", "relative_timepoint": "post_event"}]
    )
    sens = pd.DataFrame(columns=["firm_id", "relative_timepoint"])
    cov = mod.build_coverage(firms, obs, primary, sens, pd.DataFrame(), targeted=set())
    assert cov.iloc[0]["german_longitudinal_ready_primary"] == "TRUE"
    assert cov.iloc[0]["german_longitudinal_ready_extended"] == "TRUE"


def test_cli_validate_dry_run_no_network():
    import subprocess

    proc = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/run_full_sample_rescue.py"),
            "--config",
            "config/full_sample_rescue.yaml",
            "--stage",
            "validate",
            "--no-network",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["stage"] == "validate"
    assert payload["safe_to_execute"] is True
    assert payload["no_network"] is True
    assert len(payload["targeted_firms"]) == 19
