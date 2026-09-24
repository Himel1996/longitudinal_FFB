#!/usr/bin/env python3
"""OFFLINE Phase B cumulative assembly.

Reconstructs full_sample_v1_1_rescue_final from parent + accepted batch
artifacts + persisted rescue artifacts. Does not contact Wayback.
Does not write inside data/releases/full_sample_v1/ or overwrite
data/releases/full_sample_v1_1_rescue/.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.corpus_outputs import (
    build_branding_corpus_observations,
    build_branding_corpus_pages,
    build_governance_metadata_observations,
    build_governance_metadata_pages,
    build_observation_text_summary,
)
from ffb_webminer.pipeline.schemas import (
    BRANDING_CORPUS_OBSERVATION_COLUMNS,
    BRANDING_CORPUS_PAGE_COLUMNS,
    GOVERNANCE_METADATA_OBSERVATION_COLUMNS,
    GOVERNANCE_METADATA_PAGE_COLUMNS,
    OBSERVATION_TEXT_SUMMARY_COLUMNS,
    PAGE_COLUMNS,
    SNAPSHOT_COLUMNS,
)
from ffb_webminer.quality.checks import as_bool
from ffb_webminer.rescue.audit import assert_parent_unchanged, audit_non_targeted_immutability, file_sha256
from ffb_webminer.rescue.discovery_state import DiscoveryStateStore, load_authoritative_rescue_snapshots
from ffb_webminer.rescue.paths import assert_not_parent_release, rescue_layout
from ffb_webminer.rescue.resumable_fetcher import ResumableRescueFetcher
from ffb_webminer.rescue.runner import RescuePipelineRunner, refresh_snapshot_enrichment
from ffb_webminer.rescue.special_cases import entity_change_firm_ids, special_case_notes
from ffb_webminer.rescue.transport import TransportPolicy

# Import helpers from orchestrator without running CLI
sys.path.insert(0, str(ROOT / "scripts"))
from run_full_sample_rescue import (  # noqa: E402
    PRE,
    POST,
    apply_decisions_to_tables,
    build_coverage,
    regenerate_corpora,
)

EXPECTED_PARENT_SHA = "c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27"
FINAL_RELEASE_NAME = "full_sample_v1_1_rescue_final"
RESCUE_FIRMS = [
    "10", "2", "11", "12",
    "14", "15", "16",
    "17", "18", "19",
    "20", "23", "25",
    "21", "22", "24",
    "5", "27", "30",
]
NON_RESCUE_FIRMS = [str(i) for i in range(1, 31) if str(i) not in RESCUE_FIRMS]
BATCH_MAP = {
    "10": ("B_BRAUN_SMOKE", "COMPLETED"),
    "2": ("B01", "COMPLETED_WITH_LIMITATIONS"),
    "11": ("B01", "COMPLETED_WITH_LIMITATIONS"),
    "12": ("B01", "COMPLETED_WITH_LIMITATIONS"),
    "14": ("B02", "COMPLETED"),
    "15": ("B02", "COMPLETED"),
    "16": ("B02", "COMPLETED"),
    "17": ("B03", "COMPLETED_WITH_LIMITATIONS"),
    "18": ("B03", "COMPLETED_WITH_LIMITATIONS"),
    "19": ("B03", "COMPLETED_WITH_LIMITATIONS"),
    "20": ("B04", "COMPLETED"),
    "23": ("B04", "COMPLETED"),
    "25": ("B04", "COMPLETED"),
    "21": ("B05", "COMPLETED_WITH_LIMITATIONS"),
    "22": ("B05", "COMPLETED_WITH_LIMITATIONS"),
    "24": ("B05", "COMPLETED_WITH_LIMITATIONS"),
    "5": ("B06", "COMPLETED_WITH_LIMITATIONS"),
    "27": ("B06", "COMPLETED_WITH_LIMITATIONS"),
    "30": ("B06", "COMPLETED_WITH_LIMITATIONS"),
}
CACHE_FIRMS = ["5", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "27", "30"]


class CacheOnlyRescueFetcher(ResumableRescueFetcher):
    """Fetcher that never contacts the network; cache miss → empty failure."""

    def fetch(self, original_url: str, archive_timestamp: str | None = None, use_cache: bool = True):
        from ffb_webminer.archive.wayback_url import build_replay_url, unwrap_wayback_url
        from ffb_webminer.crawl.fetcher import FetchResult
        from ffb_webminer.rescue.page_cache import STATUS_EXTRACTED, STATUS_FETCHED, page_cache_key
        from ffb_webminer.rescue.timestamps import normalize_archive_timestamp

        if not archive_timestamp:
            return FetchResult(
                requested_url=original_url,
                final_url=original_url,
                original_archived_url=original_url,
                wayback_replay_url=None,
                http_status=None,
                mime_type=None,
                content=b"",
                content_hash=None,
                redirect_chain=None,
                fetch_error="cache_only_no_network",
                raw_html_path=None,
            )
        ts = normalize_archive_timestamp(archive_timestamp)
        original = unwrap_wayback_url(original_url)
        replay = build_replay_url(original, ts)
        key = page_cache_key(original, ts)
        existing = self.store.get(key)
        if use_cache and existing and existing.fetch_status in {STATUS_FETCHED, STATUS_EXTRACTED} and existing.cache_valid:
            cached = self.cache.read_valid(key, expected_hash=existing.content_hash)
            if cached is not None:
                content, _meta = cached
                self.stats["cache_hits"] += 1
                return FetchResult(
                    requested_url=replay,
                    final_url=replay,
                    original_archived_url=original,
                    wayback_replay_url=replay,
                    http_status=existing.http_status or 200,
                    mime_type=existing.mime_type or "text/html",
                    content=content,
                    content_hash=existing.content_hash,
                    redirect_chain=None,
                    fetch_error=None,
                    raw_html_path=str(self.cache.html_path(key)),
                )
        if use_cache:
            cached = self.cache.read_valid(key, expected_hash=existing.content_hash if existing else None)
            if cached is not None:
                content, meta = cached
                self.stats["cache_hits"] += 1
                return FetchResult(
                    requested_url=replay,
                    final_url=replay,
                    original_archived_url=original,
                    wayback_replay_url=replay,
                    http_status=int(meta.get("http_status") or 200),
                    mime_type=str(meta.get("mime_type") or "text/html"),
                    content=content,
                    content_hash=meta.get("content_hash"),
                    redirect_chain=None,
                    fetch_error=None,
                    raw_html_path=str(self.cache.html_path(key)),
                )
        self.stats["resumable_failures"] += 1
        return FetchResult(
            requested_url=replay,
            final_url=replay,
            original_archived_url=original,
            wayback_replay_url=replay,
            http_status=None,
            mime_type=None,
            content=b"",
            content_hash=None,
            redirect_chain=None,
            fetch_error="cache_only_miss",
            raw_html_path=None,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def company_map(parent_data: Path) -> dict[str, str]:
    firms = pd.read_csv(parent_data / "firms.csv", dtype=str)
    return {str(r.firm_id): str(r.company) for _, r in firms.iterrows()}


def load_decision_source(path: Path, source_batch: str) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str)
    d["source_batch"] = source_batch
    d["decision_source_file"] = str(path.relative_to(ROOT))
    d["assembly_timestamp"] = utc_now()
    d["final_decision_provenance"] = f"accepted_{source_batch}"
    return d


def build_inventory(layout: dict[str, Path], companies: dict[str, str]) -> pd.DataFrame:
    interim = layout["interim"]
    sources = interim / "assembly_sources"
    rows = []
    decision_files = {
        "B_BRAUN_SMOKE": sources / "bbraun_smoke" / "rescue_comparison_decisions.csv",
        "B01": sources / "b01_batch1" / "rescue_comparison_decisions.csv",
        "B02": interim / "rescue_comparison_decisions_B02.csv",
        "B03": interim / "rescue_comparison_decisions_B03.csv",
        "B04": interim / "rescue_comparison_decisions_B04.csv",
        "B05": interim / "rescue_comparison_decisions_B05.csv",
        "B06": interim / "rescue_comparison_decisions_B06.csv",
    }
    page_sources = {
        "B_BRAUN_SMOKE": sources / "bbraun_smoke" / "pages.csv",
        "B01": sources / "b01_batch1" / "pages.csv",
    }
    obs_sources = {
        "B_BRAUN_SMOKE": sources / "bbraun_smoke" / "observation_text_summary.csv",
        "B01": sources / "b01_batch1" / "observation_text_summary.csv",
    }
    con = sqlite3.connect(interim / "state" / "page_fetch_state.sqlite")
    fetch_firms = {
        str(r[0]): int(r[1])
        for r in con.execute(
            "SELECT firm_id, COUNT(*) FROM page_fetch_state WHERE fetch_status='FETCHED' GROUP BY firm_id"
        )
    }
    con.close()
    dcon = sqlite3.connect(interim / "state" / "rescue_discovery_state.sqlite")
    disc_firms = {
        str(r[0]): int(r[1])
        for r in dcon.execute(
            "SELECT firm_id, COUNT(*) FROM rescue_discovery_selection WHERE selected_snapshot_status='selected' GROUP BY firm_id"
        )
    }
    dcon.close()

    for fid in RESCUE_FIRMS:
        batch, status = BATCH_MAP[fid]
        dec_path = decision_files[batch]
        dec = pd.read_csv(dec_path, dtype=str) if dec_path.exists() else pd.DataFrame()
        if len(dec) and "firm_id" in dec.columns:
            dec = dec[dec.firm_id.astype(str) == fid]
        counts = dec["rescue_decision"].value_counts().to_dict() if len(dec) else {}
        pages_ok = False
        obs_ok = False
        notes = []
        if batch in page_sources and page_sources[batch].exists():
            p = pd.read_csv(page_sources[batch], dtype=str, low_memory=False)
            pages_ok = (p.firm_id.astype(str) == fid).any()
        if batch in obs_sources and obs_sources[batch].exists():
            o = pd.read_csv(obs_sources[batch], dtype=str)
            obs_ok = (o.firm_id.astype(str) == fid).any()
        if fid in CACHE_FIRMS:
            pages_ok = pages_ok or fetch_firms.get(fid, 0) > 0
            obs_ok = obs_ok or disc_firms.get(fid, 0) > 0
            notes.append(f"cache_fetched={fetch_firms.get(fid, 0)}")
            notes.append(f"discovery_selected={disc_firms.get(fid, 0)}")
        if batch == "B_BRAUN_SMOKE":
            notes.append("from_git:6b28230")
        if batch == "B01":
            notes.append("from_git:79d2df9")
        complete = bool(len(dec)) and pages_ok and (obs_ok or pages_ok)
        rows.append(
            {
                "firm_id": fid,
                "company": companies.get(fid, ""),
                "source_batch": batch,
                "batch_status": status,
                "decision_artifact": str(dec_path.relative_to(ROOT)) if dec_path.exists() else "MISSING",
                "rescue_observation_artifact": (
                    str(obs_sources[batch].relative_to(ROOT))
                    if batch in obs_sources and obs_sources[batch].exists()
                    else ("cache+discovery_reextract" if fid in CACHE_FIRMS else "MISSING")
                ),
                "rescue_pages_available": "TRUE" if pages_ok else "FALSE",
                "accepted_decision_count": int(len(dec)),
                "replace_count": int(counts.get("replace_with_rescue", 0)),
                "sensitivity_alt_count": int(counts.get("add_as_sensitivity_alternative", 0)),
                "retain_count": int(counts.get("retain_original", 0)),
                "reject_count": int(
                    counts.get("rejected_insufficient_text", 0)
                    + counts.get("rejected_wrong_language", 0)
                    + counts.get("rejected_outside_tolerance", 0)
                ),
                "manual_review_count": int(counts.get("manual_review_required", 0)),
                "remain_unavailable_count": int(counts.get("remain_unavailable", 0)),
                "assembly_source_complete": "TRUE" if complete else "FALSE",
                "notes": ";".join(notes),
            }
        )
    for fid in NON_RESCUE_FIRMS:
        rows.append(
            {
                "firm_id": fid,
                "company": companies.get(fid, ""),
                "source_batch": "PARENT_ONLY",
                "batch_status": "N/A",
                "decision_artifact": "parent",
                "rescue_observation_artifact": "parent",
                "rescue_pages_available": "N/A",
                "accepted_decision_count": 0,
                "replace_count": 0,
                "sensitivity_alt_count": 0,
                "retain_count": 0,
                "reject_count": 0,
                "manual_review_count": 0,
                "remain_unavailable_count": 0,
                "assembly_source_complete": "TRUE",
                "notes": "non_rescue_parent_immutable",
            }
        )
    return pd.DataFrame(rows).sort_values(by="firm_id", key=lambda s: s.astype(int))


def build_cumulative_decisions(layout: dict[str, Path]) -> pd.DataFrame:
    interim = layout["interim"]
    sources = interim / "assembly_sources"
    parts = [
        load_decision_source(sources / "bbraun_smoke" / "rescue_comparison_decisions.csv", "B_BRAUN_SMOKE"),
        load_decision_source(sources / "b01_batch1" / "rescue_comparison_decisions.csv", "B01"),
        load_decision_source(interim / "rescue_comparison_decisions_B02.csv", "B02"),
        load_decision_source(interim / "rescue_comparison_decisions_B03.csv", "B03"),
        load_decision_source(interim / "rescue_comparison_decisions_B04.csv", "B04"),
        load_decision_source(interim / "rescue_comparison_decisions_B05.csv", "B05"),
        load_decision_source(interim / "rescue_comparison_decisions_B06.csv", "B06"),
    ]
    all_d = pd.concat(parts, ignore_index=True)
    all_d["firm_id"] = all_d["firm_id"].astype(str)
    all_d["relative_timepoint"] = all_d["relative_timepoint"].astype(str)
    # one authoritative row per firm × timepoint (batches are disjoint firms)
    dup = all_d.duplicated(subset=["firm_id", "relative_timepoint"], keep=False)
    if dup.any():
        raise RuntimeError(
            f"duplicate firm×timepoint decisions: {all_d.loc[dup, ['firm_id','relative_timepoint','source_batch']].to_dict('records')}"
        )
    missing = set(RESCUE_FIRMS) - set(all_d["firm_id"].unique())
    if missing:
        raise RuntimeError(f"missing decision firms: {sorted(missing, key=int)}")
    all_d["_fid"] = all_d["firm_id"].astype(int)
    all_d = all_d.sort_values(["_fid", "relative_timepoint"]).drop(columns=["_fid"])
    return all_d


def offline_reextract_cache_firms(layout: dict[str, Path], firm_ids: list[str], work_out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Re-extract rescue pages/snapshots for firms with local HTML cache (no network)."""
    work_out.mkdir(parents=True, exist_ok=True)
    # seed output with parent firms/config paths via pipeline config
    cfg_path = layout["interim"] / "pipeline_config.yaml"
    if not cfg_path.exists():
        # build minimal from rescue yaml merge pattern used by orchestrator
        full = yaml.safe_load(layout["full_sample_config"].read_text())
        rescue = yaml.safe_load(layout["rescue_config"].read_text())
        # Use existing processed pipeline_config if present
        alt = layout["processed"] / "pipeline_config.yaml"
        if alt.exists():
            cfg_path = alt
        else:
            raise FileNotFoundError("pipeline_config.yaml missing for rescue runner")

    # Copy parent firms into work_out
    shutil.copy2(layout["parent_data"] / "firms.csv", work_out / "firms.csv")

    store = DiscoveryStateStore(layout["interim"] / "state" / "rescue_discovery_state.sqlite")
    try:
        snaps = load_authoritative_rescue_snapshots(layout["interim"], store, firm_ids=firm_ids)
    finally:
        store.close()
    if snaps.empty:
        raise RuntimeError(f"no authoritative rescue snapshots for {firm_ids}")

    # Enrich like extract stage
    pipe_cfg = PipelineConfig.from_yaml(cfg_path).resolve_paths(ROOT)
    # Point runner at work_out and interim html/state
    pipe_cfg.run.output_dir = str(work_out)
    pipe_cfg.run.interim_dir = str(layout["interim"])
    pipe_cfg.extract.raw_html_dir = str(layout["interim"] / "html")
    runner = RescuePipelineRunner(pipe_cfg)
    runner.output_dir = work_out
    runner.state_dir = layout["interim"]
    runner.transport_policy = TransportPolicy.from_mapping(
        yaml.safe_load(layout["rescue_config"].read_text()).get("transport") or {}
    )
    snaps = refresh_snapshot_enrichment(runner, snaps)
    for col in SNAPSHOT_COLUMNS:
        if col not in snaps.columns:
            snaps[col] = None
    snaps.to_csv(work_out / "snapshots.csv", index=False)

    # Patch fetcher class so crawl_and_extract never contacts Wayback
    import ffb_webminer.rescue.resumable_fetcher as rf_mod

    original = rf_mod.ResumableRescueFetcher
    rf_mod.ResumableRescueFetcher = CacheOnlyRescueFetcher
    try:
        pages = runner.crawl_and_extract(firm_ids=firm_ids)
    finally:
        rf_mod.ResumableRescueFetcher = original

    snaps = pd.read_csv(work_out / "snapshots.csv", dtype=str)
    pages = pd.read_csv(work_out / "pages.csv", dtype=str, low_memory=False)
    pages = pages[pages["firm_id"].astype(str).isin(firm_ids)].copy()
    snaps = snaps[snaps["firm_id"].astype(str).isin(firm_ids)].copy()
    return snaps, pages


def merge_rescue_artifacts(
    *,
    layout: dict[str, Path],
    cache_snaps: pd.DataFrame,
    cache_pages: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sources = layout["interim"] / "assembly_sources"
    bbraun_snaps = pd.read_csv(sources / "bbraun_smoke" / "snapshots.csv", dtype=str)
    bbraun_snaps = bbraun_snaps[bbraun_snaps.firm_id.astype(str) == "10"].copy()
    bbraun_pages = pd.read_csv(sources / "bbraun_smoke" / "pages.csv", dtype=str, low_memory=False)
    bbraun_pages = bbraun_pages[bbraun_pages.firm_id.astype(str) == "10"].copy()

    b01_obs_snaps = pd.read_csv(sources / "b01_batch1" / "snapshots_targeted.csv", dtype=str)
    b01_snaps = b01_obs_snaps[b01_obs_snaps.firm_id.astype(str).isin(["2", "11", "12"])].copy()
    b01_pages = pd.read_csv(sources / "b01_batch1" / "pages.csv", dtype=str, low_memory=False)

    # Prefer live B06 interim pages when present (exact accepted extract)
    live_pages = layout["interim"] / "rescue_pages.csv"
    live_snaps = layout["interim"] / "rescue_snapshots.csv"
    b06_pages = pd.DataFrame()
    b06_snaps = pd.DataFrame()
    if live_pages.exists():
        lp = pd.read_csv(live_pages, dtype=str, low_memory=False)
        b06_pages = lp[lp.firm_id.astype(str).isin(["5", "27", "30"])].copy()
    if live_snaps.exists():
        ls = pd.read_csv(live_snaps, dtype=str)
        b06_snaps = ls[ls.firm_id.astype(str).isin(["5", "27", "30"])].copy()

    # cache_snaps/pages for B02-B05 (+ fallback B06 if live missing)
    cache_only_firms = ["14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25"]
    if b06_pages.empty:
        cache_only_firms += ["5", "27", "30"]
    c_snaps = cache_snaps[cache_snaps.firm_id.astype(str).isin(cache_only_firms)].copy()
    c_pages = cache_pages[cache_pages.firm_id.astype(str).isin(cache_only_firms)].copy()

    snaps = pd.concat([bbraun_snaps, b01_snaps, c_snaps, b06_snaps], ignore_index=True)
    pages = pd.concat([bbraun_pages, b01_pages, c_pages, b06_pages], ignore_index=True)
    # drop duplicate firm×timepoint snap rows preferring first (sources are disjoint firms)
    snaps = snaps.drop_duplicates(subset=["firm_id", "relative_timepoint"], keep="first")
    return snaps, pages


def assemble_tables(
    layout: dict[str, Path],
    decisions: pd.DataFrame,
    rescue_snaps: pd.DataFrame,
    rescue_pages: pd.DataFrame,
    work_out: Path,
) -> dict[str, pd.DataFrame]:
    parent_snaps = pd.read_csv(layout["parent_data"] / "full_sample_snapshots.csv", dtype=str)
    parent_pages = pd.read_csv(layout["parent_data"] / "full_sample_pages.csv", dtype=str, low_memory=False)
    final_snaps, final_pages = apply_decisions_to_tables(
        parent_snaps, parent_pages, rescue_snaps, rescue_pages, decisions
    )
    work_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(layout["parent_data"] / "firms.csv", work_out / "firms.csv")
    pipeline_io.write_csv(final_snaps, work_out / "snapshots.csv", SNAPSHOT_COLUMNS)
    pipeline_io.write_csv(final_pages, work_out / "pages.csv", PAGE_COLUMNS)

    # regenerate corpora using a lightweight runner stub
    class _R:
        def __init__(self, output_dir: Path, config: PipelineConfig):
            self.output_dir = output_dir
            self.config = config

    cfg_path = (
        layout["interim"] / "pipeline_config.yaml"
        if (layout["interim"] / "pipeline_config.yaml").exists()
        else layout["processed"] / "pipeline_config.yaml"
    )
    cfg = PipelineConfig.from_yaml(cfg_path).resolve_paths(ROOT)
    corpora = regenerate_corpora(_R(work_out, cfg))
    firms = pd.read_csv(work_out / "firms.csv", dtype=str)
    coverage = build_coverage(
        firms, corpora["obs"], corpora["primary"], corpora["sens_de"], decisions, set(RESCUE_FIRMS)
    )
    # enrich coverage with source_batch
    coverage["source_batch"] = coverage["firm_id"].map(lambda x: BATCH_MAP.get(str(x), ("PARENT_ONLY",))[0])
    # migration flags from decisions if present
    if "forced_sensitivity_treatment" in decisions.columns:
        mig = (
            decisions.assign(firm_id=decisions.firm_id.astype(str))
            .groupby("firm_id")["forced_sensitivity_treatment"]
            .apply(lambda s: "TRUE" if s.astype(str).str.lower().isin(["true", "1"]).any() else "FALSE")
        )
        coverage["site_migration_flag"] = coverage["firm_id"].map(lambda x: mig.get(str(x), "FALSE"))
    coverage["rescue_targeted"] = coverage["firm_id"].astype(str).isin(RESCUE_FIRMS).map({True: "TRUE", False: "FALSE"})
    coverage.to_csv(work_out / "firm_longitudinal_coverage.csv", index=False)
    corpora["coverage"] = coverage
    corpora["snapshots"] = final_snaps
    corpora["pages"] = final_pages
    return corpora


def write_final_release(layout: dict[str, Path], work_out: Path, decisions: pd.DataFrame, corpora: dict[str, pd.DataFrame]) -> Path:
    release_dir = ROOT / "data" / "releases" / FINAL_RELEASE_NAME
    assert_not_parent_release(release_dir, project_root=ROOT)
    if release_dir.exists():
        shutil.rmtree(release_dir)
    data_dir = release_dir / "data"
    reports_dir = release_dir / "reports"
    cfg_dir = release_dir / "config"
    data_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    cfg_dir.mkdir(parents=True)

    mapping = {
        "snapshots.csv": "full_sample_snapshots.csv",
        "pages.csv": "full_sample_pages.csv",
        "observation_text_summary.csv": "full_sample_observation_text_summary.csv",
        "branding_corpus_pages_all_languages.csv": "full_sample_branding_corpus_pages_all_languages.csv",
        "branding_corpus_pages_de.csv": "full_sample_branding_corpus_pages_de.csv",
        "branding_corpus_observations_primary.csv": "full_sample_branding_corpus_observations_primary.csv",
        "branding_corpus_observations_sensitivity.csv": "full_sample_branding_corpus_observations_sensitivity.csv",
        "branding_corpus_observations_sensitivity_all_languages.csv": "full_sample_branding_corpus_observations_sensitivity_all_languages.csv",
        "branding_corpus_observations_sensitivity_de.csv": "full_sample_branding_corpus_observations_sensitivity_de.csv",
        "governance_metadata_pages.csv": "full_sample_governance_metadata_pages.csv",
        "governance_metadata_observations.csv": "full_sample_governance_metadata_observations.csv",
        "firm_longitudinal_coverage.csv": "firm_longitudinal_coverage.csv",
        "firms.csv": "firms.csv",
    }
    for src, dst in mapping.items():
        sp = work_out / src
        if sp.exists():
            shutil.copy2(sp, data_dir / dst)
    decisions.to_csv(data_dir / "rescue_comparison_decisions_FINAL.csv", index=False)
    decisions.to_csv(data_dir / "rescue_comparison_decisions.csv", index=False)
    shutil.copy2(layout["candidate_csv"], data_dir / "full_sample_url_rescue_candidates.csv")
    shutil.copy2(layout["rescue_config"], cfg_dir / "full_sample_rescue.yaml")
    shutil.copy2(layout["full_sample_config"], cfg_dir / "full_sample.yaml")
    parent_check = assert_parent_unchanged(layout["parent_data"], EXPECTED_PARENT_SHA)
    manifest = {
        "parent_release": "full_sample_v1",
        "release_name": FINAL_RELEASE_NAME,
        "run_type": "cumulative_rescue_final_assembly",
        "firms_targeted": RESCUE_FIRMS,
        "parent_primary_sha256": parent_check["parent_primary_sha256"],
        "creation_timestamp": utc_now(),
        "network_used": False,
        "source_batches": ["B_BRAUN_SMOKE", "B01", "B02", "B03", "B04", "B05", "B06"],
        "counts": {
            "observations": int(len(corpora["obs"])),
            "primary": int(len(corpora["primary"])),
            "sensitivity_all": int(len(corpora["sens_all"])),
            "sensitivity_de": int(len(corpora["sens_de"])),
            "pages": int(len(corpora["pages"])),
            "decisions": int(len(decisions)),
        },
        "corpus_definitions": {
            "primary": "German only",
            "sensitivity_all": "all languages",
            "sensitivity_de": "German only",
        },
    }
    (data_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readme = """# full_sample_v1_1_rescue_final

Cumulative Phase B rescue release assembled offline from frozen parent
`full_sample_v1` plus accepted B. Braun + B01–B06 rescue decisions and
persisted rescue artifacts.

## Corpus definitions

- `full_sample_branding_corpus_observations_primary.csv` — German PRIMARY only
- `full_sample_branding_corpus_observations_sensitivity_all_languages.csv` — ALL languages sensitivity
- `full_sample_branding_corpus_observations_sensitivity_de.csv` — German-only sensitivity
- `full_sample_branding_corpus_pages_all_languages.csv` — ALL language branding pages
- `full_sample_branding_corpus_pages_de.csv` — German-only branding pages

Parent release was not modified. No Wayback network access during assembly.
"""
    (release_dir / "README.md").write_text(readme, encoding="utf-8")
    return release_dir


def main() -> int:
    layout = rescue_layout(ROOT)
    parent_check = assert_parent_unchanged(layout["parent_data"], EXPECTED_PARENT_SHA)
    print(json.dumps({"parent_sha": parent_check["parent_primary_sha256"], "ok": True}, indent=2))

    companies = company_map(layout["parent_data"])
    inventory = build_inventory(layout, companies)
    inv_path = layout["interim"] / "final_assembly_inventory.csv"
    inventory.to_csv(inv_path, index=False)
    print(f"inventory → {inv_path}")
    incomplete = inventory[
        (inventory["source_batch"] != "PARENT_ONLY") & (inventory["assembly_source_complete"] != "TRUE")
    ]
    if len(incomplete):
        print("INCOMPLETE SOURCES:")
        print(incomplete.to_string(index=False))
        print("STOP: cannot assemble unambiguously")
        return 2

    decisions = build_cumulative_decisions(layout)
    dec_path = layout["interim"] / "rescue_comparison_decisions_FINAL.csv"
    decisions.to_csv(dec_path, index=False)
    print(f"cumulative decisions → {dec_path} n={len(decisions)} firms={sorted(decisions.firm_id.unique(), key=int)}")

    # B. Braun token check
    bb = decisions[decisions.firm_id == "10"]
    assert len(bb) == 5 and (bb.rescue_decision == "replace_with_rescue").all()
    tok = bb["rescue_branding_tokens_de"].astype(float).sum()
    print(f"B.Braun decisions OK tokens_de_sum={tok}")
    if abs(tok - 18028) > 1:
        raise RuntimeError(f"B.Braun token sum mismatch: {tok} != 18028")

    work = layout["interim"] / "final_assembly_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print("Offline cache re-extract for B02–B06 firms...")
    cache_snaps, cache_pages = offline_reextract_cache_firms(layout, CACHE_FIRMS, work / "cache_extract")
    print(f"cache extract snaps={len(cache_snaps)} pages={len(cache_pages)} firms={sorted(cache_pages.firm_id.unique(), key=lambda x: int(x))}")

    rescue_snaps, rescue_pages = merge_rescue_artifacts(
        layout=layout, cache_snaps=cache_snaps, cache_pages=cache_pages
    )
    print(f"merged rescue snaps firms={sorted(rescue_snaps.firm_id.astype(str).unique(), key=int)}")
    print(f"merged rescue pages firms={sorted(rescue_pages.firm_id.astype(str).unique(), key=int)}")

    # Ensure every replace_with_rescue has rescue pages/snaps
    for _, d in decisions[decisions.rescue_decision == "replace_with_rescue"].iterrows():
        fid, tp = str(d.firm_id), str(d.relative_timepoint)
        if rescue_snaps[(rescue_snaps.firm_id.astype(str) == fid) & (rescue_snaps.relative_timepoint == tp)].empty:
            raise RuntimeError(f"missing rescue snapshot for replace {fid}/{tp}")
        if rescue_pages[(rescue_pages.firm_id.astype(str) == fid) & (rescue_pages.relative_timepoint == tp)].empty:
            raise RuntimeError(f"missing rescue pages for replace {fid}/{tp}")

    final_out = work / "final_output"
    corpora = assemble_tables(layout, decisions, rescue_snaps, rescue_pages, final_out)
    release_dir = write_final_release(layout, final_out, decisions, corpora)
    print(f"final release → {release_dir}")

    # Non-targeted regression
    parent_obs = pd.read_csv(layout["parent_data"] / "full_sample_observation_text_summary.csv", dtype=str)
    audit_non_targeted_immutability(
        parent_obs=parent_obs, rescue_obs=corpora["obs"], targeted_firm_ids=set(RESCUE_FIRMS)
    )
    print("non-targeted immutability PASS")

    # Persist impact stub path for follow-on report writer
    (layout["interim"] / "final_assembly_meta.json").write_text(
        json.dumps(
            {
                "release": str(release_dir),
                "parent_sha": parent_check["parent_primary_sha256"],
                "n_decisions": len(decisions),
                "n_primary": len(corpora["primary"]),
                "n_sens_de": len(corpora["sens_de"]),
                "timestamp": utc_now(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
