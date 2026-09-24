"""Offline final-assembly regression checks (no network)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "data" / "releases" / "full_sample_v1_1_rescue_final" / "data"
PARENT = ROOT / "data" / "releases" / "full_sample_v1" / "data"
INTERIM = ROOT / "data" / "interim" / "full_sample_rescue"
EXPECTED_SHA = "c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27"
RESCUE = {
    "10", "2", "11", "12", "14", "15", "16", "17", "18", "19",
    "20", "23", "25", "21", "22", "24", "5", "27", "30",
}


@pytest.mark.skipif(not FINAL.exists(), reason="final release not assembled")
def test_cumulative_decision_uniqueness():
    dec = pd.read_csv(FINAL / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    assert set(dec.firm_id.astype(str)) == RESCUE
    assert not dec.duplicated(subset=["firm_id", "relative_timepoint"]).any()
    assert len(dec) == 87


@pytest.mark.skipif(not FINAL.exists(), reason="final release not assembled")
def test_bbraun_preservation():
    dec = pd.read_csv(FINAL / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    bb = dec[dec.firm_id.astype(str) == "10"]
    assert len(bb) == 5
    assert (bb.rescue_decision == "replace_with_rescue").all()
    assert abs(bb.rescue_branding_tokens_de.astype(float).sum() - 18028) < 1
    primary = pd.read_csv(FINAL / "full_sample_branding_corpus_observations_primary.csv", dtype=str)
    p10 = primary[primary.firm_id.astype(str) == "10"]
    assert len(p10) == 5
    assert abs(p10.tokens_de.astype(float).sum() - 18028) < 1
    cov = pd.read_csv(FINAL / "firm_longitudinal_coverage.csv", dtype=str)
    row = cov[cov.firm_id.astype(str) == "10"].iloc[0]
    assert row.german_longitudinal_ready_primary == "TRUE"
    assert row.german_longitudinal_ready_extended == "TRUE"


@pytest.mark.skipif(not FINAL.exists(), reason="final release not assembled")
def test_parent_only_immutability_sample():
    parent = pd.read_csv(PARENT / "full_sample_observation_text_summary.csv", dtype=str)
    final = pd.read_csv(FINAL / "full_sample_observation_text_summary.csv", dtype=str)
    non = sorted(set(parent.firm_id.astype(str)) - RESCUE, key=int)
    cols = [
        c
        for c in [
            "firm_id",
            "relative_timepoint",
            "tokens_de",
            "german_text_analysis_eligible",
            "observation_recommendation",
            "archive_timestamp",
        ]
        if c in parent.columns and c in final.columns
    ]
    for fid in non:
        p = parent[parent.firm_id.astype(str) == fid][cols].sort_values("relative_timepoint").reset_index(drop=True)
        f = final[final.firm_id.astype(str) == fid][cols].sort_values("relative_timepoint").reset_index(drop=True)
        assert p.equals(f), f"drift firm {fid}"


@pytest.mark.skipif(not FINAL.exists(), reason="final release not assembled")
def test_parent_sha_and_german_primary_purity():
    import hashlib

    sha = hashlib.sha256(
        (PARENT / "full_sample_branding_corpus_observations_primary.csv").read_bytes()
    ).hexdigest()
    assert sha == EXPECTED_SHA
    primary = pd.read_csv(FINAL / "full_sample_branding_corpus_observations_primary.csv", dtype=str)
    if "german_text_analysis_eligible" in primary.columns:
        assert primary.german_text_analysis_eligible.astype(str).str.lower().isin(["true", "1"]).all()


@pytest.mark.skipif(not FINAL.exists(), reason="final release not assembled")
def test_special_case_flags_preserved():
    dec = pd.read_csv(FINAL / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    assert (dec[dec.firm_id == "30"].entity_change_flag.astype(str).str.lower() == "true").any()
    assert (dec[dec.firm_id == "24"].entity_change_flag.astype(str).str.lower() == "true").any()
    assert (dec[dec.firm_id == "30"].rescue_decision == "manual_review_required").sum() >= 1
    # MSF retained post_event (threshold / not better) documented in decisions
    msf = dec[dec.firm_id == "5"]
    assert (msf.rescue_decision == "retain_original").any()


@pytest.mark.skipif(not (INTERIM / "rescue_comparison_decisions_FINAL.csv").exists(), reason="no FINAL decisions")
def test_batch_decision_reconciliation_counts():
    final = pd.read_csv(INTERIM / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    # each batch backup firm set present
    assert set(final.loc[final.source_batch == "B02", "firm_id"]) == {"14", "15", "16"}
    assert set(final.loc[final.source_batch == "B06", "firm_id"]) == {"5", "27", "30"}
    assert set(final.loc[final.source_batch == "B_BRAUN_SMOKE", "firm_id"]) == {"10"}
