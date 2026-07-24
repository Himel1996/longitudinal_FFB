#!/usr/bin/env python3
"""Read-only release acceptance audit for pilot_v1_4_1."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.crawl.priority import classify_path_match, normalize_path_segments

REL = ROOT / "data/releases/pilot_v1_4_1/data"
PREV_CANDIDATES = [
    ROOT / "data/archive/pilot_v1_4_pre_v1_4_1/data",
    ROOT / "data/releases/pilot_v1_4/data",
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


def as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def load(base: Path, name: str) -> pd.DataFrame | None:
    path = base / name
    if not path.exists():
        return None
    return pd.read_csv(path)


def firm_keys(df: pd.DataFrame) -> set[tuple[str, str]]:
    return {
        (str(int(float(r["firm_id"]))), r["relative_timepoint"])
        for _, r in df.iterrows()
    }


def url_keys(df: pd.DataFrame) -> set[tuple[str, str, str]]:
    return {
        (
            str(int(float(r["firm_id"]))),
            r["relative_timepoint"],
            str(r["original_archived_url"]),
        )
        for _, r in df.iterrows()
        if pd.notna(r.get("original_archived_url"))
    }


def main() -> int:
    prev = next((p for p in PREV_CANDIDATES if p.exists()), None)
    pages = load(REL, "pages.csv")
    bp = load(REL, "branding_corpus_pages.csv")
    bp_all = load(REL, "branding_corpus_pages_all_languages.csv")
    bp_de = load(REL, "branding_corpus_pages_de.csv")
    bp_en = load(REL, "branding_corpus_pages_en.csv")
    bp_other = load(REL, "branding_corpus_pages_other.csv")
    gov = load(REL, "governance_metadata_pages.csv")
    primary = load(REL, "branding_corpus_observations_primary.csv")
    sens = load(REL, "branding_corpus_observations_sensitivity.csv")
    obs = load(REL, "observation_text_summary.csv")
    dup_sum = load(REL, "duplicate_summary.csv")
    quality = load(REL, "quality_summary.csv")
    crawl = load(REL, "crawl_priority_summary.csv")
    results: dict = {"files_checked": sorted(p.name for p in REL.glob("*.csv")) + ["run_manifest.json"]}

    # ---------- PART 1 ----------
    legal_terms_url = (
        "impressum",
        "agb",
        "privacy",
        "datenschutz",
        "cookie",
        "legal-notice",
        "legal_notice",
        "disclaimer",
        "rechtliches",
        "datenschutzerklärung",
        "datenschutzerklaerung",
    )
    legal_terms_title = (
        "impressum",
        "agb",
        "privacy",
        "datenschutz",
        "disclaimer",
        "cookie",
        "legal notice",
        "rechtliches",
    )
    legal_cats = {
        "impressum",
        "legal_notice",
        "privacy_policy",
        "terms_conditions",
        "cookie_notice",
        "legal_other",
    }
    offenders = []
    for _, r in bp.iterrows():
        fields = {
            "url": str(r.get("original_archived_url") or ""),
            "normalized_url": str(r.get("normalized_url") or r.get("canonical_page_url") or ""),
            "title": str(r.get("document_title") or ""),
            "h1": str(r.get("h1_text") or ""),
            "category": str(r.get("page_category") or ""),
            "path": str(r.get("path") or ""),
        }
        evidence = []
        if fields["category"] in legal_cats:
            evidence.append(f"category={fields['category']}")
        for t in legal_terms_url:
            for key in ("url", "normalized_url", "path"):
                if t in fields[key].lower():
                    evidence.append(f"{key} contains '{t}'")
        for t in legal_terms_title:
            for key in ("title", "h1"):
                if t in fields[key].lower():
                    evidence.append(f"{key} contains '{t}'")
        if evidence:
            offenders.append({**fields, "evidence": sorted(set(evidence))})
    results["part1"] = {
        "name": "Legal page exclusion from branding corpus",
        "pass": len(offenders) == 0,
        "n_branding_pages": len(bp),
        "n_offenders": len(offenders),
        "offenders": offenders,
    }

    # ---------- PART 2 ----------
    # Christian explicitly allows impressum, legal notice, ownership,
    # legal representatives, and corporate affiliation in the governance layer.
    allowed_gov = {
        "impressum",
        "legal_notice",
        "corporate_affiliation",
        "ownership",
        "legal_representatives",
    }
    brandingish = {
        "homepage",
        "company_about",
        "history_heritage",
        "family_values",
        "management_leadership",
        "sustainability_responsibility",
        "products_services",
        "news_press",
        "careers_employer",
        "unknown",
    }
    gov_violations = []
    for _, r in gov.iterrows():
        cat = str(r.get("page_category") or "")
        url = str(r.get("original_archived_url") or "").lower()
        title = str(r.get("document_title") or "")
        if cat in brandingish:
            gov_violations.append(
                {
                    "url": r.get("original_archived_url"),
                    "category": cat,
                    "title": title,
                    "reason": "branding/product/history/company category in governance layer",
                    "gov_reason": r.get("governance_inclusion_reason"),
                }
            )
        elif cat not in allowed_gov:
            if not any(x in url for x in ("impressum", "imprint", "legal-notice", "legal_notice")):
                gov_violations.append(
                    {
                        "url": r.get("original_archived_url"),
                        "category": cat,
                        "title": title,
                        "reason": f"category '{cat}' outside allowed governance scope",
                        "gov_reason": r.get("governance_inclusion_reason"),
                    }
                )
        if any(m in url for m in ("produkt", "/products", "/product/")) and not any(
            m in url for m in ("impressum", "imprint", "datenschutz", "privacy")
        ):
            gov_violations.append(
                {
                    "url": r.get("original_archived_url"),
                    "category": cat,
                    "title": title,
                    "reason": "product URL in governance layer",
                    "gov_reason": r.get("governance_inclusion_reason"),
                }
            )
    gov_cats = gov["page_category"].fillna("NA").value_counts().to_dict()
    results["part2"] = {
        "name": "Governance layer scope",
        "pass": len(gov_violations) == 0,
        "n_gov_pages": len(gov),
        "category_distribution": gov_cats,
        "n_violations": len(gov_violations),
        "violations": gov_violations,
    }

    # ---------- PART 3 ----------
    pri_bad = primary.loc[~primary["text_analysis_eligible"].map(as_bool)]
    sens_bad = sens.loc[~sens["text_analysis_eligible"].map(as_bool)]
    expected_primary = set()
    expected_sens = set()
    for _, r in obs.iterrows():
        key = (str(int(float(r["firm_id"]))), r["relative_timepoint"])
        if as_bool(r.get("german_text_analysis_eligible")) and r.get("observation_recommendation") == "include":
            expected_primary.add(key)
        if as_bool(r.get("text_analysis_eligible")) and r.get("observation_recommendation") in {
            "include",
            "sensitivity_analysis",
        }:
            expected_sens.add(key)
    pri_keys = firm_keys(primary)
    sens_keys = firm_keys(sens)
    results["part3"] = {
        "name": "Observation eligibility",
        "pass": (
            len(pri_bad) == 0
            and len(sens_bad) == 0
            and pri_keys == expected_primary
            and sens_keys == expected_sens
        ),
        "primary_n": len(primary),
        "sensitivity_n": len(sens),
        "primary_all_text_analysis_eligible_true": len(pri_bad) == 0,
        "sensitivity_all_text_analysis_eligible_true": len(sens_bad) == 0,
        "primary_key_mismatch": [list(x) for x in sorted(pri_keys ^ expected_primary)],
        "sensitivity_key_mismatch": [list(x) for x in sorted(sens_keys ^ expected_sens)],
        "primary_ineligible_examples": pri_bad[["firm_id", "relative_timepoint"]].to_dict("records")
        if len(pri_bad)
        else [],
        "sensitivity_ineligible_examples": sens_bad[["firm_id", "relative_timepoint"]].to_dict("records")
        if len(sens_bad)
        else [],
    }

    # ---------- PART 4 ----------
    within_dups = []
    for (fid, tp), g in bp.groupby(
        [bp["firm_id"].map(lambda x: str(int(float(x)))), "relative_timepoint"]
    ):
        if "normalized_content_hash" in g.columns:
            h = g["normalized_content_hash"].dropna()
            if h.duplicated().any():
                within_dups.append(
                    {
                        "firm_id": fid,
                        "relative_timepoint": tp,
                        "duplicate_hashes": h[h.duplicated()].unique().tolist(),
                    }
                )
    branding_dup_flag = int(bp["duplicate_content_flag"].map(as_bool).sum()) if "duplicate_content_flag" in bp.columns else 0
    flagged = pages.loc[pages["duplicate_content_flag"].map(as_bool)]
    flag_issues = []
    for _, r in flagged.iterrows():
        if pd.isna(r.get("duplicate_group_id")) or not str(r.get("duplicate_group_id") or "").strip():
            flag_issues.append({"url": r.get("original_archived_url"), "issue": "missing_duplicate_group_id"})
        if pd.isna(r.get("duplicate_of_page_id")) or not str(r.get("duplicate_of_page_id") or "").strip():
            flag_issues.append({"url": r.get("original_archived_url"), "issue": "missing_duplicate_of_page_id"})
    non_dup = pages.loc[
        pages["normalized_content_hash"].notna() & ~pages["duplicate_content_flag"].map(as_bool)
    ]
    multi = non_dup.groupby(
        [non_dup["firm_id"].map(lambda x: str(int(float(x)))), "normalized_content_hash"]
    )["relative_timepoint"].nunique()
    cross_preserved = int((multi > 1).sum())
    n_groups = int(pages["duplicate_group_id"].dropna().nunique()) if "duplicate_group_id" in pages.columns else 0
    results["part4"] = {
        "name": "Duplicate handling",
        "pass": len(within_dups) == 0 and branding_dup_flag == 0 and len(flag_issues) == 0 and cross_preserved > 0,
        "within_timepoint_duplicate_hash_groups_in_branding": within_dups,
        "branding_pages_with_duplicate_content_flag": branding_dup_flag,
        "flag_metadata_issues": flag_issues[:30],
        "n_duplicate_groups": n_groups,
        "n_removed": int(len(flagged)),
        "n_preserved_across_timepoints": cross_preserved,
        "duplicate_summary_rows": len(dup_sum) if dup_sum is not None else 0,
    }

    # ---------- PART 5 ----------
    lang_col = "detected_language" if "detected_language" in bp_de.columns else "text_language"
    de_langs = bp_de[lang_col].fillna("").astype(str).str.lower()
    en_in_de = bp_de.loc[de_langs.eq("en"), "original_archived_url"].astype(str).tolist()
    unk_in_de = bp_de.loc[de_langs.isin(["unknown", "nan", ""]), "original_archived_url"].astype(str).tolist()
    non_de = bp_de.loc[~de_langs.eq("de"), "original_archived_url"].astype(str).tolist()
    urls_all = set(bp_all["original_archived_url"].astype(str))
    urls_de = set(bp_de["original_archived_url"].astype(str))
    urls_en = set(bp_en["original_archived_url"].astype(str))
    urls_other = set(bp_other["original_archived_url"].astype(str))
    union = urls_de | urls_en | urls_other
    disjoint = (
        len(urls_de & urls_en) == 0
        and len(urls_de & urls_other) == 0
        and len(urls_en & urls_other) == 0
    )
    sum_exact = urls_all == union and disjoint
    results["part5"] = {
        "name": "Language corpora",
        "pass": len(non_de) == 0 and len(en_in_de) == 0 and len(unk_in_de) == 0 and sum_exact,
        "n_all": len(bp_all),
        "n_de": len(bp_de),
        "n_en": len(bp_en),
        "n_other": len(bp_other),
        "de_language_value_counts": de_langs.value_counts().to_dict(),
        "non_german_in_de_corpus": non_de,
        "english_in_de_corpus": en_in_de,
        "unknown_in_de_corpus": unk_in_de,
        "partition_disjoint": disjoint,
        "all_equals_union_of_parts": urls_all == union,
        "all_minus_parts": sorted(urls_all - union)[:30],
        "parts_minus_all": sorted(union - urls_all)[:30],
    }

    # ---------- PART 6 ----------
    legal_markers = (
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
    legal_reserved = []
    foreign_reserved = []
    substring_false_about = []
    weak_match_reserved = []
    for _, p in pages.iterrows():
        url = str(p.get("original_archived_url") or "")
        path = str(p.get("path") or urlparse(url).path or "").lower()
        cat = str(p.get("reserved_slot_category") or "")
        reserved_sel = as_bool(p.get("selected_under_reserved_slot"))

        if any(m in path for m in legal_markers):
            if reserved_sel and cat in RESERVE_CATS:
                legal_reserved.append(url)
            if cat in (RESERVE_CATS - {"homepage"}):
                legal_reserved.append(url)
        if str(p.get("path_language_priority") or "") == "foreign_language_deprioritized":
            if reserved_sel:
                foreign_reserved.append(url)

        segs = normalize_path_segments(path)
        # Careers/news/product/press segments must not consume company_about reserved slots
        if reserved_sel and cat == "company_about" and (set(segs) & LOW_VALUE_SEGMENTS):
            substring_false_about.append(url)

        # Re-score with segment-aware matcher: reserved slots require high-confidence structural match
        if reserved_sel and cat in RESERVE_CATS:
            match = classify_path_match(url, is_homepage=(cat == "homepage" and path in {"", "/"}))
            # Fail if current code would not assign this reserved category with high confidence
            if cat != "homepage":
                if (
                    match.reserved_slot_category != cat
                    or not match.eligible_for_reserved_slot
                    or match.priority_match_confidence != "high"
                    or match.priority_match_type
                    not in {"exact_path_segment", "homepage_flag", "root_path"}
                ):
                    weak_match_reserved.append(
                        {
                            "url": url,
                            "assigned": cat,
                            "rescored": match.reserved_slot_category,
                            "match_type": match.priority_match_type,
                            "confidence": match.priority_match_confidence,
                            "segments": segs,
                        }
                    )
            # Explicit: "unternehmen" only as substring inside another slug is not a segment hit
            if "unternehmen" in path and "unternehmen" not in segs and cat == "company_about":
                substring_false_about.append(url)

    low_took_reserved = []
    for _, p in pages.iterrows():
        path = str(p.get("path") or "").lower()
        segs = set(normalize_path_segments(path))
        if (segs & LOW_VALUE_SEGMENTS) and as_bool(p.get("selected_under_reserved_slot")):
            if str(p.get("reserved_slot_category") or "") in RESERVE_CATS:
                low_took_reserved.append(str(p.get("original_archived_url")))

    order_ok_obs = 0
    order_issue_obs = []
    for (fid, tp), g in pages.groupby(
        [pages["firm_id"].map(lambda x: str(int(float(x)))), "relative_timepoint"]
    ):
        if "crawl_budget_position" not in g.columns:
            continue
        g = g.dropna(subset=["crawl_budget_position"])
        if g.empty:
            continue

        low_mask = g["path"].fillna("").astype(str).str.lower().str.contains(
            r"news|presse|press|aktuelles|produkt|product|karriere|career|jobs|stellen|/en/",
            regex=True,
            na=False,
        )
        high_reserved = g.loc[
            g["selected_under_reserved_slot"].map(as_bool)
            & g["reserved_slot_category"].fillna("").isin(RESERVE_CATS)
        ]
        low_pages = g.loc[low_mask]
        if len(high_reserved) and len(low_pages):
            hmin = float(high_reserved["crawl_budget_position"].min())
            lmin = float(low_pages["crawl_budget_position"].min())
            if hmin <= lmin:
                order_ok_obs += 1
            else:
                order_issue_obs.append(
                    {
                        "firm_id": fid,
                        "relative_timepoint": tp,
                        "high_min_pos": hmin,
                        "low_min_pos": lmin,
                    }
                )
        elif len(high_reserved):
            order_ok_obs += 1

    results["part6"] = {
        "name": "Reserved-slot priority",
        "pass": (
            len(set(legal_reserved)) == 0
            and len(set(foreign_reserved)) == 0
            and len(set(low_took_reserved)) == 0
            and len(set(substring_false_about)) == 0
            and len(weak_match_reserved) == 0
            and len(order_issue_obs) == 0
        ),
        "legal_pages_consuming_reserved_slots": sorted(set(legal_reserved)),
        "foreign_pages_consuming_reserved_slots": sorted(set(foreign_reserved)),
        "news_product_career_consuming_reserved_slots": sorted(set(low_took_reserved)),
        "unternehmen_substring_false_company_about": sorted(set(substring_false_about)),
        "reserved_slots_without_high_confidence_segment_match": weak_match_reserved[:40],
        "observations_where_reserved_branding_before_low_pages": order_ok_obs,
        "observations_where_low_pages_before_reserved_branding": order_issue_obs,
        "crawl_summary_totals": {
            "high_priority_fetched": int(crawl["n_high_priority_pages_fetched"].sum()),
            "secondary_fetched": int(crawl["n_secondary_pages_fetched"].sum()),
            "broad_fetched": int(crawl["n_broad_pages_fetched"].sum()),
            "foreign_deprioritized_discovered": int(crawl["n_foreign_pages_deprioritized"].sum()),
        },
    }

    # ---------- PART 7 ----------
    def analysis_tokens(row) -> float | None:
        if "analysis_token_count" in row.index and pd.notna(row.get("analysis_token_count")):
            return float(row.get("analysis_token_count"))
        tc = row.get("token_count")
        if pd.isna(tc):
            return None
        return float(tc)

    zero_tok = []
    alias_mismatch = []
    for _, r in pages.iterrows():
        text = str(r.get("main_text") or r.get("extracted_text") or "").strip()
        at = analysis_tokens(r)
        usable = as_bool(r.get("usable_for_analysis"))
        chars = r.get("character_count")
        char_n = int(float(chars)) if pd.notna(chars) else len(text)
        if usable and char_n >= 50 and (at is None or at <= 0):
            zero_tok.append(
                {
                    "url": r.get("original_archived_url"),
                    "firm_id": r.get("firm_id"),
                    "relative_timepoint": r.get("relative_timepoint"),
                    "chars": char_n,
                    "analysis_token_count": at,
                    "token_count": r.get("token_count"),
                    "tokenization_method": r.get("tokenization_method"),
                }
            )
        if (
            "analysis_token_count" in pages.columns
            and pd.notna(r.get("analysis_token_count"))
            and pd.notna(r.get("token_count"))
            and float(r["analysis_token_count"]) != float(r["token_count"])
        ):
            alias_mismatch.append(str(r.get("original_archived_url")))

    mismatches = []
    tok_col = "analysis_token_count" if "analysis_token_count" in pages.columns else "token_count"
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
            mismatches.append(
                {"firm_id": fid, "relative_timepoint": tp, "obs": obs_tok, "pages": page_sum}
            )

    chinese_page = pages.loc[
        pages["original_archived_url"]
        .astype(str)
        .str.contains("peter-lacke.de/chn/peter-lacke/company/company.html", na=False)
    ]
    chinese_status = None
    if len(chinese_page):
        row = chinese_page.iloc[0]
        chinese_status = {
            "url": row.get("original_archived_url"),
            "character_count": row.get("character_count"),
            "token_count": row.get("token_count"),
            "analysis_token_count": row.get("analysis_token_count"),
            "lexical_token_count": row.get("lexical_token_count"),
            "tokenization_method": row.get("tokenization_method"),
            "usable_for_analysis": as_bool(row.get("usable_for_analysis")),
            "detected_language": row.get("detected_language") or row.get("text_language"),
            "german_corpus_eligible": as_bool(row.get("german_corpus_eligible"))
            if "german_corpus_eligible" in row.index
            else None,
        }

    results["part7"] = {
        "name": "Token consistency",
        "pass": len(zero_tok) == 0 and len(mismatches) == 0 and len(alias_mismatch) == 0,
        "policy": "token_count is alias of analysis_token_count (choice A)",
        "n_usable_pages_with_substantive_text_but_zero_analysis_tokens": len(zero_tok),
        "zero_token_examples": zero_tok[:30],
        "token_count_analysis_alias_mismatches": alias_mismatch[:20],
        "observation_vs_page_token_mismatches": mismatches,
        "chinese_peter_lacke_page": chinese_status,
    }

    # ---------- PART 8 ----------
    q_issues = []
    for _, q in quality.iterrows():
        attempted = int(q.get("pages_attempted") or 0)
        success = int(q.get("pages_fetch_success") or 0)
        failed = int(q.get("pages_fetch_failed") or 0)
        usable = int(q.get("pages_extraction_usable") or 0)
        branding = int(q.get("pages_branding_eligible") or 0)
        key = f"{q.get('firm_id')}|{q.get('relative_timepoint')}"
        if attempted != success + failed:
            q_issues.append(f"{key}: attempted != success+failed ({attempted} != {success}+{failed})")
        if success < usable:
            q_issues.append(f"{key}: fetch_success < extraction_usable ({success} < {usable})")
        if usable < branding:
            q_issues.append(f"{key}: extraction_usable < branding_eligible ({usable} < {branding})")
        if min(attempted, success, failed, usable, branding) < 0:
            q_issues.append(f"{key}: negative counts")
    results["part8"] = {
        "name": "Quality summary internal consistency",
        "pass": len(q_issues) == 0,
        "n_rows": len(quality),
        "issues": q_issues,
    }

    # ---------- PART 9 ----------
    diffs: dict = {}
    if prev is not None:
        prev_bp = load(prev, "branding_corpus_pages_all_languages.csv")
        if prev_bp is None:
            prev_bp = load(prev, "branding_corpus_pages.csv")
        prev_pages = load(prev, "pages.csv")
        prev_pri = load(prev, "branding_corpus_observations_primary.csv")
        prev_sens = load(prev, "branding_corpus_observations_sensitivity.csv")
        prev_obs = load(prev, "observation_text_summary.csv")
        prev_dup = load(prev, "duplicate_summary.csv")
        prev_de = load(prev, "branding_corpus_pages_de.csv")
        prev_manifest = json.loads((prev / "run_manifest.json").read_text())
        cur_manifest = json.loads((REL / "run_manifest.json").read_text())

        if prev_bp is not None:
            a, b = url_keys(prev_bp), url_keys(bp_all)
            diffs["branding_count_prev"] = len(prev_bp)
            diffs["branding_count_cur"] = len(bp_all)
            diffs["branding_urls_added"] = len(b - a)
            diffs["branding_urls_removed"] = len(a - b)
            diffs["branding_urls_added_sample"] = [list(x) for x in sorted(b - a)[:15]]
            diffs["branding_urls_removed_sample"] = [list(x) for x in sorted(a - b)[:15]]
        if prev_pages is not None:
            a, b = url_keys(prev_pages), url_keys(pages)
            diffs["pages_prev"] = len(prev_pages)
            diffs["pages_cur"] = len(pages)
            diffs["page_urls_added"] = len(b - a)
            diffs["page_urls_removed"] = len(a - b)
        if prev_pri is not None:
            diffs["primary_prev"] = len(prev_pri)
            diffs["primary_cur"] = len(primary)
            diffs["primary_keys_identical"] = firm_keys(prev_pri) == firm_keys(primary)
        if prev_sens is not None:
            diffs["sensitivity_prev"] = len(prev_sens)
            diffs["sensitivity_cur"] = len(sens)
            diffs["sensitivity_keys_identical"] = firm_keys(prev_sens) == firm_keys(sens)
        if prev_obs is not None:
            diffs["branding_token_sum_prev"] = int(prev_obs["branding_token_count"].fillna(0).sum())
            diffs["branding_token_sum_cur"] = int(obs["branding_token_count"].fillna(0).sum())
            if "tokens_de" in prev_obs.columns:
                diffs["tokens_de_prev"] = int(prev_obs["tokens_de"].fillna(0).sum())
                diffs["tokens_de_cur"] = int(obs["tokens_de"].fillna(0).sum())
        if prev_dup is not None:
            diffs["dup_rows_prev"] = len(prev_dup)
            diffs["dup_rows_cur"] = len(dup_sum)
        if prev_de is not None:
            diffs["branding_de_prev"] = len(prev_de)
            diffs["branding_de_cur"] = len(bp_de)

        meaningful = any(
            [
                diffs.get("branding_urls_added", 0) > 0,
                diffs.get("branding_urls_removed", 0) > 0,
                diffs.get("page_urls_added", 0) > 0,
                diffs.get("page_urls_removed", 0) > 0,
                diffs.get("primary_prev") != diffs.get("primary_cur"),
                diffs.get("sensitivity_prev") != diffs.get("sensitivity_cur"),
                diffs.get("branding_token_sum_prev") != diffs.get("branding_token_sum_cur"),
                diffs.get("dup_rows_prev") != diffs.get("dup_rows_cur"),
            ]
        )
        results["part9"] = {
            "name": "Comparison vs pilot_v1_4",
            "prev_path": str(prev),
            "run_id_prev": prev_manifest.get("run_id"),
            "run_id_cur": cur_manifest.get("run_id"),
            "git_commit_prev": prev_manifest.get("git_commit"),
            "git_commit_cur": cur_manifest.get("git_commit"),
            "meaningful_content_differences": meaningful,
            "diffs": diffs,
            "interpretation": (
                "Only run metadata differs; content metrics match."
                if not meaningful
                else "Content differs as expected for reserved-slot and tokenization fixes."
            ),
        }
    else:
        results["part9"] = {"name": "Comparison vs pilot_v1_4", "error": "previous release not found"}

    parts = [f"part{i}" for i in range(1, 9)]
    all_pass = all(results[p]["pass"] for p in parts)
    results["part10"] = {
        "name": "Release acceptance",
        "pass": all_pass,
        "recommendation": "READY TO SCALE" if all_pass else "NOT READY TO SCALE",
        "part_results": {p: ("PASS" if results[p]["pass"] else "FAIL") for p in parts},
    }

    out_json = ROOT / "data/interim/release_acceptance_audit.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(results["part10"], indent=2))
    for p in parts:
        print(p, "PASS" if results[p]["pass"] else "FAIL")
    if "part9" in results:
        print("part9 meaningful_diff", results["part9"].get("meaningful_content_differences"))
    print("wrote", out_json)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
