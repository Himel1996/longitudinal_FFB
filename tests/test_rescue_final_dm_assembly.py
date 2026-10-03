"""Offline definitive dm-final release regression checks (no network)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FINAL_DM = ROOT / "data" / "releases" / "full_sample_v1_1_rescue_final_dm" / "data"
BASE_FINAL = ROOT / "data" / "releases" / "full_sample_v1_1_rescue_final" / "data"
PARENT = ROOT / "data" / "releases" / "full_sample_v1" / "data"
EXPECTED_SHA = "c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27"
PRIOR_RESCUE = {
    "10", "2", "11", "12", "14", "15", "16", "17", "18", "19",
    "20", "23", "25", "21", "22", "24", "5", "27", "30",
}
ALL_RESCUE = PRIOR_RESCUE | {"8"}


@pytest.mark.skipif(not FINAL_DM.exists(), reason="dm final release not assembled")
def test_decision_count_and_dm_batch():
    dec = pd.read_csv(FINAL_DM / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    assert len(dec) == 89
    assert set(dec.firm_id.astype(str)) == ALL_RESCUE
    assert not dec.duplicated(subset=["firm_id", "relative_timepoint"]).any()
    dm = dec[dec.firm_id.astype(str) == "8"]
    assert len(dm) == 2
    assert (dm.source_batch == "DM_FINAL").all()
    pe = dm[dm.relative_timepoint == "post_event"].iloc[0]
    assert pe.rescue_decision == "replace_with_rescue"
    assert str(pe.forced_sensitivity_treatment).lower() in {"true", "1"}
    assert abs(float(pe.rescue_branding_tokens_de) - 5069) < 1
    assert dm[dm.relative_timepoint == "post_post_event"].iloc[0].rescue_decision == "retain_original"


@pytest.mark.skipif(not FINAL_DM.exists(), reason="dm final release not assembled")
def test_prior_19_decisions_unchanged():
    prior = pd.read_csv(BASE_FINAL / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    now = pd.read_csv(FINAL_DM / "rescue_comparison_decisions_FINAL.csv", dtype=str)
    now_prior = now[now.firm_id.astype(str).isin(PRIOR_RESCUE)].copy()
    cols = [
        "firm_id",
        "relative_timepoint",
        "rescue_decision",
        "rescue_decision_reason",
        "rescue_branding_tokens_de",
        "forced_sensitivity_treatment",
        "entity_change_flag",
    ]
    a = prior[cols].sort_values(["firm_id", "relative_timepoint"]).reset_index(drop=True)
    b = now_prior[cols].sort_values(["firm_id", "relative_timepoint"]).reset_index(drop=True)
    assert a.equals(b)


@pytest.mark.skipif(not FINAL_DM.exists(), reason="dm final release not assembled")
def test_dm_readiness_and_sensitivity_only_post():
    cov = pd.read_csv(FINAL_DM / "firm_longitudinal_coverage.csv", dtype=str)
    row = cov[cov.firm_id.astype(str) == "8"].iloc[0]
    assert row.german_longitudinal_ready_primary == "FALSE"
    assert row.german_longitudinal_ready_extended == "TRUE"
    primary = pd.read_csv(FINAL_DM / "full_sample_branding_corpus_observations_primary.csv", dtype=str)
    sens = pd.read_csv(FINAL_DM / "full_sample_branding_corpus_observations_sensitivity_de.csv", dtype=str)
    assert primary[(primary.firm_id == "8") & (primary.relative_timepoint == "post_event")].empty
    pe = sens[(sens.firm_id == "8") & (sens.relative_timepoint == "post_event")]
    assert len(pe) == 1
    assert abs(float(pe.iloc[0].tokens_de) - 5069) < 1
    assert abs(float(pe.iloc[0].n_pages_de) - 17) < 1
    snaps = pd.read_csv(FINAL_DM / "full_sample_snapshots.csv", dtype=str)
    snap = snaps[(snaps.firm_id == "8") & (snaps.relative_timepoint == "post_event")].iloc[0]
    assert snap.observation_recommendation == "sensitivity_analysis"
    assert str(snap.temporal_fit_quality).lower() == "very_low"
    assert abs(float(snap.temporal_distance_days) - 441) < 0.5
    assert str(snap.archive_timestamp).startswith("20200416175348")


@pytest.mark.skipif(not FINAL_DM.exists(), reason="dm final release not assembled")
def test_headlines_22_primary_28_extended():
    cov = pd.read_csv(FINAL_DM / "firm_longitudinal_coverage.csv", dtype=str)
    assert (cov.german_longitudinal_ready_primary == "TRUE").sum() == 22
    assert (cov.german_longitudinal_ready_extended == "TRUE").sum() == 28
    not_ext = sorted(
        cov.loc[cov.german_longitudinal_ready_extended != "TRUE", "firm_id"].astype(str), key=int
    )
    assert not_ext == ["24", "30"]


@pytest.mark.skipif(not FINAL_DM.exists(), reason="dm final release not assembled")
def test_parent_sha_and_base_final_immutable():
    sha = hashlib.sha256(
        (PARENT / "full_sample_branding_corpus_observations_primary.csv").read_bytes()
    ).hexdigest()
    assert sha == EXPECTED_SHA
    freeze = ROOT / "data" / "releases" / "full_sample_v1_1_rescue_final" / "freeze_manifest.json"
    assert (
        hashlib.sha256(freeze.read_bytes()).hexdigest()
        == "8c0bb4436a4158996fd89e2c9b825848980c55eb5a4d83995a208a981fb2aa69"
    )
    cand = ROOT / "data" / "input" / "full_sample_url_rescue_candidates.csv"
    assert (
        hashlib.sha256(cand.read_bytes()).hexdigest()
        == "d28b44180c44eabaefca54ecc1322493b144fe63a39cd4e56e51dc2140530120"
    )
