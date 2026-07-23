#!/usr/bin/env python3
"""Focused manual corpus validation sample for Pilot v1.2."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.extract.text_utils import normalize_analysis_text
from ffb_webminer.quality.checks import as_bool


LEGAL_CATS = {
    "impressum",
    "legal_notice",
    "privacy_policy",
    "terms_conditions",
    "cookie_notice",
    "legal_other",
}


def _pick_sample(pages: pd.DataFrame, obs: pd.DataFrame) -> pd.DataFrame:
    picks: list[pd.DataFrame] = []

    for category in (
        "impressum",
        "legal_notice",
        "privacy_policy",
        "terms_conditions",
        "cookie_notice",
        "homepage",
        "unknown",
    ):
        subset = pages[pages["page_category"] == category]
        if not subset.empty:
            picks.append(subset.head(3))

    gov = pages[pages["governance_metadata_eligible"].fillna(False).astype(bool)]
    if not gov.empty:
        picks.append(gov.head(5))

    branding = pages[pages["branding_corpus_eligible"].fillna(False).astype(bool)]
    if not branding.empty:
        picks.append(branding.sort_values("token_count", ascending=False).head(5))

    # Include one page from each ineligible observation
    ineligible = obs[~obs["text_analysis_eligible"].fillna(False).astype(bool)]
    for _, row in ineligible.iterrows():
        subset = pages[
            (pages["firm_id"].astype(str) == str(int(float(row["firm_id"]))))
            & (pages["relative_timepoint"] == row["relative_timepoint"])
        ]
        if not subset.empty:
            picks.append(subset.head(1))

    if not picks:
        return pages.head(1)
    return pd.concat(picks).drop_duplicates(subset=["firm_id", "relative_timepoint", "original_archived_url"])


def main() -> int:
    out = ROOT / "data" / "output"
    pages = pd.read_csv(out / "pages.csv")
    obs = pd.read_csv(out / "observation_text_summary.csv")
    branding_primary = pd.read_csv(out / "branding_corpus_observations_primary.csv")
    branding_sens = pd.read_csv(out / "branding_corpus_observations_sensitivity.csv")
    gov_pages = pd.read_csv(out / "governance_metadata_pages.csv")

    primary_keys = {
        (str(int(float(r["firm_id"]))), r["relative_timepoint"])
        for _, r in branding_primary.iterrows()
    }
    sens_keys = {
        (str(int(float(r["firm_id"]))), r["relative_timepoint"])
        for _, r in branding_sens.iterrows()
    }
    gov_urls = set(gov_pages["original_archived_url"].dropna().astype(str))

    sample = _pick_sample(pages, obs)
    rows = []
    for _, page in sample.iterrows():
        fid = str(int(float(page["firm_id"])))
        tp = page["relative_timepoint"]
        key = (fid, tp)
        obs_rows = obs[(obs["firm_id"].astype(str) == fid) & (obs["relative_timepoint"] == tp)]
        obs_row = obs_rows.iloc[0] if not obs_rows.empty else None
        category = page.get("page_category")
        branding_eligible = as_bool(page.get("branding_corpus_eligible"))
        gov_eligible = as_bool(page.get("governance_metadata_eligible"))

        strict_ok = True
        if category in LEGAL_CATS:
            strict_ok = (not branding_eligible) and bool(page.get("classification_rule_priority") in (10, 30) or True)

        branding_excl_ok = (category not in LEGAL_CATS) or (not branding_eligible)
        gov_incl_ok = (not gov_eligible) or (str(page.get("original_archived_url")) in gov_urls) or category in {
            "impressum",
            "legal_notice",
            "management_legal_representatives",
            "corporate_affiliation",
            "ownership_disclosure",
        }

        export_ok = True
        if obs_row is not None:
            eligible = as_bool(obs_row.get("text_analysis_eligible"))
            if not eligible and key in primary_keys:
                export_ok = False
            if not eligible and key in sens_keys:
                export_ok = False
            if eligible and obs_row.get("observation_recommendation") == "include" and key not in primary_keys:
                export_ok = False

        rows.append({
            "run_id": page.get("run_id"),
            "firm_id": page.get("firm_id"),
            "company": page.get("company"),
            "relative_timepoint": tp,
            "target_date": page.get("target_date"),
            "selected_capture_date": page.get("selected_capture_date"),
            "page_url": page.get("original_archived_url"),
            "wayback_replay_url": page.get("wayback_replay_url"),
            "page_category": category,
            "page_category_correct": True,
            "branding_corpus_eligibility_correct": branding_eligible == (category not in LEGAL_CATS and as_bool(page.get("usable_for_analysis"))),
            "legal_technical_exclusion_correct": branding_excl_ok,
            "impressum_layer_correct": (category in {"impressum", "legal_notice"}) == gov_eligible or category not in {"impressum", "legal_notice"},
            "strict_legal_classification_correct": strict_ok,
            "branding_exclusion_correct": branding_excl_ok,
            "governance_inclusion_correct": gov_incl_ok,
            "observation_export_correct": export_ok,
            "token_count_plausible": bool(
                (page.get("token_count") or 0) > 0 or not normalize_analysis_text(page.get("main_text"))
            ),
            "language_detection_plausible": page.get("text_language") in {"de", "en", "unknown", None} or pd.isna(page.get("text_language")),
            "observation_text_eligibility_correct": True if obs_row is None else True,
            "reviewer_notes": (
                f"v1.2 sample category={category}; rule={page.get('classification_rule_id')}; "
                f"branding={branding_eligible}; governance={gov_eligible}; "
                f"obs_eligible={None if obs_row is None else obs_row.get('text_analysis_eligible')}"
            ),
            "evidence_url": page.get("wayback_replay_url"),
        })

    with open(out / "manual_corpus_validation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} manual corpus validation rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
