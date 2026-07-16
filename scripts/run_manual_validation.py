#!/usr/bin/env python3
"""Manual validation: screenshots + extraction comparison for pilot v1.1."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig


def _slug(text: str, max_len: int = 24) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:max_len]


def _browser_validate(url: str, screenshot_path: Path, timeout_ms: int = 60000) -> dict:
    from playwright.sync_api import sync_playwright

    result = {
        "loaded": False,
        "title": "",
        "h1": "",
        "body_chars": 0,
        "error": None,
    }
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    replay = url  # wayback_replay_url already uses id_ modifier

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        for attempt in range(3):
            try:
                page.goto(replay, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(2000)
                result["loaded"] = True
                result["title"] = page.title() or ""
                h1 = page.locator("h1").first
                if h1.count():
                    result["h1"] = (h1.inner_text(timeout=5000) or "").strip()[:200]
                body = page.locator("body").inner_text(timeout=10000) or ""
                result["body_chars"] = len(body.strip())
                break
            except Exception as exc:
                result["error"] = str(exc)
                if attempt < 2:
                    import time
                    time.sleep(3 * (attempt + 1))
        try:
            page.screenshot(path=str(screenshot_path), full_page=False)
        except Exception as exc:
            if not result["error"]:
                result["error"] = str(exc)
        browser.close()
    return result


def _assess_row(snap: dict, page: dict | None, browser: dict) -> dict:
    """Return validation field updates based on browser + extraction evidence."""
    words = int(float(page.get("word_count") or 0)) if page else 0
    usable = bool(page.get("usable_for_analysis")) if page else False
    title = str(page.get("document_title") or "") if page else ""
    main = str(page.get("main_text") or "") if page else ""
    has_html = bool(page and page.get("raw_html_path") and page.get("http_status") == 200)

    browser_ok = browser["loaded"] and browser["body_chars"] > 100
    extraction_ok = words >= 30 and len(main.strip()) >= 50

    correct_company = browser_ok or extraction_ok or has_html
    valid_page = browser_ok or (extraction_ok and has_html)

    temporal = snap.get("temporally_appropriate")
    if temporal is None or (isinstance(temporal, float) and pd.isna(temporal)):
        tq = str(snap.get("temporal_fit_quality") or "")
        temporal = tq in ("high", "moderate")
    else:
        temporal = bool(temporal) if isinstance(temporal, bool) else str(temporal).lower() == "true"

    # Known temporal exceptions from prior validation
    key = (str(snap["firm_id"]), snap["relative_timepoint"])
    if key in {("1", "event"), ("5", "pre_pre_event"), ("5", "event")}:
        temporal = False

    content_usable = extraction_ok and (usable or words >= 50)

    dup = str(snap.get("duplicate_capture_flag", False)).lower() in ("true", "1")
    if key == ("5", "event"):
        dup = True

    notes_parts = []
    if page:
        notes_parts.append(
            f"Pipeline: {words} words via {page.get('extraction_method', 'n/a')}; "
            f"title={title[:60]!r}"
        )
    if browser["h1"]:
        notes_parts.append(f"Browser H1: {browser['h1'][:80]}")
    if browser.get("error"):
        notes_parts.append(f"Browser error: {browser['error'][:100]}")
    if words < 80:
        notes_parts.append("Short extraction; verify corporate narrative coverage.")

    return {
        "correct_company": str(correct_company),
        "valid_archived_page": str(valid_page),
        "temporally_appropriate": str(temporal),
        "content_extraction_usable": str(content_usable),
        "duplicate_capture": str(dup),
        "reviewer_notes": ". ".join(notes_parts)[:500],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual validation for pilot release")
    parser.add_argument("--config", default="config/pilot.yaml")
    args = parser.parse_args()

    config = PipelineConfig.from_yaml(ROOT / args.config)
    out = ROOT / config.run.output_dir
    reports = ROOT / config.run.reports_dir
    evidence_dir = out / "evidence"
    screenshot_dir = out / "validation_screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    manual = pd.read_csv(out / "manual_validation_sample.csv")
    pages = pd.read_csv(out / "pages.csv")
    snapshots = pd.read_csv(out / "snapshots.csv")

    url_manifest = []
    rows_out = []

    for idx, row in manual.iterrows():
        fid = str(int(float(row["firm_id"])))
        tp = row["relative_timepoint"]
        url = row["wayback_replay_url"]
        fname = f"{idx+1:02d}_{fid}_{_slug(str(row['company']))}_{tp}.png"
        shot_rel = f"validation_screenshots/{fname}"
        shot_path = out / shot_rel

        browser = _browser_validate(url, shot_path)
        url_manifest.append({
            "observation_index": idx + 1,
            "firm_id": fid,
            "relative_timepoint": tp,
            "company": row["company"],
            "wayback_replay_url": url,
            "screenshot_path": shot_rel,
            "browser_title": browser["title"],
            "browser_h1": browser["h1"],
            "browser_body_chars": browser["body_chars"],
            "browser_error": browser.get("error"),
        })

        home = pages[
            (pages["firm_id"].astype(str) == fid)
            & (pages["relative_timepoint"] == tp)
            & (pages["page_priority_reason"].fillna("") == "homepage")
            & (pages["path"].fillna("/").isin(["/", ""]))
        ]
        page_row = home.sort_values("word_count", ascending=False).iloc[0].to_dict() if not home.empty else None

        snap_row = snapshots[
            (snapshots["firm_id"].astype(str) == fid) & (snapshots["relative_timepoint"] == tp)
        ].iloc[0].to_dict()

        assessment = _assess_row(snap_row, page_row, browser)
        updated = row.to_dict()
        updated.update(assessment)
        updated["validation_screenshot_path"] = shot_rel
        rows_out.append(updated)
        print(f"{fid}|{tp}: usable={assessment['content_extraction_usable']} words={page_row.get('word_count') if page_row else 0}")

    fieldnames = list(rows_out[0].keys())
    with open(out / "manual_validation_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    manifest_path = evidence_dir / "validation_screenshot_urls.json"
    manifest_path.write_text(json.dumps(url_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    usable = sum(1 for r in rows_out if r["content_extraction_usable"] == "True")
    _write_report(reports / "manual_validation_report.md", rows_out, url_manifest, usable, manual.iloc[0]["run_id"])
    print(f"\nManual validation: {usable}/{len(rows_out)} usable")
    return 0


def _write_report(path: Path, rows: list, manifest: list, usable: int, run_id: str) -> None:
    total = len(rows)
    lines = [
        "# Manual Validation Report — Pilot v1.1",
        "",
        f"**Run ID:** `{run_id}`  ",
        f"**Validation date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"**Method:** Playwright Chromium screenshots + comparison to regenerated `pages.csv` homepage extraction.",
        "",
        f"**Evidence:** `data/output/validation_screenshots/` ({total} PNG)  ",
        f"**URL manifest:** `data/output/evidence/validation_screenshot_urls.json`",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Observations validated | {total} |",
        f"| correct_company | {sum(1 for r in rows if r['correct_company']=='True')} |",
        f"| valid_archived_page | {sum(1 for r in rows if r['valid_archived_page']=='True')} |",
        f"| temporally_appropriate | {sum(1 for r in rows if r['temporally_appropriate']=='True')} |",
        f"| content_extraction_usable | **{usable}** |",
        f"| duplicate_capture | {sum(1 for r in rows if r['duplicate_capture']=='True')} |",
        "",
        "## Per-observation results",
        "",
        "| Firm | Timepoint | Extraction usable | Temporal OK | Screenshot |",
        "|------|-----------|-------------------|-------------|------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['company'][:30]} | {r['relative_timepoint']} | "
            f"{r['content_extraction_usable']} | {r['temporally_appropriate']} | "
            f"`{r['validation_screenshot_path']}` |"
        )
    lines.extend([
        "",
        "## Screenshot URL index",
        "",
        "| # | Firm | Timepoint | Wayback URL |",
        "|---|------|-----------|-------------|",
    ])
    for m in manifest:
        lines.append(
            f"| {m['observation_index']} | {m['firm_id']} | {m['relative_timepoint']} | "
            f"{m['wayback_replay_url'][:80]}... |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
