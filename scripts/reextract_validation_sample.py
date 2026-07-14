#!/usr/bin/env python3
"""Re-extract failed validation-sample homepages and measure improvement."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.crawl.fetcher import PageFetcher
from ffb_webminer.extract.domain import parse_domain
from ffb_webminer.extract.html_metadata import extract_metadata
from ffb_webminer.extract.html_preprocess import expand_archived_html
from ffb_webminer.extract.text import count_family_terms, extract_text
from ffb_webminer.pipeline.schemas import PAGE_COLUMNS
from ffb_webminer.quality.checks import check_page
from ffb_webminer.quality.page_validation import validate_page_for_analysis


def _homepage_row(pages: list[dict], firm_id: str, timepoint: str) -> dict | None:
    for p in pages:
        if p["firm_id"] == firm_id and p["relative_timepoint"] == timepoint:
            if p.get("path", "/") in ("/", "") and p.get("page_priority_reason") == "homepage":
                return p
    for p in pages:
        if p["firm_id"] == firm_id and p["relative_timepoint"] == timepoint:
            if p.get("path", "/") in ("/", ""):
                return p
    return None


def main() -> int:
    config = PipelineConfig.from_yaml(ROOT / "config" / "pilot.yaml")
    output_dir = ROOT / config.run.output_dir
    validation_path = output_dir / "manual_validation_sample.csv"
    pages_path = output_dir / "pages.csv"
    firms_path = output_dir / "firms.csv"

    validation_rows = list(csv.DictReader(validation_path.open()))
    failed = [r for r in validation_rows if r.get("content_extraction_usable") != "True"]

    pages_df = pd.read_csv(pages_path)
    pages = pages_df.to_dict("records")
    firms = {str(r["firm_id"]): r for r in csv.DictReader(firms_path.open())}
    snapshots = {
        (str(r["firm_id"]), r["relative_timepoint"]): r
        for r in csv.DictReader((output_dir / "snapshots.csv").open())
    }

    fetcher = PageFetcher(
        user_agent=config.crawl.user_agent,
        timeout_seconds=config.crawl.timeout_seconds,
        max_bytes=config.crawl.max_response_bytes,
        throttle_seconds=config.crawl.throttle_seconds,
        raw_html_dir=ROOT / config.extract.raw_html_dir,
        store_raw_html=config.extract.store_raw_html,
    )

    comparisons: list[dict] = []
    updated_pages: list[dict] = []

    for vr in failed:
        fid = vr["firm_id"]
        tp = vr["relative_timepoint"]
        old = _homepage_row(pages, fid, tp) or {}
        firm = firms[fid]
        snap = snapshots.get((fid, tp), {})
        replay_url = vr["wayback_replay_url"]
        original = vr["original_archived_url"]

        # Parse timestamp from replay URL
        from ffb_webminer.archive.wayback_url import parse_wayback_url

        parsed = parse_wayback_url(replay_url)
        ts = parsed[0] if parsed else None

        fetch = None
        for attempt in range(3):
            fetch = fetcher.fetch(original, archive_timestamp=ts, use_cache=(attempt > 0))
            if fetch.content:
                break
        assert fetch is not None
        new_row = dict(old) if old else {c: None for c in PAGE_COLUMNS}
        if snap:
            new_row.update({
                "run_id": snap.get("run_id"),
                "firm_id": snap.get("firm_id"),
                "rank": snap.get("rank"),
                "company": snap.get("company"),
                "event_type": snap.get("event_type"),
                "event_year": snap.get("event_year"),
                "event_label": snap.get("event_label"),
                "relative_timepoint": snap.get("relative_timepoint"),
                "target_year": snap.get("target_year"),
                "target_date": snap.get("target_date"),
                "observation_is_future": snap.get("observation_is_future"),
                "snapshot_status": snap.get("snapshot_status"),
                "snapshot_observation_key": f"{fid}|{tp}",
                "analysis_eligible": bool(snap.get("analysis_eligible")),
                "archive_timestamp": snap.get("archive_timestamp"),
                "selected_capture_date": snap.get("selected_capture_date"),
                "temporal_distance_days": snap.get("temporal_distance_days"),
                "temporal_fit_quality": snap.get("temporal_fit_quality"),
            })

        if fetch.content:
            prepared = expand_archived_html(fetch.content, replay_url, fetcher=fetcher)
            meta = extract_metadata(prepared.html)
            text_ex = extract_text(
                prepared.html,
                primary=config.extract.methods.get("primary", "trafilatura"),
                fallback=config.extract.methods.get("fallback", "readability"),
                replay_url=replay_url,
            )
            domain = parse_domain(original)
            new_row.update({
                "fetch_error": None,
                "http_status": fetch.http_status,
                "raw_html_path": fetch.raw_html_path,
                "content_hash": fetch.content_hash,
                "wayback_replay_url": replay_url,
                "original_archived_url": original,
                "requested_url": fetch.requested_url,
                "final_url": fetch.final_url,
                "registrable_domain": domain.registrable_domain,
                "path": domain.path or "/",
                "page_priority_reason": "homepage",
                "crawl_depth": 0,
            })
            if meta:
                new_row.update({
                    "document_title": meta.document_title,
                    "meta_description": meta.meta_description,
                    "html_lang": meta.html_lang,
                    "h1_text": meta.h1_text,
                    "h2_text": meta.h2_text,
                    "headings_json": meta.headings_json,
                })
            if text_ex:
                new_row.update({
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
            new_row = check_page(new_row, firm["primary_domain"], config.quality)
            new_row = validate_page_for_analysis(
                new_row,
                firm["primary_domain"],
                config.quality,
            )
        else:
            new_row["fetch_error"] = fetch.fetch_error
            new_row["usable_for_analysis"] = False

        old_words = int(float(old.get("word_count") or 0))
        new_words = int(float(new_row.get("word_count") or 0))
        old_family = count_family_terms(old.get("main_text"))
        new_family = count_family_terms(new_row.get("main_text"))

        comp = {
            "firm_id": fid,
            "timepoint": tp,
            "company": vr["company"],
            "old_method": old.get("extraction_method"),
            "new_method": new_row.get("extraction_method"),
            "old_words": old_words,
            "new_words": new_words,
            "old_usable": old.get("usable_for_analysis"),
            "new_usable": new_row.get("usable_for_analysis"),
            "old_family_terms": old_family,
            "new_family_terms": new_family,
            "old_boilerplate": old.get("boilerplate_ratio"),
            "new_boilerplate": new_row.get("boilerplate_ratio"),
            "fetch_error": fetch.fetch_error,
            "improved": bool(new_row.get("usable_for_analysis")) and new_words >= 50,
        }
        comparisons.append(comp)
        updated_pages.append((fid, tp, new_row))
        print(
            f"{fid}|{tp}: {old_words}->{new_words} words, "
            f"usable {old.get('usable_for_analysis')}->{new_row.get('usable_for_analysis')}, "
            f"method={new_row.get('extraction_method')}"
        )

    # Merge into pages.csv
    for fid, tp, new_row in updated_pages:
        mask = (
            (pages_df["firm_id"].astype(str) == fid)
            & (pages_df["relative_timepoint"] == tp)
            & (pages_df["path"].fillna("/").isin(["/", ""]))
        )
        if mask.any():
            for col, val in new_row.items():
                if col in pages_df.columns and val is not None and (not (isinstance(val, float) and pd.isna(val))):
                    pages_df.loc[mask, col] = val
        elif new_row.get("run_id"):
            pages_df = pd.concat([pages_df, pd.DataFrame([new_row])], ignore_index=True)

    pages_df.to_csv(pages_path, index=False)

    # Update manual validation where improved
    val_by_key = {(r["firm_id"], r["relative_timepoint"]): r for r in validation_rows}
    for comp in comparisons:
        key = (comp["firm_id"], comp["timepoint"])
        if comp["improved"] or (comp["new_words"] >= 50 and not comp["fetch_error"]):
            row = val_by_key[key]
            row["content_extraction_usable"] = "True"
            old_notes = row.get("reviewer_notes", "")
            row["reviewer_notes"] = (
                f"Re-extraction improved: {comp['old_words']}->{comp['new_words']} words "
                f"via {comp['new_method']}. {old_notes}"
            )[:500]

    with validation_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=validation_rows[0].keys())
        writer.writeheader()
        writer.writerows(validation_rows)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "comparisons": comparisons,
        "new_usable_count": sum(1 for c in comparisons if str(c["new_usable"]).lower() == "true"),
        "total_failed": len(comparisons),
    }
    (output_dir / "extraction_reextract_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
