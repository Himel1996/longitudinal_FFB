#!/usr/bin/env python3
"""Consistency checks for pilot release."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/pilot.yaml")
    args = parser.parse_args()

    config = PipelineConfig.from_yaml(ROOT / args.config)
    out = ROOT / config.run.output_dir
    errors: list[str] = []

    snapshots = pd.read_csv(out / "snapshots.csv")
    pages = pd.read_csv(out / "pages.csv")
    manual = pd.read_csv(out / "manual_validation_sample.csv")
    quality = pd.read_csv(out / "quality_summary.csv")
    obs_summary = pd.read_csv(out / "observation_text_summary.csv")
    branding_pages = pd.read_csv(out / "branding_corpus_pages.csv")
    branding_primary = pd.read_csv(out / "branding_corpus_observations_primary.csv")
    branding_sens = pd.read_csv(out / "branding_corpus_observations_sensitivity.csv")
    governance_pages = pd.read_csv(out / "governance_metadata_pages.csv")
    governance_obs = pd.read_csv(out / "governance_metadata_observations.csv")
    run_id = str(snapshots["run_id"].iloc[0])

    # Single run_id everywhere
    for name, df in [
        ("snapshots", snapshots),
        ("pages", pages),
        ("manual", manual),
        ("quality", quality),
        ("observation_text_summary", obs_summary),
        ("branding_corpus_pages", branding_pages),
        ("branding_corpus_observations_primary", branding_primary),
        ("branding_corpus_observations_sensitivity", branding_sens),
        ("governance_metadata_pages", governance_pages),
        ("governance_metadata_observations", governance_obs),
    ]:
        ids = df["run_id"].dropna().astype(str).unique()
        if len(ids) > 1 or (len(ids) == 1 and ids[0] != run_id):
            errors.append(f"{name}: inconsistent run_id values {ids.tolist()}")

    # Every manual row references current snapshot
    snap_keys = {
        (str(int(float(r["firm_id"]))), r["relative_timepoint"]): r
        for _, r in snapshots.iterrows()
    }
    for _, m in manual.iterrows():
        key = (str(int(float(m["firm_id"]))), m["relative_timepoint"])
        if key not in snap_keys:
            errors.append(f"Manual row missing snapshot: {key}")
            continue
        snap = snap_keys[key]
        if str(m["wayback_replay_url"]) != str(snap["wayback_replay_url"]):
            errors.append(f"Stale wayback URL for {key}")
        if str(m["run_id"]) != run_id:
            errors.append(f"Manual row stale run_id for {key}")

    # Every selected snapshot has homepage page
    selected = snapshots[snapshots["snapshot_status"] == "selected"]
    for _, s in selected.iterrows():
        key = (str(int(float(s["firm_id"]))), s["relative_timepoint"])
        home = pages[
            (pages["firm_id"].astype(str) == key[0])
            & (pages["relative_timepoint"] == key[1])
            & (pages["page_priority_reason"].fillna("") == "homepage")
        ]
        if home.empty and s.get("observation_recommendation") in ("include", "sensitivity_analysis"):
            errors.append(f"No homepage page for selected snapshot {key}")

    # Page snapshot references
    for _, p in pages.iterrows():
        if pd.isna(p.get("firm_id")):
            errors.append(f"Page with NaN firm_id: {p.get('original_archived_url')}")
            continue
        key = (str(int(float(p["firm_id"]))), p["relative_timepoint"])
        if key not in snap_keys:
            errors.append(f"Page references unknown snapshot: {key}")

    # Branding corpus pages must be traceable and never legal/technical
    banned = {
        "privacy_policy",
        "terms_conditions",
        "cookie_notice",
        "legal_other",
        "technical_system",
        "search_archive",
        "navigation_only",
        "impressum",
        "legal_notice",
    }
    for _, p in branding_pages.iterrows():
        key = (str(int(float(p["firm_id"]))), p["relative_timepoint"])
        if key not in snap_keys:
            errors.append(f"Branding page references unknown snapshot: {key}")
        if p.get("page_category") in banned:
            errors.append(f"Illegal page in branding corpus: {p.get('original_archived_url')}")

    for _, p in governance_pages.iterrows():
        key = (str(int(float(p["firm_id"]))), p["relative_timepoint"])
        if key not in snap_keys:
            errors.append(f"Governance page references unknown snapshot: {key}")
        # governance file may only contain eligible pages
        if "governance_metadata_eligible" in pages.columns:
            match = pages[
                (pages["firm_id"].astype(str) == key[0])
                & (pages["relative_timepoint"] == key[1])
                & (pages["original_archived_url"].astype(str) == str(p.get("original_archived_url")))
            ]
            if not match.empty and not bool(match.iloc[0].get("governance_metadata_eligible")):
                errors.append(f"Governance page not marked eligible in pages.csv: {p.get('original_archived_url')}")

    # Observation corpus eligibility (v1.2 hard rules)
    if branding_primary["text_analysis_eligible"].fillna(False).astype(bool).ne(True).any():
        errors.append("branding_corpus_observations_primary contains text_analysis_eligible != true")
    if branding_sens["text_analysis_eligible"].fillna(False).astype(bool).ne(True).any():
        errors.append("branding_corpus_observations_sensitivity contains text_analysis_eligible != true")

    primary_expected = obs_summary[
        (obs_summary["observation_recommendation"] == "include")
        & (obs_summary["text_analysis_eligible"].fillna(False).astype(bool))
    ]
    sens_expected = obs_summary[
        (obs_summary["observation_recommendation"].isin(["include", "sensitivity_analysis"]))
        & (obs_summary["text_analysis_eligible"].fillna(False).astype(bool))
    ]
    if len(branding_primary) != len(primary_expected):
        errors.append(
            f"primary corpus count {len(branding_primary)} != eligible primary observations {len(primary_expected)}"
        )
    if len(branding_sens) != len(sens_expected):
        errors.append(
            f"sensitivity corpus count {len(branding_sens)} != eligible sensitivity observations {len(sens_expected)}"
        )

    def _obs_keys(df: pd.DataFrame) -> set[tuple[str, str]]:
        return {
            (str(int(float(r["firm_id"]))), r["relative_timepoint"])
            for _, r in df.iterrows()
        }

    if _obs_keys(branding_primary) != _obs_keys(primary_expected):
        errors.append("primary corpus keys do not match eligible observation_text_summary rows")
    if _obs_keys(branding_sens) != _obs_keys(sens_expected):
        errors.append("sensitivity corpus keys do not match eligible observation_text_summary rows")

    # Governance observation URLs must be traceable
    gov_page_urls = set(governance_pages["original_archived_url"].dropna().astype(str))
    for _, g in governance_obs.iterrows():
        raw = g.get("governance_metadata_source_urls")
        if pd.isna(raw) or not raw:
            continue
        import json

        try:
            urls = json.loads(raw) if isinstance(raw, str) else list(raw)
        except Exception:
            errors.append(f"Unparseable governance_metadata_source_urls for {g.get('firm_id')}|{g.get('relative_timepoint')}")
            continue
        for url in urls:
            if url not in gov_page_urls:
                errors.append(f"Governance observation URL not in governance pages: {url}")

    # Quality summary consistency
    for _, q in quality.iterrows():
        attempted = int(q.get("pages_attempted", 0) or 0)
        success = int(q.get("pages_fetch_success", 0) or 0)
        failed = int(q.get("pages_fetch_failed", 0) or 0)
        usable = int(q.get("pages_extraction_usable", 0) or 0)
        branding = int(q.get("pages_branding_eligible", 0) or 0)
        if attempted != success + failed:
            errors.append(f"Attempted mismatch for {q['firm_id']}|{q['relative_timepoint']}")
        if success < usable:
            errors.append(f"Fetch success < extraction usable for {q['firm_id']}|{q['relative_timepoint']}")
        if usable < branding:
            errors.append(f"Extraction usable < branding eligible for {q['firm_id']}|{q['relative_timepoint']}")

    # Screenshot paths exist
    if "validation_screenshot_path" in manual.columns:
        for _, m in manual.iterrows():
            sp = m.get("validation_screenshot_path")
            if pd.notna(sp) and sp:
                if not (out / str(sp)).exists():
                    errors.append(f"Missing screenshot: {sp}")

    # Archive timestamps match snapshots for homepage rows
    for _, m in manual.iterrows():
        key = (str(int(float(m["firm_id"]))), m["relative_timepoint"])
        snap_rows = snapshots[
            (snapshots["firm_id"].astype(str) == key[0])
            & (snapshots["relative_timepoint"] == key[1])
        ]
        if snap_rows.empty:
            errors.append(f"Manual row missing snapshot: {key}")
            continue
        snap = snap_rows.iloc[0]
        home = pages[
            (pages["firm_id"].astype(str) == key[0])
            & (pages["relative_timepoint"] == key[1])
            & (pages["page_priority_reason"].fillna("") == "homepage")
        ]
        if not home.empty:
            best = home.sort_values("word_count", ascending=False).iloc[0]
            snap_ts = str(snap.get("archive_timestamp", "")).split(".")[0]
            page_ts = str(best.get("archive_timestamp", "")).split(".")[0]
            if snap_ts and page_ts and snap_ts != page_ts:
                errors.append(f"Timestamp mismatch {key}: snap={snap_ts} page={page_ts}")

    print(f"Run ID: {run_id}")
    print(f"Snapshots: {len(snapshots)}, Pages: {len(pages)}, Manual: {len(manual)}")
    if errors:
        print(f"\nFAILED: {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nAll consistency checks PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
