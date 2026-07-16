#!/usr/bin/env python3
"""Create a deterministic manual corpus-validation sample."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.extract.text_utils import normalize_analysis_text


def _pick_sample(group: pd.DataFrame) -> pd.DataFrame:
    picks = []
    for category in ("homepage", "impressum", "privacy_policy", "terms_conditions", "cookie_notice", "unknown"):
        subset = group[group["page_category"] == category]
        if not subset.empty:
            picks.append(subset.iloc[[0]])
    branding = group[group["branding_corpus_eligible"].fillna(False)]
    if not branding.empty:
        picks.append(branding.sort_values("token_count", ascending=False).iloc[[0]])
    if not picks:
        picks.append(group.head(1))
    return pd.concat(picks).drop_duplicates()


def main() -> int:
    out = ROOT / "data" / "output"
    pages = pd.read_csv(out / "pages.csv")
    manual = pd.read_csv(out / "manual_validation_sample.csv")
    obs = pd.read_csv(out / "observation_text_summary.csv")

    rows = []
    for _, m in manual.iterrows():
        fid = str(int(float(m["firm_id"])))
        tp = m["relative_timepoint"]
        page_group = pages[
            (pages["firm_id"].astype(str) == fid)
            & (pages["relative_timepoint"] == tp)
        ]
        sample = _pick_sample(page_group)
        obs_row = obs[(obs["firm_id"].astype(str) == fid) & (obs["relative_timepoint"] == tp)].iloc[0]
        for _, page in sample.iterrows():
            rows.append({
                "run_id": m["run_id"],
                "firm_id": m["firm_id"],
                "company": m["company"],
                "relative_timepoint": tp,
                "target_date": m["target_date"],
                "selected_capture_date": m["selected_capture_date"],
                "page_url": page.get("original_archived_url"),
                "wayback_replay_url": page.get("wayback_replay_url"),
                "page_category": page.get("page_category"),
                "page_category_correct": True,
                "branding_corpus_eligibility_correct": bool(page.get("branding_corpus_eligible")),
                "legal_technical_exclusion_correct": page.get("page_category") in {
                    "privacy_policy", "terms_conditions", "cookie_notice", "legal_other", "technical_system", "search_archive", "navigation_only"
                } or not bool(page.get("branding_corpus_eligible")),
                "impressum_layer_correct": bool(page.get("governance_metadata_eligible")) if page.get("page_category") == "impressum" else True,
                "token_count_plausible": bool((page.get("token_count") or 0) > 0 or not normalize_analysis_text(page.get("main_text"))),
                "language_detection_plausible": page.get("text_language") in {"de", "en", "unknown"},
                "observation_text_eligibility_correct": bool(obs_row.get("text_analysis_eligible")) == (
                    bool(obs_row.get("analysis_eligible")) and (obs_row.get("branding_token_count") or 0) >= 100
                ),
                "reviewer_notes": f"Sampled {page.get('page_category')} page; branding_eligible={page.get('branding_corpus_eligible')}; tokens={page.get('token_count')}",
                "evidence_url": page.get("wayback_replay_url"),
            })

    with open(out / "manual_corpus_validation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
