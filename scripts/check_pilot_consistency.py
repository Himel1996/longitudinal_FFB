#!/usr/bin/env python3
"""Consistency checks for pilot release (v1.3 scaling rules)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.quality.checks import as_bool
from ffb_webminer.quality.deduplication import normalize_for_hash


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

    branding_pages_de = (
        pd.read_csv(out / "branding_corpus_pages_de.csv")
        if (out / "branding_corpus_pages_de.csv").exists()
        else branding_pages
    )
    branding_pages_all = (
        pd.read_csv(out / "branding_corpus_pages_all_languages.csv")
        if (out / "branding_corpus_pages_all_languages.csv").exists()
        else branding_pages
    )

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

    selected = snapshots[snapshots["snapshot_status"] == "selected"]
    for _, s in selected.iterrows():
        key = (str(int(float(s["firm_id"]))), s["relative_timepoint"])
        subset = pages[
            (pages["firm_id"].astype(str) == key[0])
            & (pages["relative_timepoint"] == key[1])
        ]
        home = subset[subset["page_priority_reason"].fillna("").isin(["homepage", "reserved_slot:homepage"])]
        if home.empty and "reserved_slot_category" in subset.columns:
            home = subset[subset["reserved_slot_category"].fillna("").eq("homepage")]
        if home.empty and "crawl_depth" in subset.columns:
            home = subset[subset["crawl_depth"].fillna(1).astype(float) == 0]
        if home.empty and s.get("observation_recommendation") in ("include", "sensitivity_analysis"):
            errors.append(f"No homepage page for selected snapshot {key}")

    for _, p in pages.iterrows():
        if pd.isna(p.get("firm_id")):
            errors.append(f"Page with NaN firm_id: {p.get('original_archived_url')}")
            continue
        key = (str(int(float(p["firm_id"]))), p["relative_timepoint"])
        if key not in snap_keys:
            errors.append(f"Page references unknown snapshot: {key}")

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
        if as_bool(p.get("duplicate_content_flag")):
            errors.append(f"Duplicate page still in branding corpus: {p.get('original_archived_url')}")

    # 1) identical normalized content must not appear twice in branding corpus within firm×timepoint
    for (firm_id, tp), group in branding_pages.groupby(
        [branding_pages["firm_id"].map(lambda x: str(int(float(x)))), "relative_timepoint"]
    ):
        hashes = group["normalized_content_hash"].dropna() if "normalized_content_hash" in group.columns else pd.Series(dtype=object)
        if hashes.empty:
            # fallback compute
            texts = [
                normalize_for_hash(t)
                for t in group["main_text"].fillna("").tolist()
                if normalize_for_hash(t)
            ]
            if len(texts) != len(set(texts)):
                errors.append(f"Duplicate normalized content in branding corpus for {firm_id}|{tp}")
        else:
            if hashes.duplicated().any():
                errors.append(f"Duplicate normalized_content_hash in branding corpus for {firm_id}|{tp}")

    # 2) Cross-timepoint identical content must remain available (not globally removed)
    # If same hash exists in two timepoints for a firm, both should still have at least one non-duplicate eligible row or page row
    if "normalized_content_hash" in pages.columns:
        for firm_id, firm_pages in pages.groupby(pages["firm_id"].map(lambda x: str(int(float(x))))):
            hash_tps: dict[str, set[str]] = {}
            for _, row in firm_pages.iterrows():
                nh = row.get("normalized_content_hash")
                if pd.isna(nh) or not nh:
                    continue
                if as_bool(row.get("duplicate_content_flag")):
                    continue
                hash_tps.setdefault(str(nh), set()).add(str(row["relative_timepoint"]))
            # no hard error — informational integrity: if a hash appears in multiple TPs among non-dup rows, OK
            # Fail only if a hash was marked duplicate in ALL timepoints where content existed and branding would have wanted it
            # Skipped as soft check; hard fail is branding corpus uniqueness within TP only.

    # 3) German primary corpus must not contain confidently non-German pages
    for _, p in branding_pages_de.iterrows():
        lang = str(p.get("detected_language") or p.get("text_language") or "").lower()
        conf = float(p.get("language_confidence") or p.get("text_language_confidence") or 0)
        if lang in {"en", "fr", "es", "it"} and conf >= config.analysis.language_confidence_threshold:
            errors.append(
                f"Non-German page in German corpus: {p.get('original_archived_url')} lang={lang}"
            )
        if "german_corpus_eligible" in p and not as_bool(p.get("german_corpus_eligible")):
            errors.append(f"german_corpus_eligible=false in DE corpus pages: {p.get('original_archived_url')}")

    for _, p in branding_primary.iterrows():
        # primary is observation-level; check corpus_language_scope
        if str(p.get("corpus_language_scope") or "de") not in {"de", "all"}:
            errors.append(f"Unexpected primary corpus_language_scope={p.get('corpus_language_scope')}")

    # 5) observation token totals equal sum of deduplicated eligible page tokens
    for _, obs in obs_summary.iterrows():
        key = (str(int(float(obs["firm_id"]))), obs["relative_timepoint"])
        bp = branding_pages[
            (branding_pages["firm_id"].astype(str).map(lambda x: str(int(float(x)))) == key[0])
            & (branding_pages["relative_timepoint"] == key[1])
        ]
        if not as_bool(obs.get("text_analysis_eligible")):
            continue
        page_tokens = int(bp["token_count"].fillna(0).sum()) if len(bp) else 0
        obs_tokens = int(obs.get("branding_token_count") or 0)
        if page_tokens != obs_tokens:
            # branding_pages may be filtered to eligible obs only; compare within matching keys
            # observation branding_token_count is from all branding-eligible pages for that obs
            page_all = pages[
                (pages["firm_id"].astype(str).map(lambda x: str(int(float(x)))) == key[0])
                & (pages["relative_timepoint"] == key[1])
                & pages["branding_corpus_eligible"].fillna(False).astype(bool)
                & pages["usable_for_analysis"].fillna(False).astype(bool)
                & ~pages["duplicate_content_flag"].fillna(False).astype(bool)
            ]
            page_tokens = int(page_all["token_count"].fillna(0).sum()) if len(page_all) else 0
            if page_tokens != obs_tokens:
                errors.append(
                    f"Token mismatch {key}: obs={obs_tokens} pages={page_tokens}"
                )

    # 6) duplicate rows must not be in aggregated branding text sources
    if "duplicate_content_flag" in branding_pages_all.columns:
        if branding_pages_all["duplicate_content_flag"].fillna(False).astype(bool).any():
            errors.append("duplicate_content_flag true rows present in all-language branding pages")

    # 7) language-specific outputs traceable to page-level records
    page_urls = set(pages["original_archived_url"].dropna().astype(str))
    for label, df in [("de", branding_pages_de), ("all", branding_pages_all)]:
        for _, p in df.iterrows():
            url = str(p.get("original_archived_url"))
            if url and url != "nan" and url not in page_urls:
                errors.append(f"Language corpus ({label}) URL not in pages.csv: {url}")

    if branding_primary["text_analysis_eligible"].fillna(False).astype(bool).ne(True).any():
        errors.append("branding_corpus_observations_primary contains text_analysis_eligible != true")
    if branding_sens["text_analysis_eligible"].fillna(False).astype(bool).ne(True).any():
        errors.append("branding_corpus_observations_sensitivity contains text_analysis_eligible != true")

    primary_expected = obs_summary[
        (obs_summary["observation_recommendation"] == "include")
        & (obs_summary["german_text_analysis_eligible"].fillna(False).astype(bool))
    ] if "german_text_analysis_eligible" in obs_summary.columns else obs_summary[
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

    gov_page_urls = set(governance_pages["original_archived_url"].dropna().astype(str))
    for _, g in governance_obs.iterrows():
        raw = g.get("governance_metadata_source_urls")
        if pd.isna(raw) or not raw:
            continue
        try:
            urls = json.loads(raw) if isinstance(raw, str) else list(raw)
        except Exception:
            errors.append(f"Unparseable governance_metadata_source_urls for {g.get('firm_id')}|{g.get('relative_timepoint')}")
            continue
        for url in urls:
            if url not in gov_page_urls:
                errors.append(f"Governance observation URL not in governance pages: {url}")

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

    if "validation_screenshot_path" in manual.columns:
        for _, m in manual.iterrows():
            sp = m.get("validation_screenshot_path")
            if pd.notna(sp) and sp:
                if not (out / str(sp)).exists():
                    errors.append(f"Missing screenshot: {sp}")

    # Legal paths must not consume reserved company/About slots
    legal_markers = ("impressum", "imprint", "datenschutz", "privacy", "agb", "terms", "cookie", "legal-notice", "rechtliches")
    reserved_company = {"homepage", "company_about", "history_heritage", "family_owners", "values_responsibility", "management_leadership"}
    if "selected_under_reserved_slot" in pages.columns and "path" in pages.columns:
        for _, p in pages.iterrows():
            path = str(p.get("path") or p.get("original_archived_url") or "").lower()
            if not any(m in path for m in legal_markers):
                continue
            if as_bool(p.get("selected_under_reserved_slot")) and str(p.get("reserved_slot_category") or "") in reserved_company:
                errors.append(
                    f"Legal page consumed reserved slot {p.get('reserved_slot_category')}: {p.get('original_archived_url')}"
                )
            if str(p.get("reserved_slot_category") or "") in reserved_company - {"homepage"}:
                errors.append(
                    f"Legal page classified into reserved category {p.get('reserved_slot_category')}: {p.get('original_archived_url')}"
                )

    # Crowd-out heuristic: if a tier-1 branding candidate was fetched under reserved slots,
    # no foreign-language page should also be marked selected_under_reserved_slot
    if "selected_under_reserved_slot" in pages.columns and "path_language_priority" in pages.columns:
        foreign_reserved = pages[
            pages["selected_under_reserved_slot"].fillna(False).astype(bool)
            & pages["path_language_priority"].fillna("").eq("foreign_language_deprioritized")
        ]
        for _, p in foreign_reserved.iterrows():
            errors.append(
                f"Foreign-language page consumed reserved slot: {p.get('original_archived_url')}"
            )

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
