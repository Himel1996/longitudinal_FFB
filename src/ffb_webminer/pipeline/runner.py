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
from ffb_webminer.archive.event_dates import (
    load_event_date_overrides,
    resolve_event_date,
    resolve_event_date_full,
    target_date_for_timepoint,
)
from ffb_webminer.archive.snapshot_selector import (
    select_snapshot,
    validate_event_observation,
)
from ffb_webminer.config import PipelineConfig
from ffb_webminer.crawl.crawler import crawl_snapshot
from ffb_webminer.crawl.fetcher import PageFetcher
from ffb_webminer.extract.domain import parse_domain
from ffb_webminer.extract.html_metadata import extract_metadata
from ffb_webminer.extract.text import extract_text
from ffb_webminer.extract.visual import extract_homepage_visuals
from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.analysis_export import (
    assign_observation_scopes,
    build_analysis_observations,
    build_analysis_observations_sensitivity,
    build_firm_coverage_matrix,
    build_full_manual_validation,
)
from ffb_webminer.pipeline.schemas import (
    ANALYSIS_OBSERVATION_COLUMNS,
    FIRM_COVERAGE_COLUMNS,
    FIRM_COLUMNS,
    MANUAL_VALIDATION_COLUMNS,
    PAGE_COLUMNS,
    QUALITY_SUMMARY_COLUMNS,
    SNAPSHOT_COLUMNS,
    VISUAL_COLUMNS,
)
from ffb_webminer.quality.checks import check_page, summarize_snapshot_pages
from ffb_webminer.quality.duplicate_captures import apply_duplicate_capture_rules
from ffb_webminer.quality.page_validation import validate_page_for_analysis
from ffb_webminer.quality.temporal_validity import (
    build_temporal_validity_report,
    enrich_snapshots_dataframe,
)

logger = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(self, config: PipelineConfig, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path.cwd()
        self.config = config.resolve_paths(self.project_root)
        self.output_dir = Path(self.config.run.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = config.run.run_id or self._load_existing_run_id() or str(uuid.uuid4())
        self.config.run.run_id = self.run_id
        self.state_dir = Path(self.config.run.interim_dir) / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline_run_date = date.today()
        self.event_overrides = load_event_date_overrides(
            self.project_root / self.config.snapshot_selection.event_dates_config
        )

    def _load_existing_run_id(self) -> str | None:
        for path in (self.output_dir / "snapshots.csv", self.output_dir / "firms.csv"):
            if not path.exists():
                continue
            try:
                df = pd.read_csv(path, nrows=1)
                if "run_id" in df.columns and pd.notna(df["run_id"].iloc[0]):
                    return str(df["run_id"].iloc[0])
            except Exception:
                continue
        return None

    def prepare(self, input_csv: str | None = None, top_n: int | None = None) -> pd.DataFrame:
        existing = self._load_existing_run_id()
        if existing:
            self.run_id = existing
            self.config.run.run_id = existing
        path = input_csv or self.config.run.input_csv
        n = top_n or self.config.run.top_n
        df = pd.read_csv(path, encoding="utf-8")
        firms = df.head(n).copy()
        firms["run_id"] = self.run_id
        firms["firm_id"] = firms["rank"].astype(str)
        event_rows = []
        for _, firm in firms.iterrows():
            full = resolve_event_date_full(firm.to_dict(), self.event_overrides)
            event_rows.append({
                "event_date_inferred": (
                    full.event_date_inferred.isoformat() if full.event_date_inferred else None
                ),
                "event_date_verified": (
                    full.event_date_verified.isoformat() if full.event_date_verified else None
                ),
                "event_date_final": (
                    full.event_date_final.isoformat() if full.event_date_final else None
                ),
                "event_date_precision": full.event_date_precision,
                "event_date_source": full.event_date_source,
                "event_date_verification_status": full.event_date_verification_status,
            })
        event_df = pd.DataFrame(event_rows)
        for col in event_df.columns:
            firms[col] = event_df[col].values
        pipeline_io.write_csv(firms, self.output_dir / "firms.csv", FIRM_COLUMNS)
        observations = self._build_observation_grid(firms)
        observations.to_csv(self.state_dir / "observations.csv", index=False)
        logger.info("Prepared %d firms, %d observations", len(firms), len(observations))
        return firms

    def _build_observation_grid(self, firms: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, firm in firms.iterrows():
            event_year = int(firm["event_year"])
            full = resolve_event_date_full(firm.to_dict(), self.event_overrides)
            ev = resolve_event_date(firm.to_dict(), self.event_overrides)
            for tp in self.config.timepoints.relative:
                offset = self.config.timepoints.year_offsets[tp]
                target_year = event_year + offset
                target, target_prec = target_date_for_timepoint(
                    tp,
                    target_year,
                    ev,
                    self.config.snapshot_selection.target_month_day,
                )
                rows.append({
                    "run_id": self.run_id,
                    "firm_id": str(firm["firm_id"]),
                    "rank": firm["rank"],
                    "company": firm["company"],
                    "event_type": firm["event_type"],
                    "event_year": event_year,
                    "event_label": firm["event_label"],
                    "event_date_inferred": (
                        full.event_date_inferred.isoformat() if full.event_date_inferred else None
                    ),
                    "event_date_verified": (
                        full.event_date_verified.isoformat() if full.event_date_verified else None
                    ),
                    "event_date_final": (
                        full.event_date_final.isoformat() if full.event_date_final else None
                    ),
                    "event_date_precision": full.event_date_precision,
                    "event_date_source": full.event_date_source,
                    "event_date_verification_status": full.event_date_verification_status,
                    "relative_timepoint": tp,
                    "target_year": target_year,
                    "target_date": target.isoformat(),
                    "target_date_precision": target_prec,
                    "observation_is_future": target > self.pipeline_run_date,
                    "primary_domain": firm["primary_domain"],
                    "website": firm["website"],
                })
        return pd.DataFrame(rows)

    def discover_snapshots(self, firm_ids: list[str] | None = None) -> pd.DataFrame:
        obs_path = self.state_dir / "observations.csv"
        if not obs_path.exists():
            self.prepare()
        obs = pd.read_csv(obs_path)
        if firm_ids:
            obs = obs[obs["firm_id"].astype(str).isin([str(f) for f in firm_ids])]

        branding_patterns = self._branding_patterns_flat()
        client = CDXClient(
            api_url=self.config.archive.cdx_api_url,
            cache_dir=self.config.archive.cache_dir,
            user_agent=self.config.crawl.user_agent,
            throttle_seconds=self.config.crawl.throttle_seconds,
            retry_max=self.config.archive.retry_max,
            retry_backoff_base=self.config.archive.retry_backoff_base,
        )
        rows: list[dict[str, Any]] = []
        for _, row in obs.iterrows():
            if row["observation_is_future"]:
                rows.append(self._future_snapshot_row(row))
                continue
            rows.append(self._discover_one_snapshot(row, client, branding_patterns))

        snapshots = pd.DataFrame(rows)
        firms = pd.read_csv(self.output_dir / "firms.csv")
        snapshots = enrich_snapshots_dataframe(
            snapshots,
            firms,
            adjacent_min_days=self.config.snapshot_selection.adjacent_period_min_days,
            override_very_low_usable=self.config.snapshot_selection.override_very_low_usable,
        )
        snapshots = apply_duplicate_capture_rules(snapshots)
        snapshots = assign_observation_scopes(snapshots)
        out_path = self.output_dir / "snapshots.csv"
        if firm_ids and out_path.exists():
            existing = pd.read_csv(out_path)
            keep = existing[~existing["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
            snapshots = pd.concat([keep, snapshots], ignore_index=True)

        pipeline_io.write_csv(snapshots, out_path, SNAPSHOT_COLUMNS)
        snapshots.to_csv(self.state_dir / "snapshots.csv", index=False)
        self._write_temporal_validity_report(snapshots)
        return snapshots

    def refresh_snapshot_metadata(self) -> pd.DataFrame:
        """Re-apply temporal validity, duplicate capture, and scope to snapshots.csv."""
        firms_path = self.output_dir / "firms.csv"
        snapshots_path = self.output_dir / "snapshots.csv"
        if not firms_path.exists():
            self.prepare()
        if not snapshots_path.exists():
            return self.discover_snapshots()
        firms = pd.read_csv(firms_path)
        snapshots = pd.read_csv(snapshots_path)
        snapshots = self._merge_firm_event_dates(snapshots, firms)
        snapshots["run_id"] = self.run_id
        snapshots = enrich_snapshots_dataframe(
            snapshots,
            firms,
            adjacent_min_days=self.config.snapshot_selection.adjacent_period_min_days,
            override_very_low_usable=self.config.snapshot_selection.override_very_low_usable,
        )
        snapshots = apply_duplicate_capture_rules(snapshots)
        snapshots = assign_observation_scopes(snapshots)
        pipeline_io.write_csv(snapshots, snapshots_path, SNAPSHOT_COLUMNS)
        snapshots.to_csv(self.state_dir / "snapshots.csv", index=False)
        self._write_temporal_validity_report(snapshots)
        return snapshots

    def _merge_firm_event_dates(self, snapshots: pd.DataFrame, firms: pd.DataFrame) -> pd.DataFrame:
        df = snapshots.copy()
        firm_cols = [
            "event_date_inferred",
            "event_date_verified",
            "event_date_final",
            "event_date_precision",
            "event_date_source",
            "event_date_verification_status",
        ]
        for col in firm_cols:
            if col not in df.columns:
                df[col] = None
        for _, firm in firms.iterrows():
            fid = str(firm["firm_id"])
            mask = df["firm_id"].astype(str) == fid
            full = resolve_event_date_full(firm.to_dict(), self.event_overrides)
            df.loc[mask, "event_date_inferred"] = (
                full.event_date_inferred.isoformat() if full.event_date_inferred else None
            )
            df.loc[mask, "event_date_verified"] = (
                full.event_date_verified.isoformat() if full.event_date_verified else None
            )
            df.loc[mask, "event_date_final"] = (
                full.event_date_final.isoformat() if full.event_date_final else None
            )
            df.loc[mask, "event_date_precision"] = full.event_date_precision
            df.loc[mask, "event_date_source"] = full.event_date_source
            df.loc[mask, "event_date_verification_status"] = full.event_date_verification_status
        return df

    def _branding_patterns_flat(self) -> list[str]:
        patterns: list[str] = []
        for lang_patterns in self.config.crawl.branding_path_patterns.values():
            patterns.extend(lang_patterns)
        return patterns

    def _discover_one_snapshot(
        self,
        row: pd.Series,
        client: CDXClient,
        branding_patterns: list[str],
    ) -> dict[str, Any]:
        captures, attempts = client.search_url_variants(
            domain=row["primary_domain"],
            website=row["website"],
            variants=self.config.snapshot_selection.url_variants,
            status_codes=self.config.snapshot_selection.allowed_status_codes,
            mimetypes=self.config.snapshot_selection.allowed_mimetypes,
        )
        target = date.fromisoformat(row["target_date"])
        sel = select_snapshot(
            captures,
            target,
            self.config.snapshot_selection,
            run_date=self.pipeline_run_date,
            homepage_only=True,
        )
        event_date = (
            date.fromisoformat(str(row["event_date_final"])[:10])
            if pd.notna(row.get("event_date_final"))
            else None
        )
        sel = validate_event_observation(
            row["relative_timepoint"],
            sel,
            event_date,
            str(row.get("event_date_precision") or "year"),
            pre_window_days=self.config.snapshot_selection.event_pre_window_days,
        )

        homepage_available = sel.homepage_available
        relevant_subpages = False
        subpage_only = False

        if sel.snapshot_status not in ("selected",):
            wildcard = client.search_domain_wildcard(
                row["primary_domain"],
                status_codes=self.config.snapshot_selection.allowed_status_codes,
                mimetypes=self.config.snapshot_selection.allowed_mimetypes,
            )
            branded = client.filter_branding_subpages(wildcard, branding_patterns)
            if branded:
                relevant_subpages = True
                if sel.snapshot_status in ("not_found", "beyond_tolerance", "event_unavailable"):
                    subpage_only = True

        note = None
        if row["relative_timepoint"] == "event":
            prec = row.get("target_date_precision", "year")
            note = (
                f"Event target uses {prec}-level precision ({row['target_date']}). "
                f"Event date source: {row.get('event_date_source', '')}"
            )

        return self._snapshot_row_from_selection(
            row, sel, attempts, homepage_available, relevant_subpages, subpage_only, note
        )

    def _snapshot_row_from_selection(
        self,
        row: pd.Series,
        sel,
        attempts: list[str] | str,
        homepage_available: bool,
        relevant_subpages: bool,
        subpage_only: bool,
        event_note: str | None,
    ) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "firm_id": row["firm_id"],
            "rank": row["rank"],
            "company": row["company"],
            "event_type": row["event_type"],
            "event_year": row["event_year"],
            "event_label": row["event_label"],
            "event_date_inferred": row.get("event_date_inferred"),
            "event_date_verified": row.get("event_date_verified"),
            "event_date_final": row.get("event_date_final"),
            "event_date_precision": row.get("event_date_precision"),
            "event_date_source": row.get("event_date_source"),
            "event_date_verification_status": row.get("event_date_verification_status"),
            "relative_timepoint": row["relative_timepoint"],
            "target_year": row["target_year"],
            "target_date": row["target_date"],
            "target_date_precision": row.get("target_date_precision"),
            "observation_is_future": False,
            "snapshot_status": sel.snapshot_status,
            "capture_source": "wayback",
            "requested_url": sel.requested_url,
            "cdx_original_url": sel.cdx_original_url,
            "canonical_original_url": sel.canonical_original_url,
            "archive_timestamp": sel.archive_timestamp,
            "selected_capture_date": sel.selected_capture_date.isoformat() if sel.selected_capture_date else None,
            "temporal_distance_days": sel.temporal_distance_days,
            "temporal_fit_quality": None,
            "temporal_fit_usable_default": None,
            "event_snapshot_position": None,
            "days_from_actual_event": None,
            "days_between_selected_snapshots": None,
            "adjacent_period_overlap_flag": False,
            "homepage_available": homepage_available,
            "relevant_subpages_available": relevant_subpages,
            "subpage_only_observation": subpage_only,
            "observation_scope": None,
            "observation_recommendation": None,
            "analysis_eligible": False,
            "duplicate_capture_flag": False,
            "duplicate_capture_winner_timepoint": None,
            "wayback_replay_url": sel.wayback_replay_url,
            "http_status": sel.http_status,
            "mime_type": sel.mime_type,
            "digest": sel.digest,
            "redirect_chain": sel.redirect_chain,
            "selection_reason": sel.selection_reason,
            "fallback_attempts": attempts if isinstance(attempts, str) else json.dumps(attempts),
            "failure_reason": sel.failure_reason,
            "event_year_precision_note": event_note,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }

    def _future_snapshot_row(self, row: pd.Series) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "firm_id": row["firm_id"],
            "rank": row["rank"],
            "company": row["company"],
            "event_type": row["event_type"],
            "event_year": row["event_year"],
            "event_label": row["event_label"],
            "event_date_inferred": row.get("event_date_inferred"),
            "event_date_verified": row.get("event_date_verified"),
            "event_date_final": row.get("event_date_final"),
            "event_date_precision": row.get("event_date_precision"),
            "event_date_source": row.get("event_date_source"),
            "event_date_verification_status": row.get("event_date_verification_status"),
            "relative_timepoint": row["relative_timepoint"],
            "target_year": row["target_year"],
            "target_date": row["target_date"],
            "target_date_precision": row.get("target_date_precision"),
            "observation_is_future": True,
            "snapshot_status": "future_unavailable",
            "capture_source": "wayback",
            "requested_url": None,
            "cdx_original_url": None,
            "canonical_original_url": None,
            "archive_timestamp": None,
            "selected_capture_date": None,
            "temporal_distance_days": None,
            "temporal_fit_quality": None,
            "temporal_fit_usable_default": None,
            "event_snapshot_position": None,
            "days_from_actual_event": None,
            "days_between_selected_snapshots": None,
            "adjacent_period_overlap_flag": False,
            "homepage_available": False,
            "relevant_subpages_available": False,
            "subpage_only_observation": False,
            "observation_scope": "unavailable",
            "observation_recommendation": "exclude",
            "analysis_eligible": False,
            "duplicate_capture_flag": False,
            "duplicate_capture_winner_timepoint": None,
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
        snapshots_path = self.output_dir / "snapshots.csv"
        if not snapshots_path.exists():
            self.discover_snapshots(firm_ids=firm_ids)
        snapshots = pd.read_csv(snapshots_path)
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
            retries=self.config.crawl.retries,
        )

        crawled_by_capture: dict[tuple[str, str], list] = {}
        selected = snapshots[snapshots["snapshot_status"] == "selected"]
        for (firm_id, archive_ts), group in selected.groupby(["firm_id", "archive_timestamp"], dropna=False):
            if pd.isna(archive_ts):
                continue
            snap = group.iloc[0]
            snap_firm_id = str(firm_id)
            firm = firms[firms["firm_id"].astype(str) == snap_firm_id].iloc[0]
            seed = snap["canonical_original_url"] or firm["website"]
            crawl = crawl_snapshot(
                seed_original_url=seed,
                archive_timestamp=str(archive_ts),
                registrable_domain=firm["primary_domain"],
                config=self.config.crawl,
                fetcher=fetcher,
            )
            crawled_by_capture[(snap_firm_id, str(archive_ts))] = crawl.pages

        all_pages: list[dict[str, Any]] = []
        analysis_content_hashes: dict[str, str] = {}

        for _, snap in snapshots.iterrows():
            snap_firm_id = str(snap["firm_id"])
            if snap["snapshot_status"] != "selected" or pd.isna(snap.get("archive_timestamp")):
                all_pages.extend(self._empty_pages_for_snapshot(snap))
                continue
            firm = firms[firms["firm_id"].astype(str) == snap_firm_id].iloc[0]
            capture_key = (snap_firm_id, str(snap["archive_timestamp"]))
            crawl_pages = crawled_by_capture.get(capture_key, [])
            if not crawl_pages:
                all_pages.extend(self._empty_pages_for_snapshot(snap))
                continue
            for cp in crawl_pages:
                page_row = self._page_row_from_crawl(snap, firm, cp, fetcher=fetcher)
                page_row = check_page(page_row, firm["primary_domain"], self.config.quality)
                page_row = validate_page_for_analysis(
                    page_row,
                    firm["primary_domain"],
                    self.config.quality,
                    max_temporal_distance=self.config.quality.max_temporal_distance_days,
                )
                ch = page_row.get("content_hash")
                if page_row.get("analysis_eligible") and ch:
                    if ch in analysis_content_hashes:
                        page_row["duplicate_content_flag"] = True
                        page_row["usable_for_analysis"] = False
                        page_row["exclusion_reason"] = "duplicate_content"
                    else:
                        analysis_content_hashes[ch] = page_row["original_archived_url"]
                all_pages.append(page_row)

        pages_df = pd.DataFrame(all_pages)
        out_path = self.output_dir / "pages.csv"
        if firm_ids and out_path.exists():
            existing = pd.read_csv(out_path)
            keep = existing[~existing["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
            pages_df = pd.concat([keep, pages_df], ignore_index=True)
        else:
            self._assert_pages_match_snapshots(pages_df, pd.read_csv(snapshots_path))
        pipeline_io.write_csv(pages_df, out_path, PAGE_COLUMNS)
        if not pages_df.empty:
            pipeline_io.write_parquet(pages_df, self.output_dir / "pages.parquet")
        pages_df.to_csv(self.state_dir / "pages.csv", index=False)
        return pages_df

    def _assert_pages_match_snapshots(self, pages: pd.DataFrame, snapshots: pd.DataFrame) -> None:
        """Ensure page rows only reference current snapshot observations."""
        if pages.empty:
            return
        valid_keys = {
            (str(r["firm_id"]), r["relative_timepoint"]) for _, r in snapshots.iterrows()
        }
        page_keys = {
            (str(r["firm_id"]), r["relative_timepoint"]) for _, r in pages.iterrows()
        }
        stale = page_keys - valid_keys
        if stale:
            raise ValueError(f"Page rows reference stale observations: {sorted(stale)[:5]}")

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
            "snapshot_observation_key": f"{snap['firm_id']}|{snap['relative_timepoint']}",
            "analysis_eligible": bool(snap.get("analysis_eligible")),
            "capture_source": "wayback",
            "archive_timestamp": snap.get("archive_timestamp"),
            "page_archive_timestamp": snap.get("archive_timestamp"),
            "selected_capture_date": snap.get("selected_capture_date"),
            "temporal_distance_days": snap.get("temporal_distance_days"),
            "temporal_fit_quality": snap.get("temporal_fit_quality"),
            "wayback_replay_url": snap.get("wayback_replay_url"),
            "usable_for_analysis": False,
            "exclusion_reason": snap.get("observation_recommendation") or snap["snapshot_status"],
        })
        return [row]

    def _page_row_from_crawl(
        self,
        snap: pd.Series,
        firm: pd.Series,
        cp,
        fetcher: PageFetcher | None = None,
    ) -> dict[str, Any]:
        fetch = cp.fetch
        row = {c: None for c in PAGE_COLUMNS}
        domain = parse_domain(cp.original_url)
        html_for_extract = fetch.content if fetch and fetch.content else None
        replay_url = fetch.wayback_replay_url if fetch else snap.get("wayback_replay_url")
        if fetch and fetch.content and cp.depth == 0:
            from ffb_webminer.extract.html_preprocess import expand_archived_html

            prepared = expand_archived_html(
                fetch.content,
                replay_url=str(replay_url) if replay_url else "",
                fetcher=fetcher,
            )
            html_for_extract = prepared.html
        meta = extract_metadata(html_for_extract) if html_for_extract else None
        text_ex = (
            extract_text(
                html_for_extract,
                primary=self.config.extract.methods.get("primary", "trafilatura"),
                fallback=self.config.extract.methods.get("fallback", "readability"),
                replay_url=str(replay_url) if replay_url else None,
            )
            if html_for_extract
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
            "snapshot_status": snap["snapshot_status"],
            "snapshot_observation_key": f"{snap['firm_id']}|{snap['relative_timepoint']}",
            "analysis_eligible": bool(snap.get("analysis_eligible")),
            "capture_source": "wayback",
            "archive_timestamp": snap["archive_timestamp"],
            "page_archive_timestamp": snap["archive_timestamp"],
            "selected_capture_date": snap["selected_capture_date"],
            "temporal_distance_days": snap["temporal_distance_days"],
            "temporal_fit_quality": snap.get("temporal_fit_quality"),
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
        return row

    def validate_and_export(self) -> dict[str, Any]:
        """Build analysis-ready exports and verify page/snapshot alignment."""
        snapshots = pd.read_csv(self.output_dir / "snapshots.csv")
        pages_path = self.output_dir / "pages.csv"
        if not pages_path.exists():
            self.crawl_and_extract()
        pages = pd.read_csv(pages_path)

        self._assert_pages_match_snapshots(pages, snapshots)
        self._verify_page_fields(pages, snapshots)

        analysis = build_analysis_observations(snapshots)
        sensitivity = build_analysis_observations_sensitivity(snapshots)
        coverage = build_firm_coverage_matrix(snapshots)
        manual = build_full_manual_validation(snapshots)

        pipeline_io.write_csv(analysis, self.output_dir / "analysis_observations.csv", ANALYSIS_OBSERVATION_COLUMNS)
        pipeline_io.write_csv(
            sensitivity,
            self.output_dir / "analysis_observations_sensitivity.csv",
            ANALYSIS_OBSERVATION_COLUMNS,
        )
        pipeline_io.write_csv(coverage, self.output_dir / "firm_coverage_matrix.csv", FIRM_COVERAGE_COLUMNS)
        pipeline_io.write_csv(
            manual, self.output_dir / "manual_validation_sample.csv", MANUAL_VALIDATION_COLUMNS
        )

        stats = self._validation_stats(snapshots, pages, analysis, sensitivity)
        self._write_extraction_validation_report(snapshots, pages, stats)
        return stats

    def _verify_page_fields(self, pages: pd.DataFrame, snapshots: pd.DataFrame) -> None:
        if pages.empty:
            return
        selected_pages = pages[pages["snapshot_status"] == "selected"]
        for col in ("main_text", "visible_text", "headings_json", "document_title"):
            if col not in selected_pages.columns:
                raise ValueError(f"Missing page column: {col}")
        missing_domain = selected_pages[
            selected_pages["registrable_domain"].isna() & selected_pages["original_archived_url"].notna()
        ]
        if not missing_domain.empty:
            raise ValueError(f"{len(missing_domain)} pages missing registrable_domain")
        snap_lookup = {
            (str(r["firm_id"]), r["relative_timepoint"]): r for _, r in snapshots.iterrows()
        }
        for _, p in selected_pages.iterrows():
            key = (str(p["firm_id"]), p["relative_timepoint"])
            if key not in snap_lookup:
                raise ValueError(f"Page references unknown snapshot: {key}")
            if pd.isna(p.get("page_archive_timestamp")) and pd.notna(p.get("archive_timestamp")):
                raise ValueError(f"Page missing page_archive_timestamp: {key}")

    def _validation_stats(
        self,
        snapshots: pd.DataFrame,
        pages: pd.DataFrame,
        analysis: pd.DataFrame,
        sensitivity: pd.DataFrame,
    ) -> dict[str, Any]:
        rec_counts = snapshots["observation_recommendation"].value_counts().to_dict()
        scope_counts = snapshots["observation_scope"].value_counts().to_dict() if "observation_scope" in snapshots else {}
        dup_removed = int((snapshots["observation_recommendation"] == "exclude_duplicate_capture").sum())
        page_usable = int(pages["usable_for_analysis"].fillna(False).sum()) if not pages.empty else 0
        page_excluded = int((~pages["usable_for_analysis"].fillna(False)).sum()) if not pages.empty else 0
        exclusion_reasons = (
            pages[~pages["usable_for_analysis"].fillna(False)]["exclusion_reason"].value_counts().to_dict()
            if not pages.empty
            else {}
        )
        return {
            "included_observations": len(analysis),
            "sensitivity_observations": len(sensitivity),
            "excluded_observations": int(
                snapshots["observation_recommendation"].isin(["exclude", "exclude_duplicate_capture"]).sum()
            ),
            "duplicate_captures_removed_from_analysis": dup_removed,
            "observation_scope_counts": scope_counts,
            "page_count": len(pages),
            "pages_usable": page_usable,
            "pages_excluded": page_excluded,
            "page_exclusion_reasons": exclusion_reasons,
            "recommendation_counts": rec_counts,
        }

    def _write_extraction_validation_report(
        self, snapshots: pd.DataFrame, pages: pd.DataFrame, stats: dict[str, Any]
    ) -> None:
        lines = [
            "# Extraction Validation Report",
            "",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Observation counts",
            "",
            f"- Included (primary analysis): **{stats['included_observations']}**",
            f"- Sensitivity pool: **{stats['sensitivity_observations']}**",
            f"- Excluded: **{stats['excluded_observations']}**",
            f"- Duplicate captures removed from analysis: **{stats['duplicate_captures_removed_from_analysis']}**",
            "",
            "## Observation scope",
            "",
        ]
        for scope, count in sorted(stats.get("observation_scope_counts", {}).items()):
            lines.append(f"- {scope}: {count}")
        lines.extend([
            "",
            "## Page extraction",
            "",
            f"- Total page rows: {stats['page_count']}",
            f"- Usable for analysis: {stats['pages_usable']}",
            f"- Excluded: {stats['pages_excluded']}",
            "",
            "### Exclusion reasons",
            "",
        ])
        for reason, count in sorted(stats.get("page_exclusion_reasons", {}).items(), key=lambda x: -x[1]):
            lines.append(f"- {reason}: {count}")
        lines.extend(["", "## Manual review tasks", ""])
        manual = build_full_manual_validation(snapshots)
        lines.append(
            f"Complete manual validation for **{len(manual)}** observations "
            f"(all include + sensitivity_analysis rows in `manual_validation_sample.csv`)."
        )
        path = Path(self.config.run.reports_dir) / "extraction_validation_report.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
            manual = build_full_manual_validation(snapshots)
            pipeline_io.write_csv(
                manual, self.output_dir / "manual_validation_sample.csv", MANUAL_VALIDATION_COLUMNS
            )

        self._write_manifest(snapshots, pages, summary_df)
        self._write_quality_report(snapshots, pages, summary_df)
        if (self.output_dir / "analysis_observations.csv").exists():
            return
        self.validate_and_export()

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
            "pipeline_run_date": self.pipeline_run_date.isoformat(),
            "future_cutoff_date": self.pipeline_run_date.isoformat(),
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

    def _write_temporal_validity_report(self, snapshots: pd.DataFrame) -> None:
        report = build_temporal_validity_report(
            snapshots, self.run_id, self.pipeline_run_date
        )
        path = Path(self.config.run.reports_dir) / "temporal_validity_report.md"
        path.write_text(report, encoding="utf-8")

    def run_all(self, firm_ids: list[str] | None = None) -> None:
        self.prepare()
        self.discover_snapshots(firm_ids=firm_ids)
        self.crawl_and_extract(firm_ids=firm_ids)
        self.extract_visuals(firm_ids=firm_ids)
        self.validate_and_export()
        self.report()
