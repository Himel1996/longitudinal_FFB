"""Manual-validation sampling schema for Phase B (no live validation here)."""

from __future__ import annotations

from typing import Any

import pandas as pd

MANUAL_VALIDATION_FIELDS = [
    "observation_id",
    "firm_id",
    "company",
    "relative_timepoint",
    "sample_stratum",
    "reviewer",
    "archive_capture_verified",
    "company_entity_verified",
    "language_verified",
    "branding_relevance_verified",
    "legal_exclusion_verified",
    "duplicate_check",
    "seed_provenance_verified",
    "temporal_classification_verified",
    "primary_sensitivity_classification_verified",
    "screenshot_path",
    "notes",
    "result",
]


def build_manual_validation_sample(
    decisions: pd.DataFrame,
    *,
    newly_ready_firm_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Build an empty structured sample plan from rescue decisions (no screenshots)."""
    newly_ready_firm_ids = newly_ready_firm_ids or set()
    rows: list[dict[str, Any]] = []
    if decisions is None or decisions.empty:
        return pd.DataFrame(columns=MANUAL_VALIDATION_FIELDS)

    def add(row: pd.Series, stratum: str) -> None:
        rows.append(
            {
                "observation_id": row.get("rescue_observation_id") or row.get("original_observation_id"),
                "firm_id": row.get("firm_id"),
                "company": row.get("company"),
                "relative_timepoint": row.get("relative_timepoint"),
                "sample_stratum": stratum,
                "reviewer": "",
                "archive_capture_verified": "",
                "company_entity_verified": "",
                "language_verified": "",
                "branding_relevance_verified": "",
                "legal_exclusion_verified": "",
                "duplicate_check": "",
                "seed_provenance_verified": "",
                "temporal_classification_verified": "",
                "primary_sensitivity_classification_verified": "",
                "screenshot_path": "",
                "notes": "",
                "result": "",
            }
        )

    for _, row in decisions.iterrows():
        fid = str(row.get("firm_id"))
        decision = str(row.get("rescue_decision") or "")
        if fid in newly_ready_firm_ids:
            add(row, "newly_german_ready")
        if bool(row.get("historical_domain_used")) or "historical" in str(row.get("rescue_decision_reason") or "").lower():
            add(row, "historical_domain_rescue")
        if "locale" in str(row.get("rescue_decision_reason") or "").lower():
            add(row, "locale_path_rescue")
        if fid == "5":
            add(row, "msf")
        if fid == "21":
            add(row, "freudenberg")
        if fid == "22":
            add(row, "stihl")
        if fid == "24":
            add(row, "viessmann")
        if fid == "30":
            add(row, "oetker")
        if decision in {"remain_unavailable", "rejected_outside_tolerance", "rejected_insufficient_text"}:
            add(row, "failed_rescue")
        if decision == "retain_original":
            add(row, "unchanged_observation")
        if "subpage" in str(row.get("rescue_decision_reason") or "").lower():
            add(row, "archived_subpage_rescue")

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=MANUAL_VALIDATION_FIELDS)
    return out.drop_duplicates(subset=["firm_id", "relative_timepoint", "sample_stratum"], keep="first")
