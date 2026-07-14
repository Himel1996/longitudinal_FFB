"""Duplicate archive capture handling across relative timepoints."""

from __future__ import annotations

from datetime import date

import pandas as pd

TIMEPOINT_ORDER = ["pre_pre_event", "pre_event", "event", "post_event", "post_post_event"]


def _target_distance_days(target_date_str: str, capture_date_str: str) -> int:
    target = date.fromisoformat(str(target_date_str)[:10])
    capture = date.fromisoformat(str(capture_date_str)[:10])
    return abs((capture - target).days)


def apply_duplicate_capture_rules(snapshots: pd.DataFrame) -> pd.DataFrame:
    """Retain all snapshot rows; mark duplicate captures for analysis exclusion."""
    df = snapshots.copy()
    df["analysis_eligible"] = False
    df["duplicate_capture_flag"] = False
    df["duplicate_capture_winner_timepoint"] = None

    for _, group in df.groupby("firm_id"):
        selected = group[group["snapshot_status"] == "selected"].copy()
        if selected.empty:
            continue
        for _ts, ts_group in selected.groupby("archive_timestamp"):
            if pd.isna(_ts) or len(ts_group) <= 1:
                continue
            best_idx = None
            best_dist = None
            for idx, row in ts_group.iterrows():
                if pd.isna(row.get("target_date")) or pd.isna(row.get("selected_capture_date")):
                    continue
                dist = _target_distance_days(row["target_date"], row["selected_capture_date"])
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_idx = idx
                elif dist == best_dist:
                    # Tie-break: prefer earlier timepoint in theoretical sequence
                    tp_rank = {tp: i for i, tp in enumerate(TIMEPOINT_ORDER)}
                    if tp_rank.get(row["relative_timepoint"], 99) < tp_rank.get(
                        df.at[best_idx, "relative_timepoint"], 99
                    ):
                        best_idx = idx
            if best_idx is None:
                continue
            winner_tp = df.at[best_idx, "relative_timepoint"]
            for idx in ts_group.index:
                if idx == best_idx:
                    df.at[idx, "duplicate_capture_flag"] = False
                    if df.at[idx, "observation_recommendation"] in ("include", "sensitivity_analysis"):
                        df.at[idx, "analysis_eligible"] = True
                else:
                    df.at[idx, "duplicate_capture_flag"] = True
                    df.at[idx, "duplicate_capture_winner_timepoint"] = winner_tp
                    df.at[idx, "observation_recommendation"] = "exclude_duplicate_capture"
                    df.at[idx, "analysis_eligible"] = False

    # Non-duplicate selected observations
    for idx, row in df.iterrows():
        if row["snapshot_status"] != "selected":
            continue
        if row.get("duplicate_capture_flag"):
            continue
        if row["observation_recommendation"] in ("include", "sensitivity_analysis"):
            df.at[idx, "analysis_eligible"] = True

    return df
