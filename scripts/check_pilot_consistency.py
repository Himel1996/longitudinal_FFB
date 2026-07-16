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
    governance_pages = pd.read_csv(out / "governance_metadata_pages.csv")
    run_id = str(snapshots["run_id"].iloc[0])

    # Single run_id everywhere
    for name, df in [
        ("snapshots", snapshots),
        ("pages", pages),
        ("manual", manual),
        ("quality", quality),
        ("observation_text_summary", obs_summary),
        ("branding_corpus_pages", branding_pages),
        ("governance_metadata_pages", governance_pages),
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
    banned = {"privacy_policy", "terms_conditions", "cookie_notice", "legal_other", "technical_system", "search_archive", "navigation_only", "impressum"}
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
