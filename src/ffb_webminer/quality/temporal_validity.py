"""Temporal fit scoring, adjacent-period checks, and observation recommendations."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

TIMEPOINT_ORDER = ["pre_pre_event", "pre_event", "event", "post_event", "post_post_event"]


def temporal_fit_quality(distance_days: int | None) -> str | None:
    if distance_days is None:
        return None
    if distance_days <= 90:
        return "high"
    if distance_days <= 183:
        return "moderate"
    if distance_days <= 365:
        return "low"
    if distance_days <= 548:
        return "very_low"
    return None


def temporal_fit_usable_default(quality: str | None, override_very_low: bool = False) -> bool | None:
    if quality is None:
        return None
    if quality == "very_low":
        return override_very_low
    return True


def event_snapshot_position(
    capture_date: date | None,
    event_date: date | None,
    event_precision: str,
) -> str | None:
    if capture_date is None or event_date is None:
        return "unknown"
    if capture_date < event_date:
        return "before_event"
    if capture_date > event_date:
        return "after_event"
    return "on_event_day"


def days_from_actual_event(
    capture_date: date | None,
    event_date: date | None,
) -> int | None:
    if capture_date is None or event_date is None:
        return None
    return (capture_date - event_date).days


def is_homepage_url(url: str | None) -> bool:
    if not url:
        return False
    from urllib.parse import urlparse

    from ffb_webminer.archive.wayback_url import unwrap_wayback_url

    parsed = urlparse(unwrap_wayback_url(url))
    path = parsed.path or "/"
    return path in ("/", "")


def observation_recommendation(row: dict[str, Any]) -> str:
    status = row.get("snapshot_status")
    if status in ("future_unavailable", "not_found", "beyond_tolerance", "event_unavailable"):
        return "exclude"
    if row.get("adjacent_period_overlap_flag"):
        return "sensitivity_analysis"
    if row.get("event_snapshot_position") == "before_event" and row.get("relative_timepoint") == "event":
        return "sensitivity_analysis"
    if row.get("temporal_fit_quality") == "very_low" and not row.get("temporal_fit_usable_default"):
        return "sensitivity_analysis"
    if row.get("subpage_only_observation"):
        return "sensitivity_analysis"
    if status == "selected":
        return "include"
    return "exclude"


def enrich_snapshots_dataframe(
    snapshots: pd.DataFrame,
    firms: pd.DataFrame,
    adjacent_min_days: int = 180,
    override_very_low_usable: bool = False,
) -> pd.DataFrame:
    """Add temporal validity fields and adjacent-period metrics in-place logic."""
    df = snapshots.copy()
    firm_event: dict[str, dict] = {}
    for _, f in firms.iterrows():
        fid = str(f["firm_id"])
        firm_event[fid] = {
            "event_date": f.get("event_date_final") or f.get("event_date"),
            "event_date_precision": f.get("event_date_precision"),
        }

    qualities = []
    usable_defaults = []
    positions = []
    days_from_event = []
    recommendations = []

    for _, row in df.iterrows():
        dist = row.get("temporal_distance_days")
        if pd.notna(dist):
            dist = int(dist)
        else:
            dist = None
        q = temporal_fit_quality(dist)
        qualities.append(q)
        usable_defaults.append(temporal_fit_usable_default(q, override_very_low_usable))

        cap = row.get("selected_capture_date")
        cap_date = date.fromisoformat(str(cap)[:10]) if pd.notna(cap) else None
        ev = firm_event.get(str(row["firm_id"]), {})
        ev_date_s = ev.get("event_date")
        ev_date = date.fromisoformat(str(ev_date_s)[:10]) if ev_date_s and pd.notna(ev_date_s) else None
        ev_prec = ev.get("event_date_precision") or "year"

        positions.append(event_snapshot_position(cap_date, ev_date, ev_prec))
        days_from_event.append(days_from_actual_event(cap_date, ev_date))

    df["temporal_fit_quality"] = qualities
    df["temporal_fit_usable_default"] = usable_defaults
    df["event_snapshot_position"] = positions
    df["days_from_actual_event"] = days_from_event

    # Adjacent-period metrics per firm
    df["days_between_selected_snapshots"] = None
    df["adjacent_period_overlap_flag"] = False

    for fid, group in df.groupby("firm_id"):
        ordered = group.sort_values(
            by="relative_timepoint",
            key=lambda s: s.map({tp: i for i, tp in enumerate(TIMEPOINT_ORDER)}),
        )
        prev_date: date | None = None
        prev_idx = None
        for idx, row in ordered.iterrows():
            if row["snapshot_status"] != "selected":
                continue
            cap = row.get("selected_capture_date")
            if pd.isna(cap):
                continue
            cap_date = date.fromisoformat(str(cap)[:10])
            if prev_date is not None and prev_idx is not None:
                gap = (cap_date - prev_date).days
                df.at[idx, "days_between_selected_snapshots"] = gap
                overlap = gap < adjacent_min_days
                df.at[idx, "adjacent_period_overlap_flag"] = overlap
                if overlap:
                    df.at[prev_idx, "adjacent_period_overlap_flag"] = True
            prev_date = cap_date
            prev_idx = idx

    for _, row in df.iterrows():
        recommendations.append(observation_recommendation(row.to_dict()))
    df["observation_recommendation"] = recommendations

    return df


def build_temporal_validity_report(snapshots: pd.DataFrame, run_id: str, run_date: date) -> str:
    lines = [
        "# Temporal Validity Report",
        "",
        f"**Run ID:** `{run_id}`  ",
        f"**Pipeline run date:** {run_date.isoformat()}  ",
        f"**Observations:** {len(snapshots)}",
        "",
    ]

    selected = snapshots[snapshots["snapshot_status"] == "selected"]

    lines.extend(["## Temporal fit distribution (selected snapshots)", ""])
    for q in ["high", "moderate", "low", "very_low"]:
        subset = selected[selected["temporal_fit_quality"] == q]
        lines.append(f"- **{q}:** {len(subset)}")
        for _, r in subset.iterrows():
            lines.append(
                f"  - {r['company']} / {r['relative_timepoint']} "
                f"(target {r['target_date']}, capture {r.get('selected_capture_date', '—')}, "
                f"Δ={r.get('temporal_distance_days', '—')}d)"
            )

    lines.extend(["", "## Event snapshots vs known event dates", ""])
    events = snapshots[snapshots["relative_timepoint"] == "event"]
    for _, r in events.iterrows():
        lines.append(
            f"- **{r['company']}:** status={r['snapshot_status']}, "
            f"event_date={r.get('event_date_final', r.get('event_date', '—'))}, capture={r.get('selected_capture_date', '—')}, "
            f"position={r.get('event_snapshot_position', '—')}, "
            f"days_from_event={r.get('days_from_actual_event', '—')}"
        )

    lines.extend(["", "## Adjacent-period overlap", ""])
    overlap = snapshots[snapshots["adjacent_period_overlap_flag"] == True]  # noqa: E712
    if overlap.empty:
        lines.append("No adjacent overlap flags.")
    else:
        for _, r in overlap.iterrows():
            lines.append(
                f"- {r['company']} / {r['relative_timepoint']}: "
                f"gap={r.get('days_between_selected_snapshots', '—')} days to previous selected capture"
            )

    lines.extend(["", "## Homepage missing but archived subpages available", ""])
    subonly = snapshots[
        (snapshots.get("homepage_available") == False)  # noqa: E712
        & (snapshots.get("relevant_subpages_available") == True)  # noqa: E712
    ] if "homepage_available" in snapshots.columns else pd.DataFrame()
    if subonly.empty:
        lines.append("None flagged.")
    else:
        for _, r in subonly.iterrows():
            lines.append(f"- {r['company']} / {r['relative_timepoint']}")

    lines.extend(["", "## Observation recommendations", ""])
    for rec in ["include", "sensitivity_analysis", "exclude", "exclude_duplicate_capture"]:
        subset = snapshots[snapshots["observation_recommendation"] == rec]
        lines.append(f"### {rec} ({len(subset)})")
        for _, r in subset.iterrows():
            lines.append(
                f"- {r['company']} / {r['relative_timepoint']} "
                f"[{r['snapshot_status']}, fit={r.get('temporal_fit_quality', '—')}]"
            )
        lines.append("")

    return "\n".join(lines) + "\n"
