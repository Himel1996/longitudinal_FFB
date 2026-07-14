"""Manual validation sample generation."""

from __future__ import annotations

import random
from typing import Any

import pandas as pd


def build_manual_validation_sample(
    pages_df: pd.DataFrame,
    sample_size: int = 15,
    seed: int = 42,
) -> pd.DataFrame:
    if pages_df.empty:
        return pd.DataFrame(columns=_validation_columns())

    rng = random.Random(seed)
    usable = pages_df[pages_df["usable_for_analysis"] == True]  # noqa: E712
    pool = usable if len(usable) >= sample_size else pages_df
    n = min(sample_size, len(pool))
    sample = pool.sample(n=n, random_state=seed) if n < len(pool) else pool.head(n)

    rows = []
    for _, row in sample.iterrows():
        rows.append({
            "run_id": row.get("run_id"),
            "firm_id": row.get("firm_id"),
            "company": row.get("company"),
            "relative_timepoint": row.get("relative_timepoint"),
            "target_year": row.get("target_year"),
            "original_archived_url": row.get("original_archived_url"),
            "wayback_replay_url": row.get("wayback_replay_url"),
            "extracted_text": (row.get("extracted_text") or "")[:2000],
            "usable_for_analysis": row.get("usable_for_analysis"),
            "exclusion_reason": row.get("exclusion_reason"),
            "quality_flags": _flags(row),
            "valid_page": None,
            "relevant_corporate_content": None,
            "extraction_correct": None,
            "notes": None,
        })
    return pd.DataFrame(rows)


def _validation_columns() -> list[str]:
    return [
        "run_id", "firm_id", "company", "relative_timepoint", "target_year",
        "original_archived_url", "wayback_replay_url", "extracted_text",
        "usable_for_analysis", "exclusion_reason", "quality_flags",
        "valid_page", "relevant_corporate_content", "extraction_correct", "notes",
    ]


def _flags(row: Any) -> str:
    flags = []
    for f in ("soft_404_flag", "likely_navigation_only", "duplicate_content_flag"):
        if row.get(f):
            flags.append(f)
    return ",".join(flags)
