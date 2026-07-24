#!/usr/bin/env python3
"""Focused manual scaling validation sample for Pilot v1.3."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.schemas import MANUAL_SCALING_VALIDATION_COLUMNS
from ffb_webminer.quality.checks import as_bool


def main() -> int:
    out = ROOT / "data" / "output"
    pages = pd.read_csv(out / "pages.csv")
    picks: list[pd.DataFrame] = []

    dups = pages[pages["duplicate_content_flag"].fillna(False).astype(bool)]
    if not dups.empty:
        picks.append(dups.head(20))

    # MYRENNE pre_event www/non-www focus
    myrenne = pages[
        (pages["firm_id"].astype(str) == "4")
        & (pages["relative_timepoint"] == "pre_event")
    ]
    if not myrenne.empty:
        picks.append(myrenne.head(10))

    lang_ex = pages[
        pages["language_exclusion_reason"].fillna("").astype(str).str.len() > 0
    ] if "language_exclusion_reason" in pages.columns else pd.DataFrame()
    if not lang_ex.empty:
        picks.append(lang_ex.head(10))

    unknown = pages[
        pages.get("detected_language", pages.get("text_language", pd.Series(dtype=object))).fillna("").eq("unknown")
    ] if "detected_language" in pages.columns or "text_language" in pages.columns else pd.DataFrame()
    if not unknown.empty:
        picks.append(unknown.head(8))

    reserved = pages[pages.get("selected_under_reserved_slot", pd.Series(dtype=bool)).fillna(False).astype(bool)] if "selected_under_reserved_slot" in pages.columns else pd.DataFrame()
    if not reserved.empty:
        picks.append(reserved.head(12))

    deferred = pages[
        pages.get("crawl_selection_reason", pd.Series(dtype=object)).fillna("").isin(
            ["flexible_secondary", "flexible_broad", "remaining_capacity", "overflow_unused_reserved"]
        )
        | pages.get("crawl_priority_tier", pd.Series(dtype=float)).fillna(3).astype(float).ge(2)
    ] if "crawl_selection_reason" in pages.columns else pd.DataFrame()
    if not deferred.empty:
        picks.append(deferred.head(10))

    if not picks:
        sample = pages.head(15)
    else:
        sample = pd.concat(picks).drop_duplicates(
            subset=["firm_id", "relative_timepoint", "original_archived_url"]
        )

    rows = []
    for _, page in sample.iterrows():
        notes = []
        if as_bool(page.get("duplicate_content_flag")):
            notes.append(f"dup:{page.get('duplicate_reason')}")
        if page.get("language_exclusion_reason"):
            notes.append(f"lang:{page.get('language_exclusion_reason')}")
        if page.get("crawl_selection_reason"):
            notes.append(f"crawl:{page.get('crawl_selection_reason')}")
        rows.append({
            "firm_id": page.get("firm_id"),
            "relative_timepoint": page.get("relative_timepoint"),
            "page_url": page.get("original_archived_url"),
            "duplicate_group_correct": "" if as_bool(page.get("duplicate_content_flag")) else "n/a",
            "canonical_page_choice_correct": "" if page.get("duplicate_group_id") else "n/a",
            "cross_time_content_preserved": "",
            "language_detection_correct": "",
            "german_corpus_decision_correct": "",
            "crawl_priority_correct": "",
            "reviewer_notes": "; ".join(notes) if notes else "",
        })

    df = pd.DataFrame(rows)
    pipeline_io.write_csv(df, out / "manual_scaling_validation.csv", MANUAL_SCALING_VALIDATION_COLUMNS)
    print(f"Wrote {len(df)} scaling validation rows to {out / 'manual_scaling_validation.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
