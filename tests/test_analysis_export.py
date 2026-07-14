"""Tests for analysis-ready export tables."""

import pandas as pd

from ffb_webminer.pipeline.analysis_export import (
    assign_observation_scopes,
    build_analysis_observations,
    build_analysis_observations_sensitivity,
    build_firm_coverage_matrix,
    observation_scope,
)


def _sample_snapshots() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "firm_id": "1",
            "rank": 1,
            "company": "A",
            "relative_timepoint": "pre_event",
            "snapshot_status": "selected",
            "homepage_available": True,
            "relevant_subpages_available": True,
            "subpage_only_observation": False,
            "observation_recommendation": "include",
            "analysis_eligible": True,
        },
        {
            "firm_id": "1",
            "rank": 1,
            "company": "A",
            "relative_timepoint": "event",
            "snapshot_status": "not_found",
            "homepage_available": False,
            "relevant_subpages_available": True,
            "subpage_only_observation": True,
            "observation_recommendation": "sensitivity_analysis",
            "analysis_eligible": True,
        },
    ])


def test_observation_scope_values():
    assert observation_scope(_sample_snapshots().iloc[0].to_dict()) == "homepage_plus_subpages"
    assert observation_scope(_sample_snapshots().iloc[1].to_dict()) == "subpages_only"


def test_analysis_exports_filter_recommendations():
    df = assign_observation_scopes(_sample_snapshots())
    primary = build_analysis_observations(df)
    sensitivity = build_analysis_observations_sensitivity(df)
    assert len(primary) == 1
    assert len(sensitivity) == 2


def test_firm_coverage_matrix():
    df = _sample_snapshots()
    matrix = build_firm_coverage_matrix(df)
    assert matrix.iloc[0]["pre_event"] == "include"
    assert matrix.iloc[0]["event"] == "sensitivity_analysis"
