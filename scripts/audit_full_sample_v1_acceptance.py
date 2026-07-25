#!/usr/bin/env python3
"""Final release acceptance audit for full_sample_v1 (read-only verification)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.crawl.priority import classify_path_match, normalize_path_segments

REL = ROOT / "data/releases/full_sample_v1"
REL_DATA = REL / "data"
REL_REPORTS = REL / "reports"
PILOT = ROOT / "data/releases/pilot_v1_4_1/data"
if not PILOT.exists():
    PILOT = ROOT / "data/archive/pilot_v1_4_pre_v1_4_1/data"

REQUIRED_DATA = [
    "firms.csv",
    "run_manifest.json",
    "full_sample_snapshots.csv",
    "full_sample_pages.csv",
    "full_sample_branding_corpus_pages_de.csv",
    "full_sample_branding_corpus_pages_all_languages.csv",
    "full_sample_branding_corpus_observations_primary.csv",
    "full_sample_branding_corpus_observations_sensitivity.csv",
    "full_sample_governance_metadata_pages.csv",
    "full_sample_governance_metadata_observations.csv",
    "full_sample_observation_text_summary.csv",
    "full_sample_quality_summary.csv",
    "full_sample_duplicate_summary.csv",
    "full_sample_crawl_priority_summary.csv",
]

REQUIRED_REPORTS = [
    "full_sample_quality_report.md",
    "full_sample_manual_validation_report.md",
    "full_sample_readiness.md",
    "full_sample_reproducibility.md",
    "full_sample_baseline_freeze.md",
]

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

LEGAL_CATS = {
    "impressum",
    "legal_notice",
    "privacy_policy",
    "terms_conditions",
    "cookie_notice",
    "legal_other",
    "technical_system",
}

LEGAL_URL_TERMS = (
    "impressum",
    "imprint",
    "datenschutz",
    "datenschutzerklaerung",
    "datenschutzerklärung",
    "privacy",
    "agb",
    "/terms",
    "terms-conditions",
    "terms_conditions",
    "cookie",
    "disclaimer",
    "legal-notice",
    "legal_notice",
    "rechtliches",
)

LEGAL_TITLE_TERMS = (
    "impressum",
    "imprint",
    "datenschutz",
    "privacy",
    "agb",
    "disclaimer",
    "cookie",
    "legal notice",
    "terms and conditions",
    "terms & conditions",
    "allgemeine geschäftsbedingungen",
)

GOV_ALLOWED = {
    "impressum",
    "legal_notice",
    "management_legal_representatives",
    "corporate_affiliation",
    "ownership",
    "legal_other",  # narrow; validated separately
}

GOV_REJECT_HINTS = (
    "product",
    "produkte",
    "service",
    "karriere",
    "career",
    "jobs",
    "geschichte",
    "history",
    "heritage",
)


def as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def fid(v) -> str:
    return str(int(float(v)))


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(REL_DATA / name)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_diff_names(a: str, b: str, paths: list[str]) -> list[str]:
    raw = subprocess.check_output(
        ["git", "diff", "--name-only", f"{a}..{b}", "--", *paths],
        cwd=ROOT,
        text=True,
    ).strip()
    return [x for x in raw.splitlines() if x.strip()]


def section(results: dict, key: str, name: str, passed: bool, **payload) -> None:
    results[key] = {"name": name, "pass": bool(passed), **payload}


def main() -> int:
    results: dict = {
        "audit": "full_sample_v1_final_release_acceptance",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "release_path": str(REL),
    }
    blocking: list[str] = []

    # ---------- SECTION 1 ----------
    missing_data = [f for f in REQUIRED_DATA if not (REL_DATA / f).exists()]
    missing_reports = [f for f in REQUIRED_REPORTS if not (REL_REPORTS / f).exists()]
    manifest = json.loads((REL_DATA / "run_manifest.json").read_text())
    head = git_head()
    manifest_commit = str(manifest.get("git_commit") or "")
    run_id = str(manifest.get("run_id") or "")
    config_hash_now = sha256(ROOT / "config/full_sample.yaml")
    freeze_text = (REL_REPORTS / "full_sample_baseline_freeze.md").read_text(encoding="utf-8")
    config_hash_documented = "2e3c987c0cb13b2c248d75275d4cacf16370741d791085b43f65079a9622c58b"
    config_hash_match = config_hash_now == config_hash_documented and config_hash_documented in freeze_text

    run_id_issues = []
    for f in REL_DATA.glob("*.csv"):
        df = pd.read_csv(f)
        if "run_id" not in df.columns:
            if f.name == "manual_scaling_validation.csv":
                continue
            run_id_issues.append({"file": f.name, "issue": "missing_run_id_column"})
            continue
        bad = df.loc[df["run_id"].astype(str) != run_id]
        if len(bad):
            run_id_issues.append({"file": f.name, "issue": "stale_or_mixed_run_id", "n": len(bad)})

    pipeline_paths = ["src", "config/full_sample.yaml", "config/event_dates.yaml", "config/pilot.yaml", "pyproject.toml"]
    code_diff = git_diff_names(manifest_commit, head, pipeline_paths) if manifest_commit else ["missing_manifest_commit"]
    # extraction-critical paths only
    src_diff = git_diff_names(manifest_commit, head, ["src", "config/event_dates.yaml", "pyproject.toml"]) if manifest_commit else []
    exact_commit_match = manifest_commit == head
    # Manifest records the extraction-producing commit. HEAD may advance for packaging /
    # QC tooling only. Freeze requires: no extraction-code drift + matching config hash.
    packaging_only_drift = (not exact_commit_match) and (len(src_diff) == 0)
    s1_pass = (
        not missing_data
        and not missing_reports
        and config_hash_match
        and len(run_id_issues) == 0
        and len(src_diff) == 0
        and (exact_commit_match or packaging_only_drift)
    )
    if src_diff:
        blocking.append("section1_src_drift")
    if missing_data or missing_reports or run_id_issues or not config_hash_match:
        blocking.append("section1_bundle_or_metadata")
    if not exact_commit_match and not packaging_only_drift:
        blocking.append("section1_manifest_commit_ne_head")

    section(
        results,
        "section1",
        "Reproducibility",
        s1_pass,
        missing_data=missing_data,
        missing_reports=missing_reports,
        manifest_commit=manifest_commit,
        git_head=head,
        exact_commit_match=exact_commit_match,
        packaging_only_drift=packaging_only_drift,
        src_config_diff_since_manifest=src_diff,
        tooling_diff_since_manifest=code_diff,
        config_hash_now=config_hash_now,
        config_hash_documented=config_hash_documented,
        config_hash_match=config_hash_match,
        run_id=run_id,
        run_id_issues=run_id_issues,
        note=(
            "Manifest commit equals HEAD."
            if exact_commit_match
            else (
                "Manifest commit records extraction code; HEAD differs by packaging/tooling only "
                "(no src/event_dates/pyproject drift). Config hash still matches freeze docs."
                if packaging_only_drift
                else "Manifest commit differs from HEAD with extraction-relevant drift."
            )
        ),
    )

    pages = load("full_sample_pages.csv")
    snaps = load("full_sample_snapshots.csv")
    obs = load("full_sample_observation_text_summary.csv")
    primary = load("full_sample_branding_corpus_observations_primary.csv")
    sens = load("full_sample_branding_corpus_observations_sensitivity.csv")
    bp_all = load("full_sample_branding_corpus_pages_all_languages.csv")
    bp_de = load("full_sample_branding_corpus_pages_de.csv")
    gov = load("full_sample_governance_metadata_pages.csv")
    gov_obs = load("full_sample_governance_metadata_observations.csv")
    dup = load("full_sample_duplicate_summary.csv")
    quality = load("full_sample_quality_summary.csv")
    crawl = load("full_sample_crawl_priority_summary.csv")

    for df in (pages, snaps, obs, primary, sens, bp_all, bp_de, gov, gov_obs, dup, quality, crawl):
        if "firm_id" in df.columns:
            df["firm_id"] = df["firm_id"].map(fid)

    # ---------- SECTION 2 ----------
    status = snaps["snapshot_status"].fillna("").astype(str).str.lower()
    rec = snaps.get("observation_recommendation", pd.Series([""] * len(snaps))).fillna("").astype(str)
    future_flags = snaps.get("observation_is_future", pd.Series([False] * len(snaps))).map(as_bool)
    selected_n = int((status == "selected").sum())
    beyond = int((status == "beyond_tolerance").sum())
    future_unavail = int(status.str.contains("future", na=False).sum())
    event_unavail = int((status == "event_unavailable").sum())
    # silent substitution heuristic: selected rows with empty archive timestamp
    silent = snaps.loc[(status == "selected") & snaps["archive_timestamp"].isna()]
    # future selected incorrectly
    future_selected = snaps.loc[future_flags & (status == "selected")]
    # sensitivity identified
    sens_rec = int((rec == "sensitivity_analysis").sum())
    # beyond-tolerance should not be selected
    beyond_selected = snaps.loc[(status == "beyond_tolerance")]  # status itself
    s2_pass = len(silent) == 0 and len(future_selected) == 0 and selected_n == int(manifest.get("counts", {}).get("snapshots_selected", selected_n))
    if not s2_pass:
        blocking.append("section2_snapshot_policy")
    section(
        results,
        "section2",
        "Snapshot quality",
        s2_pass,
        total_observations=len(snaps),
        selected=selected_n,
        beyond_tolerance=beyond,
        future_unavailable=future_unavail,
        event_unavailable=event_unavail,
        unavailable_total=beyond + future_unavail + event_unavail + int((status == "unavailable").sum()),
        sensitivity_recommendations=sens_rec,
        include_recommendations=int((rec == "include").sum()),
        exclude_recommendations=int((rec == "exclude").sum()),
        silent_substitution_selected_missing_timestamp=len(silent),
        future_incorrectly_selected=len(future_selected),
        status_counts=status.value_counts().to_dict(),
        recommendation_counts=rec.value_counts().to_dict(),
    )

    # ---------- SECTION 3 ----------
    legal_violations = []
    for _, r in bp_all.iterrows():
        cat = str(r.get("page_category") or "").lower()
        url = str(r.get("original_archived_url") or "")
        path = str(r.get("path") or urlparse(url).path or "").lower()
        title = str(r.get("document_title") or "").lower()
        h1 = str(r.get("h1_text") or "").lower()
        reasons = []
        if cat in LEGAL_CATS:
            reasons.append(f"category:{cat}")
        if any(t in path or t in url.lower() for t in LEGAL_URL_TERMS):
            # allow if clearly non-legal branding category and term only incidental? Still flag URL hits for audit.
            if cat in LEGAL_CATS or any(t in title or t in h1 for t in LEGAL_TITLE_TERMS):
                reasons.append("url_or_path_legal_term")
            elif any(t in path for t in ("/impressum", "/datenschutz", "/agb", "/privacy", "terms-conditions", "/cookie")):
                reasons.append("path_legal_term")
        if any(t in title or t in h1 for t in LEGAL_TITLE_TERMS) and cat in LEGAL_CATS.union({"unknown", "contact"}):
            reasons.append("title_h1_legal")
        if reasons:
            legal_violations.append(
                {
                    "url": url,
                    "category": cat,
                    "title": title[:120],
                    "h1": h1[:80],
                    "reasons": reasons,
                    "firm_id": r.get("firm_id"),
                    "relative_timepoint": r.get("relative_timepoint"),
                }
            )
    # Stricter: any LEGAL_CATS in branding is always a fail
    legal_cat_hits = [v for v in legal_violations if any(x.startswith("category:") for x in v["reasons"])]
    s3_pass = len(legal_cat_hits) == 0
    # Also fail on clear path legal pages even if miscategorized
    path_legal = [
        v
        for v in legal_violations
        if "path_legal_term" in v["reasons"] or "url_or_path_legal_term" in v["reasons"]
    ]
    if path_legal:
        s3_pass = False
    if not s3_pass:
        blocking.append("section3_legal_in_branding")
    section(
        results,
        "section3",
        "Legal page exclusion",
        s3_pass,
        n_branding_pages=len(bp_all),
        n_category_violations=len(legal_cat_hits),
        n_path_title_violations=len(path_legal),
        violations=(legal_cat_hits + path_legal)[:50],
    )

    # ---------- SECTION 4 ----------
    gov_violations = []
    for _, r in gov.iterrows():
        cat = str(r.get("page_category") or "").lower()
        url = str(r.get("original_archived_url") or "").lower()
        title = str(r.get("document_title") or "").lower()
        if cat not in GOV_ALLOWED and cat not in {"", "nan"}:
            # allow legal_other only with legal evidence
            if cat == "legal_other" and any(t in url or t in title for t in ("impressum", "legal", "agb", "datenschutz")):
                continue
            gov_violations.append({"url": r.get("original_archived_url"), "category": cat, "reason": "disallowed_category"})
        if any(h in url for h in GOV_REJECT_HINTS) and cat not in {"impressum", "legal_notice", "management_legal_representatives", "corporate_affiliation"}:
            gov_violations.append({"url": r.get("original_archived_url"), "category": cat, "reason": "reject_url_hint"})
    s4_pass = len(gov_violations) == 0
    if not s4_pass:
        blocking.append("section4_governance_scope")
    section(
        results,
        "section4",
        "Governance layer",
        s4_pass,
        n_gov_pages=len(gov),
        category_distribution=gov["page_category"].fillna("NA").value_counts().to_dict(),
        n_violations=len(gov_violations),
        violations=gov_violations[:40],
    )

    # ---------- SECTION 5 ----------
    pri_bad = primary.loc[~primary["text_analysis_eligible"].map(as_bool)] if "text_analysis_eligible" in primary.columns else primary.iloc[0:0]
    sens_bad = sens.loc[~sens["text_analysis_eligible"].map(as_bool)] if "text_analysis_eligible" in sens.columns else sens.iloc[0:0]
    s5_pass = len(pri_bad) == 0 and len(sens_bad) == 0
    if not s5_pass:
        blocking.append("section5_eligibility")
    section(
        results,
        "section5",
        "Observation eligibility",
        s5_pass,
        primary_n=len(primary),
        sensitivity_n=len(sens),
        primary_ineligible=len(pri_bad),
        sensitivity_ineligible=len(sens_bad),
    )

    # ---------- SECTION 6 ----------
    within_dups = []
    for (f, tp), g in bp_all.groupby(["firm_id", "relative_timepoint"]):
        if "normalized_content_hash" not in g.columns:
            continue
        h = g["normalized_content_hash"].dropna()
        if h.duplicated().any():
            within_dups.append({"firm_id": f, "relative_timepoint": tp, "n": int(h.duplicated().sum())})
    branding_dup_flag = int(bp_all["duplicate_content_flag"].map(as_bool).sum()) if "duplicate_content_flag" in bp_all.columns else 0
    # cross-time preserve
    non_dup = pages.loc[pages["normalized_content_hash"].notna() & ~pages["duplicate_content_flag"].map(as_bool)]
    multi = non_dup.groupby(["firm_id", "normalized_content_hash"])["relative_timepoint"].nunique()
    cross_preserved = int((multi > 1).sum())
    # www / scheme alias evidence: duplicate_summary reasons
    reasons = dup["duplicate_reason"].fillna("").astype(str).str.lower() if "duplicate_reason" in dup.columns else pd.Series(dtype=str)
    s6_pass = len(within_dups) == 0 and branding_dup_flag == 0 and cross_preserved > 0
    if not s6_pass:
        blocking.append("section6_duplicates")
    section(
        results,
        "section6",
        "Duplicate handling",
        s6_pass,
        within_timepoint_duplicate_groups_in_branding=within_dups,
        branding_pages_with_duplicate_flag=branding_dup_flag,
        duplicate_summary_rows=len(dup),
        duplicate_tokens_removed=int(dup["tokens_removed"].fillna(0).sum()) if "tokens_removed" in dup.columns else None,
        preserved_longitudinal_duplicate_groups=cross_preserved,
        duplicate_reason_top=reasons.value_counts().head(15).to_dict() if len(reasons) else {},
    )

    # ---------- SECTION 7 ----------
    lang_col = "detected_language" if "detected_language" in bp_de.columns else "text_language"
    de_langs = bp_de[lang_col].fillna("").astype(str).str.lower()
    non_de = bp_de.loc[~de_langs.eq("de"), "original_archived_url"].astype(str).tolist()
    en_in_de = bp_de.loc[de_langs.eq("en"), "original_archived_url"].astype(str).tolist()
    unk_in_de = bp_de.loc[de_langs.isin(["unknown", "nan", ""]), "original_archived_url"].astype(str).tolist()
    # DE corpus = all-language branding pages that are german_corpus_eligible AND whose
    # observation is german_text_analysis_eligible (require_german_observation=True).
    all_lang = bp_all[lang_col if lang_col in bp_all.columns else "text_language"].fillna("").astype(str).str.lower()
    german_obs_keys = set(
        zip(
            obs.loc[obs["german_text_analysis_eligible"].map(as_bool), "firm_id"].map(fid),
            obs.loc[obs["german_text_analysis_eligible"].map(as_bool), "relative_timepoint"].astype(str),
        )
    ) if "german_text_analysis_eligible" in obs.columns else set()
    expected_de = bp_all.loc[
        all_lang.eq("de")
        & bp_all["german_corpus_eligible"].map(as_bool)
        & bp_all.apply(lambda r: (fid(r["firm_id"]), str(r["relative_timepoint"])) in german_obs_keys, axis=1)
    ].copy() if "german_corpus_eligible" in bp_all.columns else bp_all.loc[all_lang.eq("de")].copy()
    keys = ["firm_id", "relative_timepoint", "original_archived_url"]
    expected_keys = set(map(tuple, expected_de[keys].fillna("").astype(str).values.tolist()))
    actual_keys = set(map(tuple, bp_de[keys].fillna("").astype(str).values.tolist()))
    partition_ok = expected_keys == actual_keys
    partition_missing = sorted(expected_keys - actual_keys)[:20]
    partition_extra = sorted(actual_keys - expected_keys)[:20]
    # German token totals: observation tokens_de must equal sum over German branding pages
    tok_page = "analysis_token_count" if "analysis_token_count" in pages.columns else "token_count"
    if "german_corpus_eligible" in pages.columns:
        mask_de = (
            pages["german_corpus_eligible"].map(as_bool)
            & pages["branding_corpus_eligible"].map(as_bool)
            & pages["usable_for_analysis"].map(as_bool)
            & ~pages["duplicate_content_flag"].map(as_bool)
        )
    else:
        mask_de = (
            pages["detected_language"].fillna("").astype(str).str.lower().eq("de")
            & pages["branding_corpus_eligible"].map(as_bool)
            & pages["usable_for_analysis"].map(as_bool)
            & ~pages["duplicate_content_flag"].map(as_bool)
        )
    de_pages_tokens = int(pages.loc[mask_de, tok_page].fillna(0).sum())
    tok_col = "analysis_token_count" if "analysis_token_count" in bp_de.columns else "token_count"
    de_branding_token_sum = int(bp_de[tok_col].fillna(0).sum()) if tok_col in bp_de.columns else None
    tokens_de_obs = int(obs["tokens_de"].fillna(0).sum()) if "tokens_de" in obs.columns else None
    # tokens_de on observations includes German pages even when observation is EN-primary;
    # DE file only includes german_text_analysis_eligible observations — both must be internally consistent.
    token_de_ok = tokens_de_obs is None or de_pages_tokens == tokens_de_obs
    de_file_vs_expected_tokens_ok = True
    if de_branding_token_sum is not None and tok_col in expected_de.columns:
        de_file_vs_expected_tokens_ok = de_branding_token_sum == int(expected_de[tok_col].fillna(0).sum())
    s7_pass = (
        len(non_de) == 0
        and len(en_in_de) == 0
        and len(unk_in_de) == 0
        and partition_ok
        and token_de_ok
        and de_file_vs_expected_tokens_ok
    )
    if not s7_pass:
        blocking.append("section7_language")
    section(
        results,
        "section7",
        "Language handling",
        s7_pass,
        n_de=len(bp_de),
        n_all=len(bp_all),
        n_de_pages_in_all_languages=int(all_lang.eq("de").sum()),
        n_expected_de_under_german_observation_gate=len(expected_de),
        non_german_in_de_corpus=non_de[:20],
        english_in_de_corpus=en_in_de[:20],
        unknown_in_de_corpus=unk_in_de[:20],
        de_partition_matches_all_language_filter=partition_ok,
        partition_missing_from_de_file=partition_missing,
        partition_extra_in_de_file=partition_extra,
        tokens_de_observation_sum=tokens_de_obs,
        tokens_de_from_german_eligible_pages=de_pages_tokens,
        de_branding_file_token_sum=de_branding_token_sum,
        language_dist_all=all_lang.value_counts().to_dict(),
        note=(
            "German page file is gated by german_text_analysis_eligible observations; "
            "German pages in EN-primary observations remain in all-languages only."
        ),
    )

    # ---------- SECTION 8 ----------
    legal_reserved = []
    foreign_reserved = []
    low_took = []
    substring_false = []
    for _, p in pages.iterrows():
        url = str(p.get("original_archived_url") or "")
        path = str(p.get("path") or urlparse(url).path or "").lower()
        cat = str(p.get("reserved_slot_category") or "")
        reserved_sel = as_bool(p.get("selected_under_reserved_slot"))
        segs = set(normalize_path_segments(path))
        if reserved_sel and cat in RESERVE_CATS:
            if any(m in path for m in ("impressum", "imprint", "datenschutz", "privacy", "agb", "cookie", "disclaimer", "rechtliches", "terms-conditions", "legal-notice")) and cat != "homepage":
                # require legal segment, not bare substring in about path alone
                if segs & {"impressum", "imprint", "datenschutz", "privacy", "agb", "cookie", "cookies", "disclaimer", "rechtliches", "terms", "terms-conditions", "terms_conditions", "legal-notice", "legal_notice"}:
                    legal_reserved.append(url)
            if str(p.get("path_language_priority") or "") == "foreign_language_deprioritized":
                foreign_reserved.append(url)
            if cat == "company_about" and (segs & LOW_VALUE_SEGMENTS):
                low_took.append(url)
            if "unternehmen" in path and "unternehmen" not in segs and cat == "company_about":
                substring_false.append(url)
            if reserved_sel and cat == "company_about" and (segs & LOW_VALUE_SEGMENTS):
                low_took.append(url)
        if reserved_sel and cat in RESERVE_CATS and (segs & LOW_VALUE_SEGMENTS) and cat != "homepage":
            # careers/news under reserved high cats
            if cat in RESERVE_CATS - {"homepage"}:
                low_took.append(url)

    # ordering: reserved high before low within observations
    order_issues = []
    order_ok = 0
    for (f, tp), g in pages.groupby(["firm_id", "relative_timepoint"]):
        if "crawl_budget_position" not in g.columns:
            continue
        g = g.dropna(subset=["crawl_budget_position"])
        if g.empty:
            continue
        high = g.loc[g["selected_under_reserved_slot"].map(as_bool) & g["reserved_slot_category"].fillna("").isin(RESERVE_CATS)]
        low = g.loc[g["path"].fillna("").astype(str).map(lambda p: bool(set(normalize_path_segments(str(p).lower())) & LOW_VALUE_SEGMENTS))]
        if len(high) and len(low):
            if float(high["crawl_budget_position"].min()) <= float(low["crawl_budget_position"].min()):
                order_ok += 1
            else:
                order_issues.append({"firm_id": f, "relative_timepoint": tp})
        elif len(high):
            order_ok += 1

    s8_pass = (
        len(set(legal_reserved)) == 0
        and len(set(foreign_reserved)) == 0
        and len(set(low_took)) == 0
        and len(set(substring_false)) == 0
        and len(order_issues) == 0
    )
    if not s8_pass:
        blocking.append("section8_reserved")
    section(
        results,
        "section8",
        "Reserved-slot prioritization",
        s8_pass,
        legal_pages_consuming_reserved_slots=sorted(set(legal_reserved))[:30],
        foreign_pages_consuming_reserved_slots=sorted(set(foreign_reserved))[:30],
        news_careers_products_consuming_reserved=sorted(set(low_took))[:30],
        unternehmen_substring_false_company_about=sorted(set(substring_false))[:30],
        observations_order_ok=order_ok,
        observations_order_issues=order_issues[:20],
        reserved_coverage=pages.loc[pages["selected_under_reserved_slot"].map(as_bool), "reserved_slot_category"]
        .fillna("")
        .value_counts()
        .to_dict(),
        crawl_high_priority_fetched=int(crawl["n_high_priority_pages_fetched"].sum())
        if "n_high_priority_pages_fetched" in crawl.columns
        else None,
    )

    # ---------- SECTION 9 ----------
    tok_col = "analysis_token_count" if "analysis_token_count" in pages.columns else "token_count"
    zero_tok = []
    method_issues = []
    for _, r in pages.iterrows():
        if not as_bool(r.get("usable_for_analysis")):
            continue
        chars = r.get("character_count")
        char_n = int(float(chars)) if pd.notna(chars) else 0
        tok = r.get(tok_col)
        tok_n = float(tok) if pd.notna(tok) else 0.0
        if char_n >= 50 and tok_n <= 0:
            zero_tok.append({"url": r.get("original_archived_url"), "chars": char_n})
        if "analysis_token_count" in pages.columns and "token_count" in pages.columns:
            if pd.notna(r.get("analysis_token_count")) and pd.notna(r.get("token_count")):
                if float(r["analysis_token_count"]) != float(r["token_count"]):
                    method_issues.append(str(r.get("original_archived_url")))
        method = str(r.get("tokenization_method") or "")
        lang = str(r.get("detected_language") or r.get("text_language") or "").lower()
        # soft method checks
        if tok_n > 0 and lang in {"zh", "ja", "ko"} and method and method != "unicode_cjk_chars":
            method_issues.append(f"cjk_method:{r.get('original_archived_url')}")
    mismatches = []
    for _, o in obs.iterrows():
        if not as_bool(o.get("text_analysis_eligible")):
            continue
        f = fid(o["firm_id"])
        tp = o["relative_timepoint"]
        subset = pages.loc[
            (pages["firm_id"] == f)
            & (pages["relative_timepoint"] == tp)
            & pages["branding_corpus_eligible"].map(as_bool)
            & pages["usable_for_analysis"].map(as_bool)
            & ~pages["duplicate_content_flag"].map(as_bool)
        ]
        page_sum = int(subset[tok_col].fillna(0).sum())
        obs_tok = int(o.get("branding_token_count") or 0)
        if page_sum != obs_tok:
            mismatches.append({"firm_id": f, "relative_timepoint": tp, "obs": obs_tok, "pages": page_sum})
    s9_pass = len(zero_tok) == 0 and len(mismatches) == 0 and len(method_issues) == 0
    if not s9_pass:
        blocking.append("section9_tokens")
    section(
        results,
        "section9",
        "Tokenization",
        s9_pass,
        policy="token_count == analysis_token_count (choice A)",
        zero_analysis_token_usable_pages=zero_tok[:30],
        observation_vs_page_mismatches=mismatches[:30],
        method_or_alias_issues=method_issues[:30],
        tokenization_method_counts=pages["tokenization_method"].fillna("NA").value_counts().to_dict()
        if "tokenization_method" in pages.columns
        else {},
    )

    # ---------- SECTION 10 ----------
    q_issues = []
    for _, q in quality.iterrows():
        attempted = int(q.get("pages_attempted") or 0)
        success = int(q.get("pages_fetch_success") or 0)
        failed = int(q.get("pages_fetch_failed") or 0)
        usable = int(q.get("pages_extraction_usable") or 0)
        branding = int(q.get("pages_branding_eligible") or 0)
        key = f"{q.get('firm_id')}|{q.get('relative_timepoint')}"
        if attempted != success + failed:
            q_issues.append(f"{key}: attempted != success+failed")
        if success < usable:
            q_issues.append(f"{key}: success < usable")
        if usable < branding:
            q_issues.append(f"{key}: usable < branding")
        if min(attempted, success, failed, usable, branding) < 0:
            q_issues.append(f"{key}: negative")
    s10_pass = len(q_issues) == 0
    if not s10_pass:
        blocking.append("section10_quality")
    section(
        results,
        "section10",
        "Quality summary",
        s10_pass,
        n_rows=len(quality),
        issues=q_issues[:40],
    )

    # ---------- SECTION 11 ----------
    flags = []
    min_tokens = 100
    for _, o in obs.iterrows():
        f, tp = fid(o["firm_id"]), o["relative_timepoint"]
        subset = pages.loc[(pages["firm_id"] == f) & (pages["relative_timepoint"] == tp)]
        branding = subset.loc[
            subset["branding_corpus_eligible"].map(as_bool)
            & subset["usable_for_analysis"].map(as_bool)
            & ~subset["duplicate_content_flag"].map(as_bool)
        ]
        cats = branding["page_category"].fillna("").astype(str)
        item = {
            "firm_id": f,
            "relative_timepoint": tp,
            "branding_pages": len(branding),
            "branding_tokens": int(o.get("branding_token_count") or 0),
            "german_pages": int(branding["detected_language"].fillna("").astype(str).str.lower().eq("de").sum())
            if "detected_language" in branding.columns
            else None,
            "flags": [],
        }
        if len(branding) == 0:
            item["flags"].append("branding_pages_zero")
        if int(o.get("branding_token_count") or 0) < min_tokens:
            item["flags"].append("branding_tokens_below_threshold")
        if len(branding) and cats.isin(["navigation_only"]).all():
            item["flags"].append("only_navigation")
        if len(branding) and cats.isin(["contact"]).all():
            item["flags"].append("only_contact")
        if len(branding) and cats.isin(["news_press"]).all():
            item["flags"].append("only_news")
        if item["flags"]:
            flags.append(item)
    section(
        results,
        "section11",
        "Branding corpus quality (review flags)",
        True,  # informational
        n_flagged_observations=len(flags),
        flagged_observations=flags[:80],
        note="Flags are for review and do not by themselves fail the release.",
    )

    # ---------- SECTION 12 ----------
    # Every governance observation must have ≥1 governance page OR be explicitly unavailable.
    # impressum_available only flags impressum/legal-notice; affiliation/ownership/representatives
    # may populate governance pages with impressum_available=False.
    gov_issues = []
    n_explicit_unavailable = 0
    n_with_pages = 0
    for _, o in gov_obs.iterrows():
        f, tp = fid(o["firm_id"]), str(o["relative_timepoint"])
        gpages = gov.loc[(gov["firm_id"].map(fid) == f) & (gov["relative_timepoint"].astype(str) == tp)]
        impressum_avail = as_bool(o.get("impressum_available")) if "impressum_available" in o.index else None
        source_urls = str(o.get("governance_metadata_source_urls") or "").strip().lower()
        has_pages = len(gpages) > 0
        if has_pages:
            n_with_pages += 1
            continue
        explicit = impressum_avail is False or source_urls in {"", "nan", "none", "[]"}
        snap = snaps.loc[(snaps["firm_id"] == f) & (snaps["relative_timepoint"].astype(str) == tp)]
        if len(snap) and str(snap.iloc[0].get("snapshot_status")).lower() != "selected":
            explicit = True
        if explicit:
            n_explicit_unavailable += 1
        else:
            gov_issues.append(
                {
                    "firm_id": f,
                    "relative_timepoint": tp,
                    "issue": "no_governance_page_and_not_marked_unavailable",
                    "impressum_available": impressum_avail,
                }
            )
    s12_pass = len(gov_issues) == 0 and (n_with_pages + n_explicit_unavailable == len(gov_obs))
    if not s12_pass:
        blocking.append("section12_governance_quality")
    section(
        results,
        "section12",
        "Governance quality",
        s12_pass,
        n_gov_observations=len(gov_obs),
        n_gov_pages=len(gov),
        n_observations_with_governance_pages=n_with_pages,
        n_explicitly_unavailable=n_explicit_unavailable,
        impressum_true_observations=int(gov_obs["impressum_available"].map(as_bool).sum())
        if "impressum_available" in gov_obs.columns
        else None,
        issues=gov_issues[:40],
        note=(
            "Zero governance pages with impressum_available=False counts as explicitly unavailable."
        ),
    )

    # ---------- SECTION 13 ----------
    sample_path = REL_DATA / "full_sample_manual_validation.csv"
    sample = pd.read_csv(sample_path) if sample_path.exists() else pd.DataFrame()
    # automated evidence checks on stratified sample
    sample_checks = []
    if len(sample):
        sample["firm_id"] = sample["firm_id"].map(fid)
        for _, row in sample.iterrows():
            f, tp = row["firm_id"], row["relative_timepoint"]
            snap = snaps.loc[(snaps["firm_id"] == f) & (snaps["relative_timepoint"] == tp)]
            subset = pages.loc[(pages["firm_id"] == f) & (pages["relative_timepoint"] == tp)]
            issues = []
            if snap.empty:
                issues.append("missing_snapshot")
            else:
                if str(snap.iloc[0].get("snapshot_status")).lower() not in {"selected", "beyond_tolerance", "future_unavailable", "event_unavailable"}:
                    issues.append("odd_snapshot_status")
            if subset.empty and str(snap.iloc[0].get("snapshot_status")).lower() == "selected":
                issues.append("selected_without_pages")
            # branding eligibility consistency for usable branding pages
            if len(subset):
                legal_in_brand = subset.loc[
                    subset["branding_corpus_eligible"].map(as_bool)
                    & subset["page_category"].fillna("").isin(LEGAL_CATS)
                ]
                if len(legal_in_brand):
                    issues.append("legal_branding_in_sample_obs")
            sample_checks.append(
                {
                    "firm_id": f,
                    "relative_timepoint": tp,
                    "company": row.get("company"),
                    "issues": issues,
                    "correct_company": row.get("correct_company"),
                    "valid_archived_page": row.get("valid_archived_page"),
                    "content_extraction_usable": row.get("content_extraction_usable"),
                    "temporally_appropriate": row.get("temporally_appropriate"),
                }
            )
    sample_issue_n = sum(1 for s in sample_checks if s["issues"])
    s13_pass = len(sample) >= 20 and sample_issue_n == 0
    if not s13_pass and len(sample) == 0:
        blocking.append("section13_manual_sample_missing")
    elif sample_issue_n:
        blocking.append("section13_manual_sample_issues")
    section(
        results,
        "section13",
        "Random manual sample",
        s13_pass,
        n_sample=len(sample),
        n_with_issues=sample_issue_n,
        sample_issue_examples=[s for s in sample_checks if s["issues"]][:20],
        accuracy={
            "correct_company_true": int(sample["correct_company"].astype(str).str.lower().isin(["true", "1"]).sum()) if len(sample) else 0,
            "valid_archived_true": int(sample["valid_archived_page"].astype(str).str.lower().isin(["true", "1"]).sum()) if len(sample) else 0,
            "content_usable_true": int(sample["content_extraction_usable"].astype(str).str.lower().isin(["true", "1"]).sum()) if len(sample) else 0,
            "temporally_appropriate_true": int(sample["temporally_appropriate"].astype(str).str.lower().isin(["true", "1"]).sum()) if len(sample) else 0,
        },
        note="Evidence-based stratified sample checks; full Playwright re-open is optional and not required to fail unless sample issues found.",
    )

    # ---------- SECTION 14 ----------
    regression = {}
    if PILOT.exists():
        p_pages = pd.read_csv(PILOT / "pages.csv")
        # pilot legal in branding
        p_bp = pd.read_csv(PILOT / "branding_corpus_pages_all_languages.csv") if (PILOT / "branding_corpus_pages_all_languages.csv").exists() else pd.read_csv(PILOT / "branding_corpus_pages.csv")
        p_legal = int(p_bp["page_category"].fillna("").isin(LEGAL_CATS).sum())
        regression["pilot_legal_in_branding"] = p_legal
        regression["full_legal_category_in_branding"] = len(legal_cat_hits)
        regression["pilot_primary_n"] = len(pd.read_csv(PILOT / "branding_corpus_observations_primary.csv"))
        regression["checks"] = {
            "legal_exclusion_still_holds": len(legal_cat_hits) == 0,
            "governance_restricted": s4_pass,
            "eligibility_filtering": s5_pass,
            "duplicate_handling": s6_pass,
            "german_only_corpus": s7_pass,
            "reserved_slots": s8_pass,
            "token_policy": s9_pass,
            "quality_summary": s10_pass,
        }
        s14_pass = all(regression["checks"].values())
    else:
        regression["error"] = "pilot release not found"
        s14_pass = False
    if not s14_pass:
        blocking.append("section14_regression")
    section(results, "section14", "Regression against pilot_v1_4_1", s14_pass, **regression)

    # ---------- SECTION 15 ----------
    # Hard success criteria
    hard_fails = []
    if len(legal_cat_hits) or len(path_legal):
        hard_fails.append("legal_pages_in_branding")
    if not s4_pass:
        hard_fails.append("governance_marketing")
    if not s5_pass:
        hard_fails.append("ineligible_in_primary")
    if not s6_pass:
        hard_fails.append("within_timepoint_duplicates")
    if not s7_pass:
        hard_fails.append("german_corpus_foreign")
    if not s8_pass:
        hard_fails.append("reserved_legal_or_foreign")
    if not s9_pass:
        hard_fails.append("zero_analysis_tokens")
    if not s10_pass:
        hard_fails.append("quality_inconsistent")
    if not s1_pass:
        hard_fails.append("reproducibility_metadata")

    # For freeze: require exact commit match OR document as fail
    ready = len(hard_fails) == 0 and s2_pass and s12_pass and s13_pass and s14_pass
    recommendation = "READY TO FREEZE" if ready else "NOT READY TO FREEZE"
    section(
        results,
        "section15",
        "Final release decision",
        ready,
        recommendation=recommendation,
        hard_fail_reasons=hard_fails,
        blocking=sorted(set(blocking)),
        part_results={
            f"section{i}": ("PASS" if results[f"section{i}"]["pass"] else "FAIL")
            for i in range(1, 15)
        },
    )

    out_json = ROOT / "data/interim/full_sample_release_acceptance.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(results["section15"], indent=2, default=str))
    for i in range(1, 15):
        print(f"section{i}", "PASS" if results[f"section{i}"]["pass"] else "FAIL")
    print("wrote", out_json)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
