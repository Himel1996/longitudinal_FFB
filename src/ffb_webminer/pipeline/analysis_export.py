"""Observation scope and analysis-ready export tables."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ffb_webminer.pipeline.schemas import (
    ANALYSIS_OBSERVATION_COLUMNS,
    FIRM_COVERAGE_COLUMNS,
    MANUAL_VALIDATION_COLUMNS,
    TIMEPOINT_ORDER,
)

ANALYSIS_RECOMMENDATIONS = frozenset({"include", "sensitivity_analysis"})
SENSITIVITY_RECOMMENDATIONS = frozenset({"include", "sensitivity_analysis"})


def observation_scope(row: dict[str, Any]) -> str:
    if row.get("subpage_only_observation"):
        return "subpages_only"
    status = row.get("snapshot_status")
    if status != "selected":
        return "unavailable"
    homepage = bool(row.get("homepage_available"))
    subpages = bool(row.get("relevant_subpages_available"))
    if homepage and subpages:
        return "homepage_plus_subpages"
    if homepage:
        return "homepage_only"
    if subpages:
        return "subpages_only"
    return "unavailable"


def assign_observation_scopes(snapshots: pd.DataFrame) -> pd.DataFrame:
    df = snapshots.copy()
    df["observation_scope"] = [observation_scope(r) for _, r in df.iterrows()]
    return df


def build_analysis_observations(snapshots: pd.DataFrame) -> pd.DataFrame:
    mask = snapshots["observation_recommendation"] == "include"
    subset = snapshots[mask].copy()
    return _format_analysis_table(subset)


def build_analysis_observations_sensitivity(snapshots: pd.DataFrame) -> pd.DataFrame:
    mask = snapshots["observation_recommendation"].isin(SENSITIVITY_RECOMMENDATIONS)
    subset = snapshots[mask].copy()
    return _format_analysis_table(subset)


def _format_analysis_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ANALYSIS_OBSERVATION_COLUMNS:
        if col not in out.columns:
            out[col] = None
    return out[ANALYSIS_OBSERVATION_COLUMNS]


def build_firm_coverage_matrix(snapshots: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for firm_id, group in snapshots.groupby("firm_id"):
        row: dict[str, Any] = {
            "firm_id": firm_id,
            "rank": group["rank"].iloc[0],
            "company": group["company"].iloc[0],
        }
        for tp in TIMEPOINT_ORDER:
            tp_rows = group[group["relative_timepoint"] == tp]
            if tp_rows.empty:
                row[tp] = None
            else:
                row[tp] = tp_rows.iloc[0]["observation_recommendation"]
        rows.append(row)
    result = pd.DataFrame(rows)
    for col in FIRM_COVERAGE_COLUMNS:
        if col not in result.columns:
            result[col] = None
    return result[FIRM_COVERAGE_COLUMNS]


def build_full_manual_validation(snapshots: pd.DataFrame) -> pd.DataFrame:
    mask = snapshots["observation_recommendation"].isin(SENSITIVITY_RECOMMENDATIONS)
    subset = snapshots[mask].copy()
    rows = []
    for _, snap in subset.iterrows():
        rows.append({
            "run_id": snap.get("run_id"),
            "firm_id": snap.get("firm_id"),
            "company": snap.get("company"),
            "relative_timepoint": snap.get("relative_timepoint"),
            "target_date": snap.get("target_date"),
            "selected_capture_date": snap.get("selected_capture_date"),
            "temporal_fit_quality": snap.get("temporal_fit_quality"),
            "observation_scope": snap.get("observation_scope"),
            "observation_recommendation": snap.get("observation_recommendation"),
            "original_archived_url": snap.get("canonical_original_url"),
            "wayback_replay_url": snap.get("wayback_replay_url"),
            "duplicate_capture_flag": snap.get("duplicate_capture_flag"),
            "correct_company": None,
            "valid_archived_page": None,
            "temporally_appropriate": None,
            "content_extraction_usable": None,
            "duplicate_capture": snap.get("duplicate_capture_flag"),
            "reviewer_notes": None,
            "validation_screenshot_path": None,
        })
    result = pd.DataFrame(rows)
    for col in MANUAL_VALIDATION_COLUMNS:
        if col not in result.columns:
            result[col] = None
    return result[MANUAL_VALIDATION_COLUMNS]
