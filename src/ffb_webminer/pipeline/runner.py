"""Pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ffb_webminer.archive.cdx_client import CDXClient
from ffb_webminer.archive.snapshot_selector import select_snapshot, target_date_for_year
from ffb_webminer.config import PipelineConfig
from ffb_webminer.crawl.crawler import crawl_snapshot
from ffb_webminer.crawl.fetcher import PageFetcher
from ffb_webminer.extract.domain import parse_domain
from ffb_webminer.extract.html_metadata import extract_metadata
from ffb_webminer.extract.text import extract_text
from ffb_webminer.extract.visual import extract_homepage_visuals
from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.schemas import (
    FIRM_COLUMNS,
    PAGE_COLUMNS,
    QUALITY_SUMMARY_COLUMNS,
    SNAPSHOT_COLUMNS,
    VISUAL_COLUMNS,
)
from ffb_webminer.quality.checks import check_page, summarize_snapshot_pages
from ffb_webminer.quality.validation import build_manual_validation_sample

logger = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(self, config: PipelineConfig, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path.cwd()
        self.config = config.resolve_paths(self.project_root)
        self.run_id = config.run.run_id or str(uuid.uuid4())
        self.config.run.run_id = self.run_id
        self.state_dir = Path(self.config.run.interim_dir) / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = Path(self.config.run.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self, input_csv: str | None = None, top_n: int | None = None) -> pd.DataFrame:
        path = input_csv or self.config.run.input_csv
        n = top_n or self.config.run.top_n
        df = pd.read_csv(path, encoding="utf-8")
        firms = df.head(n).copy()
        firms["run_id"] = self.run_id
        firms["firm_id"] = firms["rank"].astype(str)
        firms = firms.rename(columns={"rank": "rank"})
        pipeline_io.write_csv(firms, self.output_dir / "firms.csv", FIRM_COLUMNS)
        observations = self._build_observation_grid(firms)
        observations.to_csv(self.state_dir / "observations.csv", index=False)
        logger.info("Prepared %d firms, %d observations", len(firms), len(observations))
        return firms

    def _build_observation_grid(self, firms: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, firm in firms.iterrows():
            event_year = int(firm["event_year"])
            for tp in self.config.timepoints.relative:
                offset = self.config.timepoints.year_offsets[tp]
                target_year = event_year + offset
                target = target_date_for_year(target_year, self.config.snapshot_selection)
                rows.append({
                    "run_id": self.run_id,
                    "firm_id": str(firm["firm_id"]),
                    "rank": firm["rank"],
                    "company": firm["company"],
                    "event_type": firm["event_type"],
                    "event_year": event_year,
                    "event_label": firm["event_label"],
                    "relative_timepoint": tp,
                    "target_year": target_year,
                    "target_date": target.isoformat(),
                    "observation_is_future": target > date.today(),
                    "primary_domain": firm["primary_domain"],
                    "website": firm["website"],
                })
        return pd.DataFrame(rows)

    def discover_snapshots(self, firm_ids: list[str] | None = None) -> pd.DataFrame:
        obs = pd.read_csv(self.state_dir / "observations.csv")
        if firm_ids:
            obs = obs[obs["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
        client = CDXClient(
            api_url=self.config.archive.cdx_api_url,
            cache_dir=self.config.archive.cache_dir,
            user_agent=self.config.crawl.user_agent,
            throttle_seconds=self.config.crawl.throttle_seconds,
            retry_max=self.config.archive.retry_max,
            retry_backoff_base=self.config.archive.retry_backoff_base,
        )
        rows = []
        for _, row in obs.iterrows():
            if row["observation_is_future"]:
                rows.append(self._future_snapshot_row(row))
                continue
            captures, attempts = client.search_url_variants(
                domain=row["primary_domain"],
                website=row["website"],
                variants=self.config.snapshot_selection.url_variants,
                status_codes=self.config.snapshot_selection.allowed_status_codes,
                mimetypes=self.config.snapshot_selection.allowed_mimetypes,
            )
            target = date.fromisoformat(row["target_date"])
            sel = select_snapshot(captures, target, self.config.snapshot_selection)
            rows.append({
                "run_id": self.run_id,
                "firm_id": row["firm_id"],
                "rank": row["rank"],
                "company": row["company"],
                "event_type": row["event_type"],
                "event_year": row["event_year"],
                "event_label": row["event_label"],
                "relative_timepoint": row["relative_timepoint"],
                "target_year": row["target_year"],
                "target_date": row["target_date"],
                "observation_is_future": False,
                "snapshot_status": sel.snapshot_status,
                "capture_source": "wayback",
                "requested_url": sel.requested_url,
                "canonical_original_url": sel.canonical_original_url,
                "archive_timestamp": sel.archive_timestamp,
                "selected_capture_date": sel.selected_capture_date.isoformat() if sel.selected_capture_date else None,
                "temporal_distance_days": sel.temporal_distance_days,
                "wayback_replay_url": sel.wayback_replay_url,
                "http_status": sel.http_status,
                "mime_type": sel.mime_type,
                "digest": sel.digest,
                "redirect_chain": sel.redirect_chain,
                "selection_reason": sel.selection_reason,
                "fallback_attempts": attempts if isinstance(attempts, str) else json.dumps(attempts),
                "failure_reason": sel.failure_reason,
                "event_year_precision_note": self.config.snapshot_selection.event_year_precision_note if row["relative_timepoint"] == "event" else None,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            })
        snapshots = pd.DataFrame(rows)
        pipeline_io.write_csv(snapshots, self.output_dir / "snapshots.csv", SNAPSHOT_COLUMNS)
        snapshots.to_csv(self.state_dir / "snapshots.csv", index=False)
        return snapshots

    def _future_snapshot_row(self, row: pd.Series) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "firm_id": row["firm_id"],
            "rank": row["rank"],
            "company": row["company"],
            "event_type": row["event_type"],
            "event_year": row["event_year"],
            "event_label": row["event_label"],
            "relative_timepoint": row["relative_timepoint"],
            "target_year": row["target_year"],
            "target_date": row["target_date"],
            "observation_is_future": True,
            "snapshot_status": "future_unavailable",
            "capture_source": "wayback",
            "requested_url": None,
            "canonical_original_url": None,
            "archive_timestamp": None,
            "selected_capture_date": None,
            "temporal_distance_days": None,
            "wayback_replay_url": None,
            "http_status": None,
            "mime_type": None,
            "digest": None,
            "redirect_chain": None,
            "selection_reason": "future_unavailable",
            "fallback_attempts": None,
            "failure_reason": None,
            "event_year_precision_note": None,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }

    def crawl_and_extract(self, firm_ids: list[str] | None = None) -> pd.DataFrame:
        if not (self.state_dir / "snapshots.csv").exists():
            self.discover_snapshots(firm_ids=firm_ids)
        snapshots = pd.read_csv(self.state_dir / "snapshots.csv")
        if firm_ids:
            snapshots = snapshots[snapshots["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
        firms = pd.read_csv(self.output_dir / "firms.csv")

        fetcher = PageFetcher(
            user_agent=self.config.crawl.user_agent,
            timeout_seconds=self.config.crawl.timeout_seconds,
            max_bytes=self.config.crawl.max_response_bytes,
            throttle_seconds=self.config.crawl.throttle_seconds,
            raw_html_dir=self.config.extract.raw_html_dir,
            store_raw_html=self.config.extract.store_raw_html,
        )

        all_pages: list[dict[str, Any]] = []
        content_hashes: dict[str, str] = {}

        for _, snap in snapshots.iterrows():
            snap_firm_id = str(snap["firm_id"])
            if snap["snapshot_status"] != "selected":
                all_pages.extend(self._empty_pages_for_snapshot(snap))
                continue
            firm = firms[firms["firm_id"].astype(str) == snap_firm_id].iloc[0]
            seed = snap["canonical_original_url"] or firm["website"]
            crawl = crawl_snapshot(
                seed_original_url=seed,
                archive_timestamp=str(snap["archive_timestamp"]),
                registrable_domain=firm["primary_domain"],
                config=self.config.crawl,
                fetcher=fetcher,
            )
            for cp in crawl.pages:
                page_row = self._page_row_from_crawl(snap, firm, cp)
                page_row = check_page(page_row, firm["primary_domain"], self.config.quality)
                ch = page_row.get("content_hash")
                if ch and ch in content_hashes:
                    page_row["duplicate_content_flag"] = True
                    page_row["usable_for_analysis"] = False
                    page_row["exclusion_reason"] = "duplicate_content"
                elif ch:
                    content_hashes[ch] = page_row["original_archived_url"]
                all_pages.append(page_row)

        pages_df = pd.DataFrame(all_pages)
        out_path = self.output_dir / "pages.csv"
        if firm_ids and out_path.exists():
            existing = pd.read_csv(out_path)
            keep = existing[~existing["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
            pages_df = pd.concat([keep, pages_df], ignore_index=True)
        pipeline_io.write_csv(pages_df, out_path, PAGE_COLUMNS)
        if not pages_df.empty:
            pipeline_io.write_parquet(pages_df, self.output_dir / "pages.parquet")
        pages_df.to_csv(self.state_dir / "pages.csv", index=False)
        return pages_df

    def _empty_pages_for_snapshot(self, snap: pd.Series) -> list[dict[str, Any]]:
        row = {c: None for c in PAGE_COLUMNS}
        row.update({
            "run_id": self.run_id,
            "firm_id": snap["firm_id"],
            "rank": snap["rank"],
            "company": snap["company"],
            "event_type": snap["event_type"],
            "event_year": snap["event_year"],
            "event_label": snap["event_label"],
            "relative_timepoint": snap["relative_timepoint"],
            "target_year": snap["target_year"],
            "target_date": snap["target_date"],
            "observation_is_future": snap["observation_is_future"],
            "snapshot_status": snap["snapshot_status"],
            "capture_source": "wayback",
            "usable_for_analysis": False,
            "exclusion_reason": snap["snapshot_status"],
        })
        return [row]

    def _page_row_from_crawl(self, snap: pd.Series, firm: pd.Series, cp) -> dict[str, Any]:
        fetch = cp.fetch
        row = {c: None for c in PAGE_COLUMNS}
        domain = parse_domain(cp.original_url)
        meta = extract_metadata(fetch.content) if fetch and fetch.content else None
        text_ex = (
            extract_text(
                fetch.content,
                primary=self.config.extract.methods.get("primary", "trafilatura"),
                fallback=self.config.extract.methods.get("fallback", "readability"),
            )
            if fetch and fetch.content
            else None
        )
        row.update({
            "run_id": self.run_id,
            "firm_id": snap["firm_id"],
            "rank": snap["rank"],
            "company": snap["company"],
            "event_type": snap["event_type"],
            "event_year": snap["event_year"],
            "event_label": snap["event_label"],
            "relative_timepoint": snap["relative_timepoint"],
            "target_year": snap["target_year"],
            "target_date": snap["target_date"],
            "observation_is_future": snap["observation_is_future"],
            "capture_source": "wayback",
            "archive_timestamp": snap["archive_timestamp"],
            "selected_capture_date": snap["selected_capture_date"],
            "temporal_distance_days": snap["temporal_distance_days"],
            "snapshot_status": snap["snapshot_status"],
            "wayback_replay_url": fetch.wayback_replay_url if fetch else snap["wayback_replay_url"],
            "original_archived_url": cp.original_url,
            "requested_url": fetch.requested_url if fetch else None,
            "final_url": fetch.final_url if fetch else None,
            "redirect_chain": fetch.redirect_chain if fetch else None,
            "http_status": fetch.http_status if fetch else None,
            "mime_type": fetch.mime_type if fetch else None,
            "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
            "fetch_error": fetch.fetch_error if fetch else None,
            "content_hash": fetch.content_hash if fetch else None,
            "scheme": domain.scheme,
            "hostname": domain.hostname,
            "subdomain": domain.subdomain,
            "registrable_domain": domain.registrable_domain,
            "suffix": domain.suffix,
            "normalized_url": domain.normalized_url,
            "path": domain.path,
            "query": domain.query,
            "crawl_depth": cp.depth,
            "discovered_from_url": cp.discovered_from_url,
            "page_priority_reason": cp.priority_reason,
        })
        if meta:
            row.update({
                "document_title": meta.document_title,
                "meta_description": meta.meta_description,
                "meta_keywords": meta.meta_keywords,
                "html_lang": meta.html_lang,
                "canonical_url": meta.canonical_url,
                "og_title": meta.og_title,
                "og_description": meta.og_description,
                "og_site_name": meta.og_site_name,
                "h1_text": meta.h1_text,
                "h2_text": meta.h2_text,
                "headings_json": meta.headings_json,
            })
        if fetch:
            row["raw_html_path"] = fetch.raw_html_path
        if text_ex:
            row.update({
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
        return row

    def extract_visuals(self, firm_ids: list[str] | None = None) -> pd.DataFrame:
        if not self.config.visual.enabled:
            return pd.DataFrame(columns=VISUAL_COLUMNS)
        snapshots = pd.read_csv(self.state_dir / "snapshots.csv")
        if firm_ids:
            snapshots = snapshots[snapshots["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
        snapshots = snapshots[snapshots["snapshot_status"] == "selected"]
        rows = []
        for _, snap in snapshots.iterrows():
            replay = snap["wayback_replay_url"]
            if not replay:
                continue
            cache_key = hashlib.sha256(f"{snap['firm_id']}|{snap['relative_timepoint']}".encode()).hexdigest()[:16]
            vis = extract_homepage_visuals(
                replay_url=replay,
                screenshot_dir=self.config.visual.screenshot_dir,
                viewport_width=self.config.visual.viewport_width,
                viewport_height=self.config.visual.viewport_height,
                cache_key=cache_key,
            )
            rows.append({
                "run_id": self.run_id,
                "firm_id": snap["firm_id"],
                "rank": snap["rank"],
                "company": snap["company"],
                "relative_timepoint": snap["relative_timepoint"],
                "target_year": snap["target_year"],
                "archive_timestamp": snap["archive_timestamp"],
                "wayback_replay_url": replay,
                "original_archived_url": snap["canonical_original_url"],
                "rendered_success": vis.rendered_success,
                "viewport_width": vis.viewport_width,
                "viewport_height": vis.viewport_height,
                "screenshot_path": vis.screenshot_path,
                "body_background_color": vis.body_background_color,
                "header_background_color": vis.header_background_color,
                "hero_background_color": vis.hero_background_color,
                "h1_text": vis.h1_text,
                "h1_font_family": vis.h1_font_family,
                "h1_font_size_px": vis.h1_font_size_px,
                "h1_font_weight": vis.h1_font_weight,
                "h1_color": vis.h1_color,
                "computed_style_source": vis.computed_style_source,
                "css_stylesheet_count": vis.css_stylesheet_count,
                "missing_asset_count": vis.missing_asset_count,
                "visual_extraction_confidence": vis.visual_extraction_confidence,
                "visual_extraction_error": vis.visual_extraction_error,
                "dominant_colors_json": vis.dominant_colors_json,
            })
        df = pd.DataFrame(rows)
        pipeline_io.write_csv(df, self.output_dir / "homepage_visuals.csv", VISUAL_COLUMNS)
        return df

    def report(self) -> None:
        snapshots = pd.read_csv(self.output_dir / "snapshots.csv")
        pages_path = self.output_dir / "pages.csv"
        pages = pd.read_csv(pages_path) if pages_path.exists() else pd.DataFrame()

        summaries = []
        for _, snap in snapshots.iterrows():
            snap_firm_id = str(snap["firm_id"])
            snap_tp = snap["relative_timepoint"]
            if not pages.empty:
                snap_pages = pages[
                    (pages["firm_id"].astype(str) == snap_firm_id)
                    & (pages["relative_timepoint"] == snap_tp)
                ]
                page_list = snap_pages.to_dict("records")
            else:
                page_list = []
            summaries.append(summarize_snapshot_pages(
                page_list, self.run_id, str(snap["firm_id"]), int(snap["rank"]),
                snap["company"], snap["relative_timepoint"], int(snap["target_year"]),
                snap["snapshot_status"],
            ))
        summary_df = pd.DataFrame(summaries)
        pipeline_io.write_csv(summary_df, self.output_dir / "quality_summary.csv", QUALITY_SUMMARY_COLUMNS)

        if not pages.empty:
            sample = build_manual_validation_sample(
                pages, sample_size=self.config.quality.manual_validation_sample_size
            )
            sample.to_csv(self.output_dir / "manual_validation_sample.csv", index=False, encoding="utf-8")

        self._write_manifest(snapshots, pages, summary_df)
        self._write_quality_report(snapshots, pages, summary_df)

    def _write_manifest(self, snapshots: pd.DataFrame, pages: pd.DataFrame, summary: pd.DataFrame) -> None:
        commit = None
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=self.project_root, text=True
            ).strip()
        except Exception:
            pass
        manifest = {
            "run_id": self.run_id,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "config": self.config.model_dump(),
            "counts": {
                "firms": len(pd.read_csv(self.output_dir / "firms.csv")),
                "snapshots": len(snapshots),
                "snapshots_selected": int((snapshots["snapshot_status"] == "selected").sum()),
                "pages": len(pages),
                "pages_usable": int(pages["usable_for_analysis"].fillna(False).sum()) if not pages.empty else 0,
            },
        }
        path = self.output_dir / "run_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    def _write_quality_report(
        self, snapshots: pd.DataFrame, pages: pd.DataFrame, summary: pd.DataFrame
    ) -> None:
        lines = [
            "# Pilot Quality Report",
            "",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Snapshot coverage",
            "",
            "| Company | Timepoint | Target year | Status | Distance (days) |",
            "|---------|-----------|-------------|--------|-----------------|",
        ]
        for _, s in snapshots.iterrows():
            lines.append(
                f"| {s['company']} | {s['relative_timepoint']} | {s['target_year']} | "
                f"{s['snapshot_status']} | {s.get('temporal_distance_days', '')} |"
            )
        lines.extend(["", "## Page extraction summary", ""])
        if summary.empty:
            lines.append("No pages extracted.")
        else:
            lines.append("| Company | Timepoint | Attempted | Usable | Avg chars |")
            lines.append("|---------|-----------|-----------|--------|-----------|")
            for _, r in summary.iterrows():
                lines.append(
                    f"| {r['company']} | {r['relative_timepoint']} | {r['pages_attempted']} | "
                    f"{r['pages_usable']} | {r['avg_text_chars']} |"
                )
        future = snapshots[snapshots["snapshot_status"] == "future_unavailable"]
        if not future.empty:
            lines.extend(["", "## Future unavailable observations", ""])
            for _, f in future.iterrows():
                lines.append(f"- {f['company']} / {f['relative_timepoint']} (target {f['target_year']})")
        report_path = Path(self.config.run.reports_dir) / "pilot_quality_report.md"
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_all(self, firm_ids: list[str] | None = None) -> None:
        self.prepare()
        self.discover_snapshots(firm_ids=firm_ids)
        self.crawl_and_extract(firm_ids=firm_ids)
        self.extract_visuals(firm_ids=firm_ids)
        self.report()
