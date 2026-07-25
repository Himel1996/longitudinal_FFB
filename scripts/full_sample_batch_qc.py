#!/usr/bin/env python3
"""Batch QC gate for full-sample scaling (release-acceptance invariants)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.crawl.priority import normalize_path_segments

RESERVE_CATS = {
    "homepage",
    "company_about",
    "history_heritage",
    "family_owners",
    "values_responsibility",
    "management_leadership",
}
LOW_VALUE_SEGMENTS = frozenset(
    {
        "news",
        "newsletter",
        "newsletters",
        "newsroom",
        "presse",
        "press",
        "aktuelles",
        "pressemitteilungen",
        "pressemitteilung",
        "pr-bereich",
        "medien",
        "media",
        "karriere",
        "career",
        "careers",
        "jobs",
        "stellen",
        "produkte",
        "produkt",
        "products",
        "product",
        "download",
        "downloads",
    }
)
LEGAL_MARKERS = (
    "impressum",
    "imprint",
    "datenschutz",
    "privacy",
    "agb",
    "terms",
    "cookie",
    "legal-notice",
    "rechtliches",
    "disclaimer",
)


def as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def load(out: Path, name: str) -> pd.DataFrame:
    path = out / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def summarize_batch(out: Path, firm_ids: list[str] | None = None) -> dict:
    pages = load(out, "pages.csv")
    snaps = load(out, "snapshots.csv")
    obs = load(out, "observation_text_summary.csv")
    primary = load(out, "branding_corpus_observations_primary.csv")
    sens = load(out, "branding_corpus_observations_sensitivity.csv")
    bp_de = load(out, "branding_corpus_pages_de.csv")
    bp_all = load(out, "branding_corpus_pages_all_languages.csv")
    dup = load(out, "duplicate_summary.csv")
    crawl = load(out, "crawl_priority_summary.csv")
    quality = load(out, "quality_summary.csv")

    if firm_ids:
        fids = {str(f) for f in firm_ids}
        def _fid(df):
            return df[df["firm_id"].astype(str).map(lambda x: str(int(float(x)))).isin(fids)]
        pages, snaps, obs = _fid(pages), _fid(snaps), _fid(obs)
        primary, sens = _fid(primary), _fid(sens)
        bp_de, bp_all = _fid(bp_de), _fid(bp_all)
        dup, crawl, quality = _fid(dup), _fid(crawl), _fid(quality)

    status = snaps["snapshot_status"].fillna("").astype(str).str.lower()
    selected = int((status == "selected").sum())
    missing = int(status.isin(["missing", "no_capture", "unavailable", "failed"]).sum())
    future = int(status.str.contains("future", na=False).sum())
    if "observation_recommendation" in snaps.columns:
        future = int((snaps["observation_recommendation"].fillna("") == "future").sum()) + future

    fetch_ok = int(pages["http_status"].fillna(0).astype(float).eq(200).sum()) if "http_status" in pages else 0
    fetch_fail = int(len(pages) - fetch_ok)
    usable = int(pages["usable_for_analysis"].map(as_bool).sum()) if "usable_for_analysis" in pages else 0

    cats = pages["page_category"].fillna("unknown").value_counts().to_dict() if "page_category" in pages else {}
    lang_col = "detected_language" if "detected_language" in bp_all.columns else "text_language"
    lang_dist = bp_all[lang_col].fillna("unknown").astype(str).str.lower().value_counts().to_dict()

    tokens_removed = int(dup["tokens_removed"].fillna(0).sum()) if "tokens_removed" in dup.columns else 0
    reserved_sel = pages.loc[pages["selected_under_reserved_slot"].map(as_bool)] if "selected_under_reserved_slot" in pages else pages.iloc[0:0]
    reserved_cov = reserved_sel["reserved_slot_category"].fillna("").value_counts().to_dict() if len(reserved_sel) else {}

    return {
        "n_snapshots": len(snaps),
        "snapshots_selected": selected,
        "snapshots_missing_or_failed": missing,
        "snapshots_future_like": future,
        "n_pages": len(pages),
        "pages_http_200": fetch_ok,
        "pages_non_200_or_missing_status": fetch_fail,
        "pages_usable": usable,
        "page_category_counts": cats,
        "duplicate_rows": len(dup),
        "duplicate_tokens_removed": tokens_removed,
        "branding_pages_all": len(bp_all),
        "branding_pages_de": len(bp_de),
        "language_distribution_branding_all": lang_dist,
        "primary_nlp_observations": len(primary),
        "sensitivity_nlp_observations": len(sens),
        "obs_german_eligible": int(obs["german_text_analysis_eligible"].map(as_bool).sum())
        if "german_text_analysis_eligible" in obs
        else None,
        "obs_text_eligible": int(obs["text_analysis_eligible"].map(as_bool).sum())
        if "text_analysis_eligible" in obs
        else None,
        "reserved_slot_coverage": reserved_cov,
        "crawl_high_priority_fetched": int(crawl["n_high_priority_pages_fetched"].sum())
        if "n_high_priority_pages_fetched" in crawl
        else None,
        "quality_rows": len(quality),
    }


def check_invariants(out: Path) -> dict:
    pages = load(out, "pages.csv")
    bp_de = load(out, "branding_corpus_pages_de.csv")
    bp_all = load(out, "branding_corpus_pages_all_languages.csv")
    obs = load(out, "observation_text_summary.csv")
    primary = load(out, "branding_corpus_observations_primary.csv")
    sens = load(out, "branding_corpus_observations_sensitivity.csv")
    failures: list[dict] = []

    # Legal pages in branding
    legal_terms = ("impressum", "agb", "privacy", "datenschutz", "cookie", "disclaimer", "rechtliches")
    for _, r in bp_all.iterrows():
        url = str(r.get("original_archived_url") or "").lower()
        title = str(r.get("document_title") or "").lower()
        cat = str(r.get("page_category") or "").lower()
        if cat in {"impressum", "legal_notice", "privacy_policy", "terms_conditions", "cookie_notice"}:
            failures.append({"invariant": "legal_in_branding", "url": url, "category": cat})
        elif any(t in url for t in legal_terms) and cat not in {"corporate_affiliation", "company_about", "homepage"}:
            # path heuristic only when category also looks legal-ish
            if any(t in title for t in legal_terms):
                failures.append({"invariant": "legal_in_branding_heuristic", "url": url, "title": title})

    # German primary corpus language purity
    lang_col = "detected_language" if "detected_language" in bp_de.columns else "text_language"
    non_de = bp_de.loc[~bp_de[lang_col].fillna("").astype(str).str.lower().eq("de")]
    for _, r in non_de.iterrows():
        failures.append(
            {
                "invariant": "non_german_in_de_corpus",
                "url": r.get("original_archived_url"),
                "lang": r.get(lang_col),
            }
        )

    # Reserved-slot violations
    for _, p in pages.iterrows():
        url = str(p.get("original_archived_url") or "")
        path = str(p.get("path") or urlparse(url).path or "").lower()
        cat = str(p.get("reserved_slot_category") or "")
        reserved_sel = as_bool(p.get("selected_under_reserved_slot"))
        segs = set(normalize_path_segments(path))
        if reserved_sel and cat in RESERVE_CATS:
            if any(m in path for m in LEGAL_MARKERS) and cat != "homepage":
                failures.append({"invariant": "legal_reserved_slot", "url": url, "category": cat})
            if str(p.get("path_language_priority") or "") == "foreign_language_deprioritized":
                failures.append({"invariant": "foreign_reserved_slot", "url": url})
            if cat == "company_about" and (segs & LOW_VALUE_SEGMENTS):
                failures.append({"invariant": "low_value_company_about_reserved", "url": url, "segments": sorted(segs & LOW_VALUE_SEGMENTS)})
            if "unternehmen" in path and "unternehmen" not in segs and cat == "company_about":
                failures.append({"invariant": "unternehmen_substring_reserved", "url": url})

    # Zero analysis tokens on usable substantive pages
    tok_col = "analysis_token_count" if "analysis_token_count" in pages.columns else "token_count"
    for _, r in pages.iterrows():
        if not as_bool(r.get("usable_for_analysis")):
            continue
        chars = r.get("character_count")
        char_n = int(float(chars)) if pd.notna(chars) else 0
        tok = r.get(tok_col)
        tok_n = float(tok) if pd.notna(tok) else 0.0
        if char_n >= 50 and tok_n <= 0:
            failures.append(
                {
                    "invariant": "zero_analysis_tokens_usable",
                    "url": r.get("original_archived_url"),
                    "chars": char_n,
                }
            )
        if "analysis_token_count" in pages.columns and "token_count" in pages.columns:
            if pd.notna(r.get("analysis_token_count")) and pd.notna(r.get("token_count")):
                if float(r["analysis_token_count"]) != float(r["token_count"]):
                    failures.append(
                        {
                            "invariant": "token_count_alias_mismatch",
                            "url": r.get("original_archived_url"),
                        }
                    )

    # Observation eligibility consistency
    for _, r in primary.iterrows():
        if not as_bool(r.get("text_analysis_eligible")):
            failures.append(
                {
                    "invariant": "primary_not_text_eligible",
                    "firm_id": r.get("firm_id"),
                    "tp": r.get("relative_timepoint"),
                }
            )
    for _, r in sens.iterrows():
        if not as_bool(r.get("text_analysis_eligible")):
            failures.append(
                {
                    "invariant": "sensitivity_not_text_eligible",
                    "firm_id": r.get("firm_id"),
                    "tp": r.get("relative_timepoint"),
                }
            )

    # Token sum consistency for eligible observations
    for _, o in obs.iterrows():
        if not as_bool(o.get("text_analysis_eligible")):
            continue
        fid = str(int(float(o["firm_id"])))
        tp = o["relative_timepoint"]
        subset = pages.loc[
            (pages["firm_id"].astype(str).map(lambda x: str(int(float(x)))) == fid)
            & (pages["relative_timepoint"] == tp)
            & pages["branding_corpus_eligible"].map(as_bool)
            & pages["usable_for_analysis"].map(as_bool)
            & ~pages["duplicate_content_flag"].map(as_bool)
        ]
        page_sum = int(subset[tok_col].fillna(0).sum())
        obs_tok = int(o.get("branding_token_count") or 0)
        if page_sum != obs_tok:
            failures.append(
                {
                    "invariant": "obs_page_token_mismatch",
                    "firm_id": fid,
                    "relative_timepoint": tp,
                    "obs": obs_tok,
                    "pages": page_sum,
                }
            )

    # Dedup: branding must not include duplicate_content_flag
    if "duplicate_content_flag" in bp_all.columns:
        n_dup = int(bp_all["duplicate_content_flag"].map(as_bool).sum())
        if n_dup:
            failures.append({"invariant": "branding_contains_duplicates", "n": n_dup})

    return {
        "pass": len(failures) == 0,
        "n_failures": len(failures),
        "failures": failures[:80],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/output")
    parser.add_argument("--batch-label", default="all")
    parser.add_argument("--firm-id", action="append", dest="firm_ids")
    parser.add_argument("--report-dir", default="data/interim/full_sample_batches")
    args = parser.parse_args()

    out = ROOT / args.output_dir
    report_dir = ROOT / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_batch(out, args.firm_ids)
    invariants = check_invariants(out)
    payload = {
        "batch_label": args.batch_label,
        "firm_ids": args.firm_ids,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "invariants": invariants,
    }
    path = report_dir / f"batch_{args.batch_label}_qc.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(json.dumps({"batch": args.batch_label, "pass": invariants["pass"], "n_failures": invariants["n_failures"], "summary": summary}, indent=2, default=str))
    print("wrote", path)
    return 0 if invariants["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
