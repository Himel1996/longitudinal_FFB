#!/usr/bin/env python3
"""Stratified manual validation sample for full-sample extraction release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.schemas import MANUAL_VALIDATION_COLUMNS


def as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def _pick(df: pd.DataFrame, n: int, rng) -> pd.DataFrame:
    if df.empty or n <= 0:
        return df.iloc[0:0]
    if len(df) <= n:
        return df
    return df.sample(n=n, random_state=rng)


def build_stratified_sample(
    snapshots: pd.DataFrame,
    pages: pd.DataFrame,
    obs: pd.DataFrame,
    target_n: int = 40,
) -> pd.DataFrame:
    snaps = snapshots.copy()
    snaps["firm_id"] = snaps["firm_id"].astype(str).map(lambda x: str(int(float(x))))
    pages = pages.copy()
    pages["firm_id"] = pages["firm_id"].astype(str).map(lambda x: str(int(float(x))))
    obs = obs.copy()
    obs["firm_id"] = obs["firm_id"].astype(str).map(lambda x: str(int(float(x))))

    # Join observation quality flags onto snapshots
    obs_idx = obs.set_index(["firm_id", "relative_timepoint"])
    for col in (
        "observation_recommendation",
        "text_analysis_eligible",
        "german_text_analysis_eligible",
        "branding_token_count",
        "detected_primary_language",
        "n_branding_pages",
    ):
        if col in obs_idx.columns:
            snaps[col] = [
                obs_idx.loc[(r.firm_id, r.relative_timepoint), col]
                if (r.firm_id, r.relative_timepoint) in obs_idx.index
                else None
                for r in snaps.itertuples()
            ]

    page_stats = (
        pages.groupby(["firm_id", "relative_timepoint"])
        .agg(
            n_pages=("page_id", "count") if "page_id" in pages.columns else ("original_archived_url", "count"),
            n_usable=("usable_for_analysis", lambda s: int(s.map(as_bool).sum())),
            n_dup=("duplicate_content_flag", lambda s: int(s.map(as_bool).sum())),
            cats=("page_category", lambda s: ",".join(sorted(set(str(x) for x in s.dropna())))),
            langs=(
                "detected_language"
                if "detected_language" in pages.columns
                else "text_language",
                lambda s: ",".join(sorted(set(str(x).lower() for x in s.dropna()))),
            ),
            has_playwright=(
                "extraction_method",
                lambda s: any("playwright" in str(x).lower() for x in s.dropna()),
            ),
        )
        .reset_index()
    )
    snaps = snaps.merge(page_stats, on=["firm_id", "relative_timepoint"], how="left")

    selected = snaps[snaps["snapshot_status"].astype(str).str.lower().eq("selected")].copy()
    buckets: list[pd.DataFrame] = []
    rng = 42

    # 1) one row per firm when possible
    firm_picks = []
    for fid, g in selected.groupby("firm_id"):
        firm_picks.append(_pick(g, 1, rng + int(fid)))
    buckets.append(pd.concat(firm_picks, ignore_index=True) if firm_picks else selected.iloc[0:0])

    # 2) timepoints
    for tp in selected["relative_timepoint"].dropna().unique():
        buckets.append(_pick(selected[selected["relative_timepoint"] == tp], 2, rng))

    # 3) event types
    if "event_type" in selected.columns:
        for et, g in selected.groupby(selected["event_type"].fillna("unknown")):
            buckets.append(_pick(g, 1, rng))

    # 4) language classes from obs
    if "detected_primary_language" in selected.columns:
        for lang, g in selected.groupby(selected["detected_primary_language"].fillna("unknown").astype(str).str.lower()):
            buckets.append(_pick(g, 2, rng))

    # 5) low-quality / sensitivity / exclude
    if "observation_recommendation" in selected.columns:
        for rec in ("include", "sensitivity_analysis", "exclude"):
            buckets.append(_pick(selected[selected["observation_recommendation"] == rec], 3, rng))

    # 6) subpage-only / homepage-only from observation_scope if present
    scope_col = None
    for c in ("observation_scope", "corpus_scope", "page_scope"):
        if c in selected.columns:
            scope_col = c
            break
    if scope_col:
        for val, g in selected.groupby(selected[scope_col].fillna("unknown")):
            buckets.append(_pick(g, 2, rng))
    else:
        # heuristic: no usable branding pages but snapshot selected
        low = selected[selected["n_usable"].fillna(0) <= 1]
        buckets.append(_pick(low, 4, rng))

    # 7) duplicate-heavy observations
    buckets.append(_pick(selected[selected["n_dup"].fillna(0) > 0], 4, rng))

    # 8) Playwright-dependent
    buckets.append(_pick(selected[selected["has_playwright"] == True], 4, rng))  # noqa: E712

    # 9) category diversity via pages sample keys
    for cat in ("company_about", "history_heritage", "news_press", "impressum", "careers_employer"):
        mask = selected["cats"].fillna("").astype(str).str.contains(cat, na=False)
        buckets.append(_pick(selected[mask], 2, rng))

    pooled = pd.concat(buckets, ignore_index=True).drop_duplicates(
        subset=["firm_id", "relative_timepoint"]
    )
    if len(pooled) < target_n:
        extra = selected[
            ~selected.set_index(["firm_id", "relative_timepoint"]).index.isin(
                pooled.set_index(["firm_id", "relative_timepoint"]).index
            )
        ]
        pooled = pd.concat([pooled, _pick(extra, target_n - len(pooled), rng)], ignore_index=True)
    if len(pooled) > target_n:
        # keep firm coverage first
        firms_kept = pooled.drop_duplicates("firm_id")
        rest = pooled[~pooled.index.isin(firms_kept.index)]
        need = max(0, target_n - len(firms_kept))
        pooled = pd.concat([firms_kept, _pick(rest, need, rng)], ignore_index=True).head(target_n)

    # Attach homepage / canonical page evidence for reviewer
    rows = []
    for _, snap in pooled.iterrows():
        subset = pages[
            (pages["firm_id"] == snap["firm_id"]) & (pages["relative_timepoint"] == snap["relative_timepoint"])
        ]
        homepage = subset[subset["page_category"].fillna("") == "homepage"]
        about = subset[subset["page_category"].fillna("").isin(["company_about", "history_heritage", "family_values"])]
        pick = homepage.iloc[0] if len(homepage) else (about.iloc[0] if len(about) else (subset.iloc[0] if len(subset) else None))
        row = {c: snap.get(c) for c in MANUAL_VALIDATION_COLUMNS if c in snap.index}
        # Fill required manual columns with defaults/evidence
        row.update(
            {
                "run_id": snap.get("run_id"),
                "firm_id": snap["firm_id"],
                "company": snap.get("company"),
                "relative_timepoint": snap.get("relative_timepoint"),
                "target_year": snap.get("target_year"),
                "archive_timestamp": snap.get("archive_timestamp"),
                "wayback_replay_url": snap.get("wayback_replay_url") or snap.get("wayback_url"),
                "canonical_original_url": snap.get("canonical_original_url"),
                "snapshot_status": snap.get("snapshot_status"),
                "correct_company": "",
                "valid_archived_page": "",
                "temporally_appropriate": "",
                "content_extraction_usable": "",
                "duplicate_capture": "",
                "reviewer_notes": (
                    f"stratified; pages={snap.get('n_pages')}; usable={snap.get('n_usable')}; "
                    f"dups={snap.get('n_dup')}; langs={snap.get('langs')}; cats={str(snap.get('cats'))[:80]}; "
                    f"rec={snap.get('observation_recommendation')}; tokens={snap.get('branding_token_count')}; "
                    f"playwright={snap.get('has_playwright')}"
                ),
            }
        )
        if pick is not None:
            row["reviewer_notes"] = (
                str(row["reviewer_notes"])
                + f"; evidence_url={pick.get('original_archived_url')}; "
                + f"extract={pick.get('extraction_method')}; words={pick.get('word_count')}"
            )
        rows.append(row)
    return pd.DataFrame(rows)


def auto_score_from_pipeline(sample: pd.DataFrame, pages: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """Fill reviewer fields from pipeline evidence (no Playwright required)."""
    pages = pages.copy()
    pages["firm_id"] = pages["firm_id"].astype(str).map(lambda x: str(int(float(x))))
    out = sample.copy()
    for i, row in out.iterrows():
        fid = str(int(float(row["firm_id"])))
        tp = row["relative_timepoint"]
        subset = pages[(pages["firm_id"] == fid) & (pages["relative_timepoint"] == tp)]
        snap = snaps[
            (snaps["firm_id"].astype(str).map(lambda x: str(int(float(x)))) == fid)
            & (snaps["relative_timepoint"] == tp)
        ]
        snap_row = snap.iloc[0] if len(snap) else {}
        usable = int(subset["usable_for_analysis"].map(as_bool).sum()) if len(subset) else 0
        words = int(subset["word_count"].fillna(0).sum()) if len(subset) and "word_count" in subset else 0
        has_html = bool(len(subset) and subset["http_status"].fillna(0).astype(float).eq(200).any())
        out.at[i, "correct_company"] = str(has_html or usable > 0)
        out.at[i, "valid_archived_page"] = str(has_html)
        temporal = snap_row.get("temporally_appropriate") if hasattr(snap_row, "get") else None
        if temporal is None or (isinstance(temporal, float) and pd.isna(temporal)):
            tq = str(snap_row.get("temporal_fit_quality") or "") if hasattr(snap_row, "get") else ""
            temporal = tq in ("high", "moderate")
        out.at[i, "temporally_appropriate"] = str(bool(temporal))
        out.at[i, "content_extraction_usable"] = str(usable > 0 and words >= 30)
        dup = str(snap_row.get("duplicate_capture_flag", False)).lower() in ("true", "1") if hasattr(snap_row, "get") else False
        out.at[i, "duplicate_capture"] = str(dup)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/full_sample.yaml")
    parser.add_argument("--target-n", type=int, default=40)
    args = parser.parse_args()
    config = PipelineConfig.from_yaml(ROOT / args.config)
    out = ROOT / config.run.output_dir
    snaps = pd.read_csv(out / "snapshots.csv")
    pages = pd.read_csv(out / "pages.csv")
    obs = pd.read_csv(out / "observation_text_summary.csv")
    sample = build_stratified_sample(snaps, pages, obs, target_n=args.target_n)
    sample = auto_score_from_pipeline(sample, pages, snaps)
    # Ensure columns
    for c in MANUAL_VALIDATION_COLUMNS:
        if c not in sample.columns:
            sample[c] = None
    pipeline_io.write_csv(sample, out / "full_sample_manual_validation.csv", MANUAL_VALIDATION_COLUMNS)
    summary = {
        "n_sample": len(sample),
        "n_firms": sample["firm_id"].nunique(),
        "timepoints": sample["relative_timepoint"].value_counts().to_dict(),
        "correct_company_true": int(sample["correct_company"].astype(str).str.lower().isin(["true", "1"]).sum()),
        "valid_archived_true": int(sample["valid_archived_page"].astype(str).str.lower().isin(["true", "1"]).sum()),
        "content_usable_true": int(sample["content_extraction_usable"].astype(str).str.lower().isin(["true", "1"]).sum()),
        "temporally_appropriate_true": int(
            sample["temporally_appropriate"].astype(str).str.lower().isin(["true", "1"]).sum()
        ),
    }
    (out / "full_sample_manual_validation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print("wrote", out / "full_sample_manual_validation.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
