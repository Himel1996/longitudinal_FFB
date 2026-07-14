#!/usr/bin/env python3
"""Consolidate re-extracted homepages and rebuild validation CSV."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.archive.wayback_url import parse_wayback_url
from ffb_webminer.config import PipelineConfig
from ffb_webminer.crawl.fetcher import PageFetcher
from ffb_webminer.extract.domain import parse_domain
from ffb_webminer.extract.html_metadata import extract_metadata
from ffb_webminer.extract.html_preprocess import expand_archived_html
from ffb_webminer.extract.text import count_family_terms, extract_text
from ffb_webminer.pipeline.schemas import PAGE_COLUMNS
from ffb_webminer.quality.checks import check_page
from ffb_webminer.quality.page_validation import validate_page_for_analysis

OBS = [
    ("1", "pre_pre_event"), ("1", "pre_event"), ("1", "event"), ("1", "post_event"),
    ("2", "pre_pre_event"), ("2", "pre_event"), ("2", "event"),
    ("3", "pre_pre_event"), ("3", "pre_event"), ("3", "event"), ("3", "post_event"),
    ("4", "pre_pre_event"), ("4", "pre_event"), ("4", "post_event"), ("4", "post_post_event"),
    ("5", "pre_pre_event"), ("5", "event"), ("5", "post_event"), ("5", "post_post_event"),
]

ORIGINAL_VALIDATION = {
    ("1", "pre_pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct BLUE MOON homepage Nov 2020; title and H1 match rendered page; rich Full-Service agency branding in extraction.",
        validation_screenshot_path="validation_screenshots/01_1_blue_moon_communicat_pre_pre_event.png",
    ),
    ("1", "pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct homepage Jul 2022; H1 matches; extensive pre-redesign agency/service content preserved in main_text.",
        validation_screenshot_path="validation_screenshots/02_1_blue_moon_communicat_pre_event.png",
    ),
    ("1", "event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="False",
        duplicate_capture="False",
        reviewer_notes="Correct company but capture is Mar 2025 (~8 months post-2024 event); post-redesign familiengeführt branding—poor event-window fit.",
        validation_screenshot_path="validation_screenshots/03_1_blue_moon_communicat_event.png",
    ),
    ("1", "post_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct 2026 homepage; familiengeführt/Vier Teams branding visible.",
        validation_screenshot_path="validation_screenshots/04_1_blue_moon_communicat_post_event.png",
    ),
    ("2", "pre_pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct PETER-LACKE homepage Jul 2011 with lacquer-industry branding.",
        validation_screenshot_path="validation_screenshots/05_2_peter_lacke_holding_pre_pre_event.png",
    ),
    ("2", "pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct archive; visible_dom extracts colInhalt Lack-Kompetenz headings.",
        validation_screenshot_path="validation_screenshots/06_2_peter_lacke_holding_pre_event.png",
    ),
    ("2", "event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct May 2015 homepage; mittelständische Unternehmensgruppe text in visible_dom extraction.",
        validation_screenshot_path="validation_screenshots/07_2_peter_lacke_holding_event.png",
    ),
    ("3", "pre_pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct Leichtle installer homepage; service content extracted, family-branding sparse.",
        validation_screenshot_path="validation_screenshots/08_3_anlagentechnik_leich_pre_pre_event.png",
    ),
    ("3", "pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct Jun 2021 homepage; service-oriented extraction.",
        validation_screenshot_path="validation_screenshots/09_3_anlagentechnik_leich_pre_event.png",
    ),
    ("3", "event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct May 2023 homepage; low family-branding density.",
        validation_screenshot_path="validation_screenshots/10_3_anlagentechnik_leich_event.png",
    ),
    ("3", "post_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct 2025 homepage; service-oriented extraction usable.",
        validation_screenshot_path="validation_screenshots/11_3_anlagentechnik_leich_post_event.png",
    ),
    ("4", "pre_pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Frames homepage; frame expansion required for welcome content.",
        validation_screenshot_path="validation_screenshots/12_4_myrenne_gmbh_pre_pre_event.png",
    ),
    ("4", "pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct homepage Apr 2010; mittelständisches Unternehmen welcome text extracted.",
        validation_screenshot_path="validation_screenshots/13_4_myrenne_gmbh_pre_event.png",
    ),
    ("4", "post_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct May 2014 homepage with Gesamtlösungen Maschinenbau text.",
        validation_screenshot_path="validation_screenshots/14_4_myrenne_gmbh_post_event.png",
    ),
    ("4", "post_post_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct Aug 2016 redesign homepage; mittelständisch branding in extraction.",
        validation_screenshot_path="validation_screenshots/15_4_myrenne_gmbh_post_post_event.png",
    ),
    ("5", "pre_pre_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="False",
        duplicate_capture="False",
        reviewer_notes="MSF-Vathauer via JS redirect+frames; capture ~11 months before 2002 target.",
        validation_screenshot_path="validation_screenshots/16_5_msf_vathauer_antrieb_pre_pre_event.png",
    ),
    ("5", "event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="False",
        duplicate_capture="True",
        reviewer_notes="Same timestamp as excluded pre_event; JS redirect+frames site.",
        validation_screenshot_path="validation_screenshots/17_5_msf_vathauer_antrieb_event.png",
    ),
    ("5", "post_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Archived root serves Über-uns; MSF-Vathauer corporate welcome text extracted.",
        validation_screenshot_path="validation_screenshots/18_5_msf_vathauer_antrieb_post_event.png",
    ),
    ("5", "post_post_event"): dict(
        correct_company="True", valid_archived_page="True", temporally_appropriate="True",
        duplicate_capture="False",
        reviewer_notes="Correct MSF-Vathauer Jun 2010 Über-uns content extracted.",
        validation_screenshot_path="validation_screenshots/19_5_msf_vathauer_antrieb_post_post_event.png",
    ),
}


def main() -> int:
    config = PipelineConfig.from_yaml(ROOT / "config/pilot.yaml")
    out = ROOT / config.run.output_dir
    pages_df = pd.read_csv(out / "pages.csv")
    snapshots = pd.read_csv(out / "snapshots.csv")
    firms = {str(r["firm_id"]): r for r in csv.DictReader(open(out / "firms.csv"))}

    fetcher = PageFetcher(
        user_agent=config.crawl.user_agent,
        timeout_seconds=60,
        throttle_seconds=2.5,
        raw_html_dir=ROOT / config.extract.raw_html_dir,
    )

    comparisons = []
    new_home_rows = []

    for fid, tp in OBS:
        snap = snapshots[(snapshots.firm_id.astype(str) == fid) & (snapshots.relative_timepoint == tp)].iloc[0]
        old_rows = pages_df[
            (pages_df.firm_id.astype(str) == fid)
            & (pages_df.relative_timepoint == tp)
            & (pages_df.path.fillna("/").isin(["/", ""]))
            & (pages_df.page_priority_reason.fillna("") == "homepage")
        ]
        old = old_rows.sort_values("word_count", ascending=False, na_position="last").iloc[0] if not old_rows.empty else {}
        old_words = int(float(old.get("word_count") or 0)) if len(old_rows) else 0

        replay = snap["wayback_replay_url"]
        original = snap.get("canonical_original_url") or snap.get("requested_url")
        parsed = parse_wayback_url(replay)
        ts = parsed[0] if parsed else None

        fetch = None
        for attempt in range(5):
            time.sleep(attempt * 2)
            fetch = fetcher.fetch(original, archive_timestamp=ts, use_cache=True)
            if fetch.content:
                break

        row = {c: None for c in PAGE_COLUMNS}
        row.update({
            "run_id": snap["run_id"], "firm_id": int(fid), "rank": snap["rank"],
            "company": snap["company"], "event_type": snap["event_type"],
            "event_year": snap["event_year"], "event_label": snap["event_label"],
            "relative_timepoint": tp, "target_year": snap["target_year"],
            "target_date": snap["target_date"],
            "observation_is_future": snap["observation_is_future"],
            "snapshot_status": snap["snapshot_status"],
            "snapshot_observation_key": f"{fid}|{tp}",
            "analysis_eligible": bool(snap.get("analysis_eligible")),
            "capture_source": "wayback",
            "archive_timestamp": snap["archive_timestamp"],
            "page_archive_timestamp": snap["archive_timestamp"],
            "selected_capture_date": snap["selected_capture_date"],
            "temporal_distance_days": snap["temporal_distance_days"],
            "temporal_fit_quality": snap.get("temporal_fit_quality"),
            "wayback_replay_url": replay,
            "original_archived_url": original,
            "page_priority_reason": "homepage",
            "path": "/",
            "crawl_depth": 0,
        })

        if fetch and fetch.content:
            prepared = expand_archived_html(fetch.content, replay, fetcher=fetcher)
            meta = extract_metadata(prepared.html)
            text_ex = extract_text(prepared.html, replay_url=replay)
            domain = parse_domain(original)
            row.update({
                "requested_url": fetch.requested_url,
                "final_url": fetch.final_url,
                "http_status": fetch.http_status,
                "fetch_error": None,
                "content_hash": fetch.content_hash,
                "raw_html_path": fetch.raw_html_path,
                "scheme": domain.scheme, "hostname": domain.hostname,
                "registrable_domain": domain.registrable_domain,
                "normalized_url": domain.normalized_url,
            })
            if meta:
                row.update({
                    "document_title": meta.document_title,
                    "meta_description": meta.meta_description,
                    "html_lang": meta.html_lang,
                    "h1_text": meta.h1_text,
                    "h2_text": meta.h2_text,
                    "headings_json": meta.headings_json,
                })
            if text_ex:
                row.update({
                    "main_text": text_ex.main_text,
                    "visible_text": text_ex.visible_text,
                    "extracted_text": text_ex.extracted_text,
                    "extraction_method": text_ex.extraction_method,
                    "text_language": text_ex.text_language,
                    "character_count": text_ex.character_count,
                    "word_count": text_ex.word_count,
                    "token_count": text_ex.token_count,
                    "extraction_quality_score": text_ex.extraction_quality_score,
                    "boilerplate_ratio": text_ex.boilerplate_ratio,
                    "archive_toolbar_removed_flag": text_ex.archive_toolbar_removed_flag,
                })
        else:
            row["fetch_error"] = fetch.fetch_error if fetch else "no_fetch"

        row = check_page(row, firms[fid]["primary_domain"], config.quality)
        row = validate_page_for_analysis(row, firms[fid]["primary_domain"], config.quality)
        new_home_rows.append(row)

        new_words = int(float(row.get("word_count") or 0))
        comparisons.append({
            "firm_id": fid, "timepoint": tp,
            "old_words": old_words, "new_words": new_words,
            "old_method": old.get("extraction_method") if len(old_rows) else None,
            "new_method": row.get("extraction_method"),
            "old_usable": old.get("usable_for_analysis") if len(old_rows) else None,
            "new_usable": row.get("usable_for_analysis"),
            "new_family_terms": count_family_terms(row.get("main_text")),
            "new_boilerplate": row.get("boilerplate_ratio"),
            "fetch_error": row.get("fetch_error"),
        })
        print(f"{fid}|{tp}: {old_words}->{new_words} usable={row.get('usable_for_analysis')} method={row.get('extraction_method')}")

    # Replace homepage rows in pages_df
    non_home = pages_df[
        ~(
            pages_df.apply(
                lambda r: (str(r.get("firm_id")), r.get("relative_timepoint")) in OBS
                and str(r.get("path", "/")) in ("/", "")
                and str(r.get("page_priority_reason", "")) == "homepage",
                axis=1,
            )
        )
    ]
    pages_df = pd.concat([non_home, pd.DataFrame(new_home_rows)], ignore_index=True)
    pages_df.to_csv(out / "pages.csv", index=False)

    # Rebuild validation CSV
    val_rows = []
    for fid, tp in OBS:
        snap = snapshots[(snapshots.firm_id.astype(str) == fid) & (snapshots.relative_timepoint == tp)].iloc[0]
        page = next(r for r in new_home_rows if str(r["firm_id"]) == fid and r["relative_timepoint"] == tp)
        words = int(float(page.get("word_count") or 0))
        meta = ORIGINAL_VALIDATION[(fid, tp)]
        content_usable = "True" if page.get("usable_for_analysis") and words >= 30 else "False"
        notes = meta["reviewer_notes"]
        if words >= 30 and page.get("extraction_method"):
            notes = f"Re-extraction: {words} words via {page.get('extraction_method')}. {notes}"[:500]
        val_rows.append({
            "run_id": snap["run_id"], "firm_id": fid, "company": snap["company"],
            "relative_timepoint": tp, "target_date": snap["target_date"],
            "selected_capture_date": snap["selected_capture_date"],
            "temporal_fit_quality": snap["temporal_fit_quality"],
            "observation_scope": snap["observation_scope"],
            "observation_recommendation": snap["observation_recommendation"],
            "original_archived_url": snap.get("requested_url") or snap.get("canonical_original_url"),
            "wayback_replay_url": snap["wayback_replay_url"],
            "duplicate_capture_flag": snap.get("duplicate_capture_flag", False),
            "correct_company": meta["correct_company"],
            "valid_archived_page": meta["valid_archived_page"],
            "temporally_appropriate": meta["temporally_appropriate"],
            "content_extraction_usable": content_usable,
            "duplicate_capture": meta["duplicate_capture"],
            "reviewer_notes": notes,
            "validation_screenshot_path": meta["validation_screenshot_path"],
        })

    with open(out / "manual_validation_sample.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(val_rows[0].keys()))
        w.writeheader()
        w.writerows(val_rows)

    usable = sum(1 for r in val_rows if r["content_extraction_usable"] == "True")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "comparisons": comparisons, "usable_count": usable}
    (out / "extraction_reextract_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nFinal usable: {usable}/19")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
