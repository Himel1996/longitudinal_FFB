"""Rescue pipeline runner: timepoint-specific seed aliases without changing core rules."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from ffb_webminer.archive.cdx_client import CDXClient
from ffb_webminer.archive.snapshot_selector import select_snapshot, validate_event_observation
from ffb_webminer.crawl.crawler import crawl_snapshot
from ffb_webminer.extract.domain import parse_domain
from ffb_webminer.pipeline.analysis_export import assign_observation_scopes
from ffb_webminer.pipeline.runner import PipelineRunner
from ffb_webminer.quality.duplicate_captures import apply_duplicate_capture_rules
from ffb_webminer.quality.temporal_validity import enrich_snapshots_dataframe
from ffb_webminer.rescue.candidates import NormalizedCandidate, expand_seed_variants
from ffb_webminer.rescue.discovery_state import (
    ATTEMPT_CDX_EMPTY,
    ATTEMPT_SELECTED,
    ATTEMPT_TRANSPORT,
    DiscoveryStateStore,
)
from ffb_webminer.rescue.timestamps import normalize_archive_timestamp, sanitize_wayback_replay_url
from ffb_webminer.rescue.transport import TRANSPORT_FAILURE_RESUMABLE, classify_fetch_error

# Columns that must be homogeneous bools before parquet merge (parent CSV may be str).
_PAGE_BOOL_COLUMNS = (
    "observation_is_future",
    "analysis_eligible",
    "selected_under_reserved_slot",
    "branding_corpus_eligible",
    "german_corpus_eligible",
    "governance_metadata_eligible",
    "duplicate_content_flag",
    "soft_404_flag",
    "archive_toolbar_removed_flag",
    "usable_for_analysis",
)


def _normalize_mixed_object_value(value: Any) -> str:
    """Stringify scalar values so firm-filtered CSV/crawl merges stay parquet-safe."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        if value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in {"nan", "none", "<na>", "nat"}:
            return ""
        return s
    if pd.isna(value):
        return ""
    return str(value)


def _normalize_pages_df_for_output(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce mixed CSV/merge dtypes so parquet write survives firm-filtered rescue merges."""
    from ffb_webminer.quality.checks import as_bool

    if df.empty:
        return df
    out = df.copy()
    if "firm_id" in out.columns:
        out["firm_id"] = out["firm_id"].astype(str)
    for col in _PAGE_BOOL_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(as_bool)
    # Remaining object columns may mix str (from CSV) with int/float (from crawl).
    for col in out.columns:
        if col in _PAGE_BOOL_COLUMNS:
            continue
        if out[col].dtype != object:
            continue
        non_null = out[col].dropna()
        if non_null.empty:
            continue
        if all(isinstance(v, str) for v in non_null.head(5000)):
            continue
        out[col] = out[col].map(_normalize_mixed_object_value)
    return out


class RescuePipelineRunner(PipelineRunner):
    """Subclass that applies firm×timepoint seed aliases during discover/crawl only.

    Selection tolerances, prioritization, eligibility, and corpus rules are inherited
    unchanged from PipelineRunner.
    """

    def __init__(
        self,
        *args,
        seed_aliases: dict[tuple[str, str], list[NormalizedCandidate]] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.seed_aliases = seed_aliases or {}
        self.rescue_discovery_log: list[dict[str, Any]] = []
        self.discovery_store: DiscoveryStateStore | None = None
        self.discovery_resume: bool = False
        self.config_hash: str | None = None
        self.candidate_file_hash: str | None = None

    def _aliases_for(self, firm_id: str, timepoint: str) -> list[NormalizedCandidate]:
        return list(self.seed_aliases.get((str(firm_id), str(timepoint)), []))

    def _persisted_snapshot_row(self, firm_id: str, timepoint: str) -> dict[str, Any] | None:
        if not self.discovery_store:
            return None
        rec = self.discovery_store.get(firm_id, timepoint)
        if not rec or not rec.has_valid_selection or not rec.snapshot_row_json:
            return None
        import json

        row = json.loads(rec.snapshot_row_json)
        row["rescue_seed_url"] = rec.rescue_seed_url or rec.candidate_seed_url
        row["rescue_source_row_id"] = rec.rescue_source_row_id or rec.source_row_id
        row["rescue_candidate_type"] = rec.rescue_candidate_type or rec.candidate_type
        row["rescue_domain"] = rec.rescue_domain or rec.candidate_domain
        row["snapshot_status"] = "selected"
        row["archive_timestamp"] = rec.selected_capture_timestamp
        return row

    def _transport_failure_snapshot_row(
        self,
        row: pd.Series,
        *,
        alias: NormalizedCandidate | None,
        error: str,
    ) -> dict[str, Any]:
        note = f"rescue_discovery_transport_failure|{error}"
        out = {
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
            "target_year": row.get("target_year"),
            "target_date": row["target_date"],
            "target_date_precision": row.get("target_date_precision"),
            "observation_is_future": False,
            "snapshot_status": "not_found",
            "capture_source": "wayback",
            "selection_reason": TRANSPORT_FAILURE_RESUMABLE,
            "failure_reason": note,
            "analysis_eligible": False,
            "rescue_seed_url": alias.candidate_seed_url if alias else None,
            "rescue_source_row_id": alias.source_row_id if alias else None,
            "rescue_candidate_type": alias.candidate_type if alias else None,
            "rescue_domain": alias.candidate_domain if alias else None,
        }
        return out

    def discover_snapshots(self, firm_ids: list[str] | None = None) -> pd.DataFrame:
        """Rescue discovery with incremental resume from persisted selections."""
        from ffb_webminer.pipeline import io as pipeline_io
        from ffb_webminer.pipeline.schemas import SNAPSHOT_COLUMNS

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
            firm_id = str(row["firm_id"])
            tp = str(row["relative_timepoint"])
            if row["observation_is_future"]:
                rows.append(self._future_snapshot_row(row))
                continue
            if self.discovery_resume and self.discovery_store:
                persisted = self._persisted_snapshot_row(firm_id, tp)
                if persisted is not None:
                    rows.append(persisted)
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

    def _discover_one_snapshot(
        self,
        row: pd.Series,
        client: CDXClient,
        branding_patterns: list[str],
    ) -> dict[str, Any]:
        firm_id = str(row["firm_id"])
        tp = str(row["relative_timepoint"])
        aliases = self._aliases_for(firm_id, tp)
        if not aliases:
            return super()._discover_one_snapshot(row, client, branding_patterns)

        target = date.fromisoformat(row["target_date"])
        status_codes = self.config.snapshot_selection.allowed_status_codes
        mimetypes = self.config.snapshot_selection.allowed_mimetypes

        best_sel = None
        best_alias: NormalizedCandidate | None = None
        best_attempts: list[str] = []
        all_attempts: list[str] = []
        transport_only = True
        saw_cdx_response = False

        for alias in aliases:
            seed_plan = [alias.candidate_seed_url] + [
                u for u in expand_seed_variants(alias.candidate_seed_url) if u != alias.candidate_seed_url
            ]
            captures: list[dict[str, str]] = []
            seen: set[str] = set()
            attempts: list[str] = []
            sel = None
            alias_transport_only = True
            for seed in seed_plan:
                attempts.append(seed)
                all_attempts.append(seed)
                try:
                    rows = client.search(seed, status_codes=status_codes, mimetypes=mimetypes)
                except Exception as exc:
                    transport = classify_fetch_error(str(exc))
                    if self.discovery_store:
                        self.discovery_store.record_attempt(
                            firm_id=firm_id,
                            relative_timepoint=tp,
                            candidate_seed_url=alias.candidate_seed_url,
                            attempt_status=ATTEMPT_TRANSPORT if transport else "discovery_error",
                            error=str(exc),
                        )
                    self.rescue_discovery_log.append(
                        {
                            "firm_id": firm_id,
                            "relative_timepoint": tp,
                            "target_date": str(row.get("target_date")),
                            "source_row_id": alias.source_row_id,
                            "original_configured_seed": row.get("website"),
                            "candidate_seed_url": alias.candidate_seed_url,
                            "normalized_seed": seed,
                            "selected_domain": alias.candidate_domain,
                            "historical_domain_flag": alias.historical_domain_flag,
                            "locale_path_flag": alias.locale_path_flag,
                            "migration_flag": alias.migration_warning,
                            "entity_change_flag": alias.entity_change_warning,
                            "candidate_priority": alias.priority,
                            "candidate_type": alias.candidate_type,
                            "archive_evidence": alias.archive_evidence,
                            "discovery_decision": TRANSPORT_FAILURE_RESUMABLE
                            if transport
                            else "discovery_error",
                            "rejection_reason": str(exc),
                            "error": str(exc),
                        }
                    )
                    continue
                alias_transport_only = False
                transport_only = False
                saw_cdx_response = True
                if not rows:
                    if self.discovery_store:
                        self.discovery_store.record_attempt(
                            firm_id=firm_id,
                            relative_timepoint=tp,
                            candidate_seed_url=alias.candidate_seed_url,
                            attempt_status=ATTEMPT_CDX_EMPTY,
                        )
                    continue
                for crow in rows:
                    key = f"{crow.get('timestamp', '')}|{crow.get('original', '')}"
                    if key not in seen:
                        seen.add(key)
                        captures.append(crow)
                homepage_only = alias.candidate_type in {
                    "corporate_root_alias",
                    "historical_domain",
                    "migrated_domain",
                    "locale_path",
                }
                sel = select_snapshot(
                    captures,
                    target,
                    self.config.snapshot_selection,
                    run_date=self.pipeline_run_date,
                    homepage_only=homepage_only,
                )
                if sel.snapshot_status == "selected":
                    break

            if sel is None:
                if not alias_transport_only:
                    transport_only = False
                continue
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
            self.rescue_discovery_log.append(
                {
                    "firm_id": firm_id,
                    "relative_timepoint": tp,
                    "target_date": str(row.get("target_date")),
                    "source_row_id": alias.source_row_id,
                    "original_configured_seed": row.get("website"),
                    "candidate_seed_url": alias.candidate_seed_url,
                    "normalized_seed": attempts[-1] if attempts else alias.candidate_seed_url,
                    "selected_domain": alias.candidate_domain,
                    "historical_domain_flag": alias.historical_domain_flag,
                    "locale_path_flag": alias.locale_path_flag,
                    "migration_flag": alias.migration_warning,
                    "entity_change_flag": alias.entity_change_warning,
                    "candidate_priority": alias.priority,
                    "candidate_type": alias.candidate_type,
                    "archive_evidence": alias.archive_evidence,
                    "n_captures": len(captures),
                    "snapshot_status": sel.snapshot_status,
                    "capture_timestamp": sel.archive_timestamp,
                    "capture_url": sel.canonical_original_url,
                    "capture_distance": sel.temporal_distance_days,
                    "temporal_fit_classification": getattr(sel, "temporal_fit_quality", None),
                    "selected_capture_date": sel.selected_capture_date.isoformat()
                    if sel.selected_capture_date
                    else None,
                    "temporal_distance_days": sel.temporal_distance_days,
                    "selection_reason": sel.selection_reason,
                    "failure_reason": sel.failure_reason,
                    "canonical_original_url": sel.canonical_original_url,
                    "discovery_decision": "selected"
                    if sel.snapshot_status == "selected"
                    else "rejected",
                    "rejection_reason": sel.failure_reason,
                }
            )
            if sel.snapshot_status == "selected":
                if best_sel is None or (sel.temporal_distance_days or 10**9) < (
                    best_sel.temporal_distance_days or 10**9
                ):
                    best_sel, best_alias, best_attempts = sel, alias, attempts
                if alias.priority == aliases[0].priority and best_alias is alias and alias.priority == 1:
                    break

        if best_sel is None:
            persisted = self._persisted_snapshot_row(firm_id, tp)
            if persisted is not None:
                return persisted
            primary_alias = aliases[0] if aliases else None
            if transport_only and not saw_cdx_response:
                return self._transport_failure_snapshot_row(row, alias=primary_alias, error="all_alias_cdx_transport_failed")
            if aliases:
                return self._transport_failure_snapshot_row(
                    row,
                    alias=primary_alias,
                    error="rescue_alias_no_selected_capture",
                )
            return super()._discover_one_snapshot(row, client, branding_patterns)

        homepage_available = bool(best_sel.homepage_available)
        relevant_subpages = (
            best_alias.candidate_type
            in {
                "about_page",
                "company_section",
                "history_page",
                "family_or_owner_page",
                "management_page",
                "responsibility_or_values_page",
                "archived_subpage_seed",
            }
            if best_alias
            else False
        )
        subpage_only = relevant_subpages and not homepage_available

        note = None
        if row["relative_timepoint"] == "event":
            prec = row.get("target_date_precision", "year")
            note = (
                f"Event target uses {prec}-level precision ({row['target_date']}). "
                f"Event date source: {row.get('event_date_source', '')}"
            )
        if best_alias:
            note = (note or "") + (
                f" | rescue_seed={best_alias.candidate_seed_url}"
                f" source_row={best_alias.source_row_id}"
                f" type={best_alias.candidate_type}"
            )

        out = self._snapshot_row_from_selection(
            row,
            best_sel,
            best_attempts or all_attempts,
            homepage_available,
            relevant_subpages,
            subpage_only,
            note,
        )
        out["rescue_seed_url"] = best_alias.candidate_seed_url if best_alias else None
        out["rescue_source_row_id"] = best_alias.source_row_id if best_alias else None
        out["rescue_candidate_type"] = best_alias.candidate_type if best_alias else None
        out["rescue_domain"] = best_alias.candidate_domain if best_alias else None
        if self.discovery_store and out.get("snapshot_status") == "selected":
            alias_meta = {
                "candidate_seed_url": best_alias.candidate_seed_url if best_alias else None,
                "source_row_id": best_alias.source_row_id if best_alias else None,
                "selected_domain": best_alias.candidate_domain if best_alias else None,
                "archive_evidence": best_alias.archive_evidence if best_alias else None,
                "historical_domain_flag": best_alias.historical_domain_flag if best_alias else False,
                "locale_path_flag": best_alias.locale_path_flag if best_alias else False,
                "migration_flag": best_alias.migration_warning if best_alias else False,
                "entity_change_flag": best_alias.entity_change_warning if best_alias else False,
                "candidate_type": best_alias.candidate_type if best_alias else None,
                "candidate_priority": best_alias.priority if best_alias else None,
            }
            self.discovery_store.persist_selection(
                out,
                alias_meta=alias_meta,
                config_hash=self.config_hash,
                candidate_file_hash=self.candidate_file_hash,
            )
        return out

    @staticmethod
    def _coerce_archive_timestamps(snapshots: pd.DataFrame) -> pd.DataFrame:
        out = snapshots.copy()
        if "archive_timestamp" in out.columns:

            def _ts(val: object) -> object:
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return val
                s = str(val).strip()
                if not s or s.lower() in {"nan", "none", "nat", "<na>"}:
                    return val
                try:
                    return normalize_archive_timestamp(s)
                except ValueError:
                    return s

            out["archive_timestamp"] = out["archive_timestamp"].map(_ts)
        if "wayback_replay_url" in out.columns:
            out["wayback_replay_url"] = out["wayback_replay_url"].map(
                lambda u: sanitize_wayback_replay_url(u) if pd.notna(u) else u
            )
        return out

    def crawl_and_extract(self, firm_ids: list[str] | None = None) -> pd.DataFrame:
        """Same as parent but binds registrable_domain to the rescue seed host."""
        snapshots_path = self.output_dir / "snapshots.csv"
        if not snapshots_path.exists():
            self.discover_snapshots(firm_ids=firm_ids)
        # dtype=str avoids float64 timestamps becoming "...75027.0id_/" in replay URLs.
        snapshots = pd.read_csv(snapshots_path, dtype=str)
        snapshots = self._coerce_archive_timestamps(snapshots)
        if firm_ids:
            snapshots = snapshots[snapshots["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
        firms = pd.read_csv(self.output_dir / "firms.csv", dtype=str)

        from ffb_webminer.pipeline import io as pipeline_io
        from ffb_webminer.pipeline.corpus_outputs import build_crawl_priority_summary
        from ffb_webminer.pipeline.schemas import CRAWL_PRIORITY_SUMMARY_COLUMNS, PAGE_COLUMNS
        from ffb_webminer.quality.checks import check_page
        from ffb_webminer.quality.deduplication import deduplicate_within_observations
        from ffb_webminer.quality.language_inclusion import annotate_language_inclusion
        from ffb_webminer.quality.page_classification import classify_page
        from ffb_webminer.quality.page_validation import validate_page_for_analysis
        from ffb_webminer.rescue.resumable_fetcher import ResumableRescueFetcher
        from ffb_webminer.rescue.transport import TransportPausedError, TransportPolicy

        policy = getattr(self, "transport_policy", None) or TransportPolicy(
            max_attempts_per_request=int(self.config.crawl.retries),
            inter_request_delay_seconds=float(self.config.crawl.throttle_seconds),
            timeout_seconds=float(self.config.crawl.timeout_seconds),
        )
        state_dir = Path(self.config.run.interim_dir) / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        fetcher = ResumableRescueFetcher(
            user_agent=self.config.crawl.user_agent,
            cache_dir=Path(self.config.extract.raw_html_dir),
            state_db=state_dir / "page_fetch_state.sqlite",
            policy=policy,
            resume_command=getattr(self, "resume_command", ""),
        )
        fetcher.print_resume_summary()

        crawled_by_capture: dict[tuple[str, str], list] = {}
        crawl_summaries: list[dict[str, Any]] = []
        selected = snapshots[snapshots["snapshot_status"] == "selected"]
        paused: TransportPausedError | None = None
        try:
            for (firm_id, archive_ts), group in selected.groupby(["firm_id", "archive_timestamp"], dropna=False):
                ts_s = str(archive_ts).strip()
                if not ts_s or ts_s.lower() in {"nan", "none", "nat", "<na>"}:
                    continue
                try:
                    archive_ts_norm = normalize_archive_timestamp(ts_s)
                except ValueError:
                    continue
                snap = group.iloc[0]
                snap_firm_id = str(firm_id)
                firm = firms[firms["firm_id"].astype(str) == snap_firm_id].iloc[0]
                seed = snap.get("canonical_original_url") or firm["website"]
                try:
                    reg_domain = parse_domain(str(seed)).registrable_domain
                except Exception:
                    reg_domain = firm["primary_domain"]
                if (
                    snap.get("rescue_domain")
                    and pd.notna(snap.get("rescue_domain"))
                    and str(snap.get("rescue_domain")).strip()
                ):
                    reg_domain = str(snap["rescue_domain"])
                fetcher.firm_id = snap_firm_id
                fetcher.relative_timepoint = str(snap.get("relative_timepoint") or "")
                crawl = crawl_snapshot(
                    seed_original_url=str(seed),
                    archive_timestamp=archive_ts_norm,
                    registrable_domain=reg_domain,
                    config=self.config.crawl,
                    fetcher=fetcher,
                )
                crawled_by_capture[(snap_firm_id, archive_ts_norm)] = crawl.pages
                crawl_summaries.append(
                    {
                        "firm_id": snap_firm_id,
                        "company": snap["company"],
                        "archive_timestamp": archive_ts_norm,
                        "n_high_priority_pages_discovered": crawl.summary.n_high_priority_pages_discovered,
                        "n_high_priority_pages_fetched": crawl.summary.n_high_priority_pages_fetched,
                        "n_high_priority_pages_missing": crawl.summary.n_high_priority_pages_missing,
                        "n_secondary_pages_fetched": crawl.summary.n_secondary_pages_fetched,
                        "n_broad_pages_fetched": crawl.summary.n_broad_pages_fetched,
                        "n_foreign_pages_deprioritized": crawl.summary.n_foreign_pages_deprioritized,
                        "crawl_limit_reached": crawl.summary.crawl_limit_reached,
                        "unused_reserved_slots": crawl.summary.unused_reserved_slots,
                        "pages_fetched": len(crawl.pages),
                    }
                )
        except TransportPausedError as exc:
            paused = exc
        finally:
            self._last_fetcher_stats = dict(getattr(fetcher, "stats", {}))
            self._last_circuit = getattr(fetcher, "circuit", None)
            try:
                fetcher.close()
            except Exception:
                pass

        if paused is not None:
            # Page cache/state already persisted; re-raise so orchestrator exits resumable.
            raise paused

        all_pages: list[dict[str, Any]] = []
        for _, snap in snapshots.iterrows():
            snap_firm_id = str(snap["firm_id"])
            raw_ts = snap.get("archive_timestamp")
            if snap["snapshot_status"] != "selected" or raw_ts is None or str(raw_ts).strip().lower() in {
                "",
                "nan",
                "none",
                "nat",
                "<na>",
            }:
                all_pages.extend(self._empty_pages_for_snapshot(snap))
                continue
            try:
                archive_ts_norm = normalize_archive_timestamp(raw_ts)
            except ValueError:
                all_pages.extend(self._empty_pages_for_snapshot(snap))
                continue
            firm = firms[firms["firm_id"].astype(str) == snap_firm_id].iloc[0]
            crawl_pages = crawled_by_capture.get((snap_firm_id, archive_ts_norm), [])
            if not crawl_pages:
                all_pages.extend(self._empty_pages_for_snapshot(snap))
                continue
            seed_url = snap.get("canonical_original_url") or firm["website"]
            try:
                check_domain = parse_domain(str(seed_url)).registrable_domain
            except Exception:
                check_domain = firm["primary_domain"]
            if (
                snap.get("rescue_domain")
                and pd.notna(snap.get("rescue_domain"))
                and str(snap.get("rescue_domain")).strip()
            ):
                check_domain = str(snap["rescue_domain"])
            for cp in crawl_pages:
                page_row = self._page_row_from_crawl(snap, firm, cp, fetcher=fetcher)
                page_row = check_page(page_row, check_domain, self.config.quality)
                page_row = validate_page_for_analysis(
                    page_row,
                    check_domain,
                    self.config.quality,
                    max_temporal_distance=self.config.quality.max_temporal_distance_days,
                )
                classification = classify_page(
                    page_row,
                    governance_allowlist=self.config.analysis.governance_url_allowlist,
                )
                page_row.update(
                    {
                        "page_category": classification.page_category,
                        "page_category_reason": classification.page_category_reason,
                        "classification_rule_priority": classification.classification_rule_priority,
                        "classification_rule_id": classification.classification_rule_id,
                        "branding_corpus_eligible": classification.branding_corpus_eligible,
                        "branding_corpus_exclusion_reason": classification.branding_corpus_exclusion_reason,
                        "governance_metadata_eligible": classification.governance_metadata_eligible,
                        "governance_inclusion_reason": classification.governance_inclusion_reason,
                        "governance_rule_id": classification.governance_rule_id,
                        "governance_evidence_type": classification.governance_evidence_type,
                    }
                )
                all_pages.append(page_row)

        preferred_hosts = {}
        for _, firm in firms.iterrows():
            host = parse_domain(str(firm.get("website") or "")).hostname or ""
            preferred_hosts[str(firm["firm_id"])] = host.lstrip("www.")
        for _, snap in snapshots.iterrows():
            if pd.notna(snap.get("canonical_original_url")):
                host = urlparse(str(snap["canonical_original_url"])).hostname or ""
                if host:
                    preferred_hosts[str(snap["firm_id"])] = host.lstrip("www.")

        near_thresh = float(
            getattr(self.config.deduplication, "near_duplicate_threshold", None)
            or self.config.analysis.near_duplicate_threshold
        )
        all_pages = deduplicate_within_observations(
            all_pages,
            preferred_hosts=preferred_hosts,
            near_duplicate_threshold=near_thresh,
        )
        all_pages = annotate_language_inclusion(all_pages, self.config.analysis)

        pages_df = pd.DataFrame(all_pages)
        pages_df = _normalize_pages_df_for_output(pages_df)
        out_path = self.output_dir / "pages.csv"
        if firm_ids and out_path.exists():
            existing = pd.read_csv(out_path, dtype=str)
            existing = _normalize_pages_df_for_output(existing)
            keep = existing[~existing["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
            pages_df = pd.concat([keep, pages_df], ignore_index=True)
            pages_df = _normalize_pages_df_for_output(pages_df)
        else:
            self._assert_pages_match_snapshots(pages_df, pd.read_csv(snapshots_path, dtype=str))
        pipeline_io.write_csv(pages_df, out_path, PAGE_COLUMNS)
        if not pages_df.empty:
            pipeline_io.write_parquet(pages_df, self.output_dir / "pages.parquet")
        pages_df.to_csv(self.state_dir / "pages.csv", index=False)

        crawl_summary_df = build_crawl_priority_summary(snapshots, crawl_summaries)
        crawl_out = self.output_dir / "crawl_priority_summary.csv"
        if firm_ids and crawl_out.exists():
            existing = pd.read_csv(crawl_out)
            keep = existing[~existing["firm_id"].astype(str).isin([str(f) for f in firm_ids])]
            crawl_summary_df = pd.concat([keep, crawl_summary_df], ignore_index=True)
        pipeline_io.write_csv(crawl_summary_df, crawl_out, CRAWL_PRIORITY_SUMMARY_COLUMNS)
        return pages_df


def refresh_snapshot_enrichment(runner: PipelineRunner, snapshots: pd.DataFrame) -> pd.DataFrame:
    firms = pd.read_csv(runner.output_dir / "firms.csv")
    snapshots = enrich_snapshots_dataframe(
        snapshots,
        firms,
        adjacent_min_days=runner.config.snapshot_selection.adjacent_period_min_days,
        override_very_low_usable=runner.config.snapshot_selection.override_very_low_usable,
    )
    snapshots = apply_duplicate_capture_rules(snapshots)
    snapshots = assign_observation_scopes(snapshots)
    return snapshots
