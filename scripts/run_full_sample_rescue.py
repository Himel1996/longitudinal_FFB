#!/usr/bin/env python3
"""Phase B: targeted German-language rescue orchestrator.

Preparation/execution entry point. Does not alter validated extraction rules.
Never writes inside data/releases/full_sample_v1/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.extract.domain import parse_domain
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
from ffb_webminer.rescue.audit import (
    assert_parent_unchanged,
    audit_non_targeted_immutability,
    file_sha256,
    guard_release_destination,
)
from ffb_webminer.rescue.candidates import (
    build_alias_map,
    candidates_to_dataframe,
    load_raw_candidates,
    normalize_candidates,
    write_validation_report,
)
from ffb_webminer.rescue.compare import decide_rescue
from ffb_webminer.rescue.manual_validation import build_manual_validation_sample
from ffb_webminer.rescue.paths import assert_not_parent_release, ensure_workspace_dirs, rescue_layout
from ffb_webminer.rescue.release import assemble_rescue_release
from ffb_webminer.rescue.reports import write_candidate_validation_report, write_report_templates
from ffb_webminer.rescue.runner import RescuePipelineRunner
from ffb_webminer.rescue.special_cases import (
    entity_change_firm_ids,
    force_sensitivity_firm_ids,
    special_case_notes,
)
from ffb_webminer.rescue.transport import DEFAULT_TRANSPORT_POLICY, TRANSPORT_FAILURE_RESUMABLE

RESCUE_EXTRA_COLS = [
    "rescue_seed_url",
    "rescue_source_row_id",
    "rescue_candidate_type",
    "rescue_domain",
]
PRE = frozenset({"pre_pre_event", "pre_event"})
POST = frozenset({"post_event", "post_post_event"})
STAGES = (
    "validate",
    "preflight",
    "discover",
    "crawl",
    "extract",
    "compare",
    "report",
    "acceptance",
    "full",
)
RESUME_FROM = ("discover", "crawl", "extract", "compare", "report", "acceptance")


def _load_nonready(parent_data: Path) -> set[str]:
    cov = pd.read_csv(parent_data / "firm_longitudinal_coverage.csv", dtype=str)
    col = "german_longitudinal_ready"
    ready = set(
        cov.loc[cov[col].astype(str).str.upper().isin(["TRUE", "1", "YES"]), "firm_id"].astype(str)
    )
    return set(cov["firm_id"].astype(str)) - ready


def _scalar_bool(val: Any) -> bool:
    if isinstance(val, pd.Series):
        val = val.iloc[0] if len(val) else False
    return as_bool(val)


def _write_pipeline_yaml(rescue_doc: dict[str, Any], interim: Path, transport: dict[str, Any]) -> Path:
    """Build an isolated pipeline YAML from full_sample.yaml + path/transport overrides."""
    base = yaml.safe_load((ROOT / "config" / "full_sample.yaml").read_text(encoding="utf-8"))
    # Prefer explicit pipeline block if present, else inherit full_sample entirely.
    pipeline = dict(rescue_doc.get("pipeline") or base)
    # Force isolation paths regardless of embedded pipeline block.
    pipeline.setdefault("run", {})
    pipeline["run"]["output_dir"] = "data/processed/full_sample_rescue/output"
    pipeline["run"]["interim_dir"] = "data/interim/full_sample_rescue"
    pipeline["run"]["reports_dir"] = "reports/full_sample_rescue"
    pipeline["run"]["run_id"] = None
    pipeline.setdefault("extract", {})
    pipeline["extract"]["raw_html_dir"] = "data/interim/full_sample_rescue/html"
    pipeline.setdefault("archive", {})
    pipeline["archive"]["cache_dir"] = "data/interim/cdx"
    pipeline.setdefault("visual", {})
    pipeline["visual"]["enabled"] = False
    pipeline["visual"]["screenshot_dir"] = "data/interim/full_sample_rescue/screenshots"
    crawl = dict(pipeline.get("crawl") or {})
    crawl["retries"] = int(transport.get("retries", crawl.get("retries", 5)))
    crawl["throttle_seconds"] = float(transport.get("throttle_seconds", crawl.get("throttle_seconds", 2.5)))
    crawl["timeout_seconds"] = int(transport.get("timeout_seconds", crawl.get("timeout_seconds", 45)))
    pipeline["crawl"] = crawl
    path = interim / "pipeline_config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(pipeline, sort_keys=False), encoding="utf-8")
    return path


def _refresh_rescue_config(
    layout: dict[str, Path],
    targeted: list[str],
    timepoints: list[str],
    alias_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    doc = yaml.safe_load(layout["rescue_config"].read_text(encoding="utf-8"))
    doc["targeted_firms"] = targeted
    doc["targeted_timepoints"] = timepoints
    doc["seed_aliases"] = alias_rows
    # keep full_sample.yaml untouched; only rewrite rescue config
    layout["rescue_config"].write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return doc


def _obs_lookup(df: pd.DataFrame, firm_id: str, tp: str) -> pd.Series | None:
    m = df[(df["firm_id"].astype(str) == str(firm_id)) & (df["relative_timepoint"].astype(str) == str(tp))]
    return m.iloc[0] if len(m) else None


def _annotate_rescue_domains(snaps: pd.DataFrame, discovery_log: pd.DataFrame | None = None) -> pd.DataFrame:
    out = snaps.copy()
    for col in RESCUE_EXTRA_COLS:
        if col not in out.columns:
            out[col] = None
    log_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if discovery_log is not None and len(discovery_log):
        for _, row in discovery_log.iterrows():
            if str(row.get("snapshot_status") or row.get("discovery_decision") or "") not in {
                "selected",
            }:
                continue
            key = (str(row["firm_id"]), str(row.get("relative_timepoint")))
            log_lookup.setdefault(key, row.to_dict())
    for idx, row in out.iterrows():
        key = (str(row["firm_id"]), str(row["relative_timepoint"]))
        seed = row.get("rescue_seed_url") or row.get("canonical_original_url")
        if key in log_lookup:
            meta = log_lookup[key]
            if not seed or (isinstance(seed, float) and pd.isna(seed)):
                seed = meta.get("canonical_original_url") or meta.get("candidate_seed_url")
            out.at[idx, "rescue_seed_url"] = meta.get("candidate_seed_url") or seed
            out.at[idx, "rescue_source_row_id"] = meta.get("source_row_id")
        if seed and not (isinstance(seed, float) and pd.isna(seed)):
            try:
                out.at[idx, "rescue_domain"] = parse_domain(str(seed)).registrable_domain
            except Exception:
                pass
    return out


def _mask_bool(series: pd.Series) -> pd.Series:
    if series is None or len(series) == 0:
        return pd.Series(dtype=bool)
    return series.map(as_bool)


def build_coverage(firms, obs, primary, sens_de, decisions, targeted) -> pd.DataFrame:
    rows = []
    for _, firm in firms.iterrows():
        fid = str(firm["firm_id"])
        o = obs[obs["firm_id"].astype(str) == fid]
        pre = o[o["relative_timepoint"].isin(PRE)]
        post = o[o["relative_timepoint"].isin(POST)]
        pre_ge = pre[_mask_bool(pre["german_text_analysis_eligible"])] if len(pre) else pre
        post_ge = post[_mask_bool(post["german_text_analysis_eligible"])] if len(post) else post
        prim = primary[primary["firm_id"].astype(str) == fid] if len(primary) else primary
        sde = sens_de[sens_de["firm_id"].astype(str) == fid] if len(sens_de) else sens_de
        pre_prim = prim[prim["relative_timepoint"].isin(PRE)] if len(prim) else prim
        post_prim = prim[prim["relative_timepoint"].isin(POST)] if len(prim) else prim
        pre_sens = sde[sde["relative_timepoint"].isin(PRE)] if len(sde) else sde
        post_sens = sde[sde["relative_timepoint"].isin(POST)] if len(sde) else sde
        ready_primary = len(pre_prim) > 0 and len(post_prim) > 0
        ready_ext = len(pre_ge) > 0 and len(post_ge) > 0
        firm_decs = decisions[decisions["firm_id"].astype(str) == fid] if len(decisions) else pd.DataFrame()
        improved = bool(
            len(firm_decs)
            and firm_decs["rescue_decision"].isin(["replace_with_rescue", "add_as_sensitivity_alternative"]).any()
        )
        notes = []
        if not ready_ext:
            if len(pre_ge) == 0:
                notes.append("missing_pre")
            if len(post_ge) == 0:
                notes.append("missing_post")
        if fid in targeted:
            notes.append("rescue_attempted")
        notes.extend(special_case_notes(fid))
        rows.append(
            {
                "firm_id": fid,
                "company": firm.get("company"),
                "event_date": firm.get("event_date_final") or firm.get("event_year"),
                "event_year": firm.get("event_year"),
                "event_type": firm.get("event_type"),
                "n_pre_event_observations_total": int(len(pre)),
                "n_post_event_observations_total": int(len(post)),
                "n_pre_event_german_eligible": int(len(pre_ge)),
                "n_post_event_german_eligible": int(len(post_ge)),
                "n_pre_event_german_primary": int(len(pre_prim)),
                "n_post_event_german_primary": int(len(post_prim)),
                "n_pre_event_german_sensitivity": int(len(pre_sens)),
                "n_post_event_german_sensitivity": int(len(post_sens)),
                "german_longitudinal_ready_primary": "TRUE" if ready_primary else "FALSE",
                "german_longitudinal_ready_extended": "TRUE" if ready_ext else "FALSE",
                "rescue_attempted": "TRUE" if fid in targeted else "FALSE",
                "rescue_improved_coverage": "TRUE" if improved else "FALSE",
                "historical_domain_used": "FALSE",
                "site_migration_flag": "FALSE",
                "entity_change_flag": "TRUE" if fid in entity_change_firm_ids() else "FALSE",
                "remaining_coverage_gap": "none" if ready_ext else ";".join(notes) or "gap",
                "coverage_notes": ";".join(notes) if notes else ("ready_primary" if ready_primary else "ready_extended"),
            }
        )
    return pd.DataFrame(rows)


def regenerate_corpora(runner: RescuePipelineRunner) -> dict[str, pd.DataFrame]:
    out = runner.output_dir
    snapshots = pd.read_csv(out / "snapshots.csv", dtype=str)
    pages = pd.read_csv(out / "pages.csv", dtype=str)
    gov_pages = build_governance_metadata_pages(pages)
    gov_obs = build_governance_metadata_observations(snapshots, gov_pages)
    obs = build_observation_text_summary(snapshots, pages, gov_obs, runner.config.analysis)
    bp_all = build_branding_corpus_pages(pages, obs, language_scope="all")
    bp_de = build_branding_corpus_pages(pages, obs, language_scope="de", require_german_observation=True)
    primary = build_branding_corpus_observations(
        obs, bp_de, primary_only=True, corpus_language_scope="de", use_german_eligibility=True
    )
    sens_all = build_branding_corpus_observations(obs, bp_all, primary_only=False, corpus_language_scope="all")
    sens_de = build_branding_corpus_observations(
        obs, bp_de, primary_only=False, corpus_language_scope="de", use_german_eligibility=True
    )
    pipeline_io.write_csv(obs, out / "observation_text_summary.csv", OBSERVATION_TEXT_SUMMARY_COLUMNS)
    pipeline_io.write_csv(bp_all, out / "branding_corpus_pages_all_languages.csv", BRANDING_CORPUS_PAGE_COLUMNS)
    pipeline_io.write_csv(bp_de, out / "branding_corpus_pages_de.csv", BRANDING_CORPUS_PAGE_COLUMNS)
    pipeline_io.write_csv(primary, out / "branding_corpus_observations_primary.csv", BRANDING_CORPUS_OBSERVATION_COLUMNS)
    # Legacy alias: sensitivity.csv == all-language sensitivity corpus
    pipeline_io.write_csv(sens_all, out / "branding_corpus_observations_sensitivity.csv", BRANDING_CORPUS_OBSERVATION_COLUMNS)
    pipeline_io.write_csv(
        sens_all, out / "branding_corpus_observations_sensitivity_all_languages.csv", BRANDING_CORPUS_OBSERVATION_COLUMNS
    )
    pipeline_io.write_csv(sens_de, out / "branding_corpus_observations_sensitivity_de.csv", BRANDING_CORPUS_OBSERVATION_COLUMNS)
    pipeline_io.write_csv(gov_pages, out / "governance_metadata_pages.csv", GOVERNANCE_METADATA_PAGE_COLUMNS)
    pipeline_io.write_csv(gov_obs, out / "governance_metadata_observations.csv", GOVERNANCE_METADATA_OBSERVATION_COLUMNS)
    return {"obs": obs, "primary": primary, "sens_all": sens_all, "sens_de": sens_de, "pages": pages, "snapshots": snapshots}


def apply_decisions_to_tables(baseline_snaps, baseline_pages, rescue_snaps, rescue_pages, decisions):
    snaps = baseline_snaps.copy()
    pages = baseline_pages.copy()
    for _, d in decisions.iterrows():
        if d["rescue_decision"] != "replace_with_rescue":
            continue
        fid, tp = str(d["firm_id"]), str(d["relative_timepoint"])
        rsnap = rescue_snaps[(rescue_snaps["firm_id"].astype(str) == fid) & (rescue_snaps["relative_timepoint"] == tp)]
        rpages = rescue_pages[(rescue_pages["firm_id"].astype(str) == fid) & (rescue_pages["relative_timepoint"] == tp)]
        if rsnap.empty:
            continue
        snaps = snaps[~((snaps["firm_id"].astype(str) == fid) & (snaps["relative_timepoint"] == tp))]
        pages = pages[~((pages["firm_id"].astype(str) == fid) & (pages["relative_timepoint"] == tp))]
        row = rsnap.iloc[0].to_dict()
        if str(d.get("forced_sensitivity_treatment")).lower() in {"true", "1"} and str(
            row.get("observation_recommendation")
        ) == "include":
            row["observation_recommendation"] = "sensitivity_analysis"
        snaps = pd.concat([snaps, pd.DataFrame([row])], ignore_index=True)
        if len(rpages):
            pages = pd.concat([pages, rpages], ignore_index=True)
    return snaps, pages


class RescueOrchestrator:
    def __init__(
        self,
        *,
        config_path: Path,
        dry_run: bool = False,
        no_network: bool = False,
        firms: list[str] | None = None,
        timepoints: list[str] | None = None,
    ) -> None:
        self.config_path = config_path
        self.dry_run = dry_run
        self.no_network = no_network
        self.firm_filter = [str(f) for f in firms] if firms else None
        self.timepoint_filter = [str(t) for t in timepoints] if timepoints else None
        self.layout = rescue_layout(ROOT)
        self.rescue_doc = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.transport = {**DEFAULT_TRANSPORT_POLICY, **(self.rescue_doc.get("transport") or {})}
        self.parent_sha = None
        self.candidates = []
        self.alias_map = {}
        self.targeted: list[str] = []
        self.vreport: dict[str, Any] = {}
        self.cand_hash = ""
        self.execution_plan: dict[str, Any] = {}

    def _network_guard(self, stage: str) -> None:
        if self.no_network or self.dry_run:
            raise RuntimeError(
                f"refusing stage={stage}: --no-network/--dry-run forbids Wayback or crawl I/O"
            )

    def validate(self) -> int:
        layout = self.layout
        ensure_workspace_dirs(layout, create=not self.dry_run)
        assert_not_parent_release(layout["processed_output"], project_root=ROOT)
        assert_not_parent_release(layout["release"], project_root=ROOT)
        guard_release_destination(layout["release"], ROOT)

        parent = assert_parent_unchanged(layout["parent_data"])
        self.parent_sha = parent["parent_primary_sha256"]

        known = set(pd.read_csv(layout["parent_data"] / "firms.csv", dtype=str)["firm_id"].astype(str))
        nonready = _load_nonready(layout["parent_data"])
        raw = load_raw_candidates(layout["candidate_csv"])
        self.cand_hash = file_sha256(layout["candidate_csv"])
        candidates, vreport = normalize_candidates(raw, nonready_firm_ids=nonready, known_firm_ids=known)
        self.candidates = candidates
        self.vreport = vreport
        self.alias_map = build_alias_map(candidates)
        self.targeted = sorted({c.firm_id for c in candidates}, key=int)
        if self.firm_filter:
            self.targeted = [f for f in self.targeted if f in set(self.firm_filter)]
            self.alias_map = {k: v for k, v in self.alias_map.items() if k[0] in set(self.firm_filter)}
        if self.timepoint_filter:
            self.alias_map = {k: v for k, v in self.alias_map.items() if k[1] in set(self.timepoint_filter)}

        firms_df = pd.read_csv(layout["parent_data"] / "firms.csv", dtype=str)
        firm_web = {str(r.firm_id): r.website for _, r in firms_df.iterrows()}
        alias_rows = []
        for c in candidates:
            if self.firm_filter and c.firm_id not in set(self.firm_filter):
                continue
            if self.timepoint_filter and c.target_timepoint not in set(self.timepoint_filter):
                continue
            alias_rows.append(
                {
                    "firm_id": c.firm_id,
                    "relative_timepoint": c.target_timepoint,
                    "original_configured_seed": firm_web.get(c.firm_id),
                    "rescue_candidate_seed": c.candidate_seed_url,
                    "priority": c.priority,
                    "source_row_id": c.source_row_id,
                    "reason_for_alias": c.assessment,
                    "historical_domain_flag": c.historical_domain_flag,
                    "locale_path_flag": c.locale_path_flag,
                    "entity_change_warning": c.entity_change_warning,
                    "migration_warning": c.migration_warning,
                    "candidate_type": c.candidate_type,
                    "rescue_strength": c.rescue_strength,
                    "archive_evidence": c.archive_evidence,
                }
            )
        timepoints = sorted({r["relative_timepoint"] for r in alias_rows})

        self.execution_plan = {
            "dry_run": self.dry_run,
            "no_network": self.no_network,
            "parent_release": str(layout["parent_release"]),
            "parent_primary_sha256": self.parent_sha,
            "candidate_sha256": self.cand_hash,
            "targeted_firms": self.targeted,
            "targeted_timepoints": timepoints,
            "n_aliases": len(alias_rows),
            "safe_to_execute": bool(vreport.get("safe_to_execute")),
            "output_paths": {k: str(v) for k, v in layout.items()},
            "transport": self.transport,
            "write_protection": {
                "parent_release_blocked": True,
                "release_destination": str(layout["release"]),
            },
        }

        if not self.dry_run:
            write_candidate_validation_report(
                ROOT / "reports" / "rescue_candidate_input_validation.md",
                vreport,
                candidate_hash=self.cand_hash,
            )
            # also keep package helper report writer for compatibility
            write_validation_report(
                vreport,
                layout["reports"] / "rescue_candidate_input_validation.md",
                candidate_hash=self.cand_hash,
            )
            candidates_to_dataframe(candidates).to_csv(
                layout["interim"] / "normalized_rescue_candidates.csv", index=False
            )
            _refresh_rescue_config(layout, self.targeted, timepoints, alias_rows)
            (layout["interim"] / "execution_plan.json").write_text(
                json.dumps(self.execution_plan, indent=2), encoding="utf-8"
            )

        print(json.dumps({"stage": "validate", **self.execution_plan}, indent=2))
        if not vreport.get("safe_to_execute"):
            print("HARD FAIL: candidate validation", file=sys.stderr)
            return 2
        return 0

    def preflight(self) -> int:
        # Local checks only when --no-network; live Wayback probe is VM-side without --no-network.
        rc = self.validate()
        if rc:
            return rc
        if self.no_network or self.dry_run:
            print(
                json.dumps(
                    {
                        "stage": "preflight",
                        "mode": "no_network",
                        "ok": True,
                        "note": "Skipped live Wayback probe; run without --no-network on the VM",
                    },
                    indent=2,
                )
            )
            return 0
        # Live probe (VM execution only)
        import httpx

        url = "https://web.archive.org/"
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(url)
            ok = 200 <= resp.status_code < 400
            print(json.dumps({"stage": "preflight", "url": url, "http_status": resp.status_code, "ok": ok}, indent=2))
            return 0 if ok else 3
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "stage": "preflight",
                        "ok": False,
                        "classification": TRANSPORT_FAILURE_RESUMABLE,
                        "error": str(exc),
                    },
                    indent=2,
                )
            )
            return 3

    def _runner(self) -> RescuePipelineRunner:
        layout = self.layout
        ensure_workspace_dirs(layout, create=True)
        pipe_yaml = _write_pipeline_yaml(self.rescue_doc, layout["interim"], self.transport)
        cfg = PipelineConfig.from_yaml(pipe_yaml).resolve_paths(ROOT)
        return RescuePipelineRunner(cfg, seed_aliases=self.alias_map)

    def bootstrap_workspace(self, runner: RescuePipelineRunner) -> None:
        layout = self.layout
        out = layout["processed_output"]
        assert_not_parent_release(out, project_root=ROOT)
        shutil.copy2(layout["parent_data"] / "firms.csv", out / "firms.csv")
        snaps = pd.read_csv(layout["parent_data"] / "full_sample_snapshots.csv", dtype=str)
        pages = pd.read_csv(layout["parent_data"] / "full_sample_pages.csv", dtype=str)
        snaps.to_csv(out / "snapshots.csv", index=False)
        pages.to_csv(out / "pages.csv", index=False)

    def discover(self) -> int:
        self._network_guard("discover")
        if self.validate():
            return 2
        runner = self._runner()
        self.bootstrap_workspace(runner)
        runner.prepare()
        snaps = runner.discover_snapshots(firm_ids=self.targeted)
        snaps = snaps[snaps["firm_id"].astype(str).isin(self.targeted)].copy()
        log_df = pd.DataFrame(runner.rescue_discovery_log)
        log_df.to_csv(self.layout["interim"] / "rescue_discovery_log.csv", index=False)
        snaps = _annotate_rescue_domains(snaps, log_df)
        snaps.to_csv(self.layout["interim"] / "rescue_snapshots.csv", index=False)
        print(f"discover complete: selected={(snaps.get('snapshot_status') == 'selected').sum() if len(snaps) else 0}")
        return 0

    def crawl(self) -> int:
        self._network_guard("crawl")
        if not self.alias_map and self.validate():
            return 2
        runner = self._runner()
        runner.prepare()
        snaps_path = self.layout["interim"] / "rescue_snapshots.csv"
        if not snaps_path.exists():
            raise FileNotFoundError("missing rescue_snapshots.csv — run discover first")
        rescue_snaps = pd.read_csv(snaps_path, dtype=str)
        parent_snaps = pd.read_csv(self.layout["parent_data"] / "full_sample_snapshots.csv", dtype=str)
        parent_pages = pd.read_csv(self.layout["parent_data"] / "full_sample_pages.csv", dtype=str)
        non_t = parent_snaps[~parent_snaps["firm_id"].astype(str).isin(self.targeted)].copy()
        for col in SNAPSHOT_COLUMNS + RESCUE_EXTRA_COLS:
            if col not in rescue_snaps.columns:
                rescue_snaps[col] = None
            if col not in non_t.columns:
                non_t[col] = None
        merged = pd.concat([non_t, rescue_snaps], ignore_index=True)
        assert_not_parent_release(runner.output_dir, project_root=ROOT)
        merged.to_csv(runner.output_dir / "snapshots.csv", index=False)
        non_t_pages = parent_pages[~parent_pages["firm_id"].astype(str).isin(self.targeted)]
        pipeline_io.write_csv(non_t_pages, runner.output_dir / "pages.csv", PAGE_COLUMNS)
        pages = runner.crawl_and_extract(firm_ids=self.targeted)
        pages[pages["firm_id"].astype(str).isin(self.targeted)].to_csv(
            self.layout["interim"] / "rescue_pages.csv", index=False
        )
        print(f"crawl complete: pages={len(pages)}")
        return 0

    def extract(self) -> int:
        # Extraction is performed inside crawl_and_extract; this stage rebuilds observation tables.
        if self.dry_run or self.no_network:
            # offline: only verify inputs exist / plan
            print(json.dumps({"stage": "extract", "dry_run": True, "note": "no extraction performed"}, indent=2))
            return 0
        runner = self._runner()
        t_snaps = pd.read_csv(runner.output_dir / "snapshots.csv", dtype=str)
        t_snaps = t_snaps[t_snaps["firm_id"].astype(str).isin(self.targeted)].copy()
        t_pages = pd.read_csv(runner.output_dir / "pages.csv", dtype=str)
        t_pages = t_pages[t_pages["firm_id"].astype(str).isin(self.targeted)].copy()
        gov_p = build_governance_metadata_pages(t_pages)
        gov_o = build_governance_metadata_observations(t_snaps, gov_p)
        rescue_obs = build_observation_text_summary(t_snaps, t_pages, gov_o, runner.config.analysis)
        rescue_obs.to_csv(self.layout["interim"] / "rescue_observation_text_summary.csv", index=False)
        t_snaps.to_csv(self.layout["interim"] / "rescue_snapshots.csv", index=False)
        t_pages.to_csv(self.layout["interim"] / "rescue_pages.csv", index=False)
        print(f"extract complete: observations={len(rescue_obs)}")
        return 0

    def compare(self) -> int:
        if self.validate():
            return 2
        if self.dry_run or self.no_network:
            print(json.dumps({"stage": "compare", "dry_run": True, "planned_keys": len(self.alias_map)}, indent=2))
            return 0
        layout = self.layout
        runner = self._runner()
        parent_snaps = pd.read_csv(layout["parent_data"] / "full_sample_snapshots.csv", dtype=str)
        parent_pages = pd.read_csv(layout["parent_data"] / "full_sample_pages.csv", dtype=str)
        parent_obs = pd.read_csv(layout["parent_data"] / "full_sample_observation_text_summary.csv", dtype=str)
        t_snaps = pd.read_csv(layout["interim"] / "rescue_snapshots.csv", dtype=str)
        t_pages = pd.read_csv(layout["interim"] / "rescue_pages.csv", dtype=str)
        rescue_obs = pd.read_csv(layout["interim"] / "rescue_observation_text_summary.csv", dtype=str)
        force_sens = force_sensitivity_firm_ids()
        entity_firms = entity_change_firm_ids() | {c.firm_id for c in self.candidates if c.entity_change_warning}
        mig_keys = {(c.firm_id, c.target_timepoint) for c in self.candidates if c.migration_warning}
        min_tok = int(runner.config.analysis.min_branding_tokens)
        rows = []
        for fid, tp in sorted(self.alias_map.keys(), key=lambda x: (int(x[0]), x[1])):
            o_obs = _obs_lookup(parent_obs, fid, tp)
            r_obs = _obs_lookup(rescue_obs, fid, tp)
            o_snap = _obs_lookup(parent_snaps, fid, tp)
            r_snap = _obs_lookup(t_snaps, fid, tp)
            transport_fail = False
            if r_snap is not None and str(r_snap.get("selection_reason") or "").find(TRANSPORT_FAILURE_RESUMABLE) >= 0:
                transport_fail = True
            packed = decide_rescue(
                firm_id=fid,
                original_obs=o_obs,
                rescue_obs=r_obs,
                original_snap=o_snap,
                rescue_snap=r_snap,
                entity_change_flag=fid in entity_firms,
                migration_flag=(fid, tp) in mig_keys,
                force_sensitivity_firms=force_sens,
                min_branding_tokens=min_tok,
                transport_failure=transport_fail,
            )
            packed.update(
                {
                    "firm_id": fid,
                    "company": (o_obs.get("company") if o_obs is not None else None)
                    or (r_obs.get("company") if r_obs is not None else None),
                    "relative_timepoint": tp,
                }
            )
            rows.append(packed)
        decisions = pd.DataFrame(rows)
        decisions.to_csv(layout["interim"] / "rescue_comparison_decisions.csv", index=False)

        final_snaps, final_pages = apply_decisions_to_tables(
            parent_snaps, parent_pages, t_snaps, t_pages, decisions
        )
        assert_not_parent_release(runner.output_dir, project_root=ROOT)
        pipeline_io.write_csv(final_snaps, runner.output_dir / "snapshots.csv", SNAPSHOT_COLUMNS)
        pipeline_io.write_csv(final_pages, runner.output_dir / "pages.csv", PAGE_COLUMNS)
        corpora = regenerate_corpora(runner)
        firms = pd.read_csv(runner.output_dir / "firms.csv", dtype=str)
        coverage = build_coverage(
            firms, corpora["obs"], corpora["primary"], corpora["sens_de"], decisions, set(self.targeted)
        )
        coverage.to_csv(runner.output_dir / "firm_longitudinal_coverage.csv", index=False)
        sample = build_manual_validation_sample(
            decisions,
            newly_ready_firm_ids=set(
                coverage.loc[coverage["german_longitudinal_ready_extended"] == "TRUE", "firm_id"].astype(str)
            ),
        )
        sample.to_csv(layout["interim"] / "rescue_manual_validation_sample.csv", index=False)
        audit_non_targeted_immutability(
            parent_obs=parent_obs,
            rescue_obs=corpora["obs"],
            targeted_firm_ids=set(self.targeted),
        )
        print(f"compare complete: decisions={len(decisions)}")
        return 0

    def report(self) -> int:
        if self.validate():
            return 2
        write_report_templates(self.layout["reports"])
        write_report_templates(ROOT / "reports")
        print(json.dumps({"stage": "report", "templates_written": True, "dry_run": self.dry_run}, indent=2))
        return 0

    def acceptance(self) -> int:
        if self.validate():
            return 2
        if self.dry_run or self.no_network:
            print(
                json.dumps(
                    {
                        "stage": "acceptance",
                        "dry_run": True,
                        "note": "Release assembly skipped under --no-network/--dry-run",
                    },
                    indent=2,
                )
            )
            return 0
        layout = self.layout
        runner = self._runner()
        decisions = pd.read_csv(layout["interim"] / "rescue_comparison_decisions.csv", dtype=str)
        corpora = regenerate_corpora(runner)
        coverage = pd.read_csv(runner.output_dir / "firm_longitudinal_coverage.csv", dtype=str)
        audit_non_targeted_immutability(
            parent_obs=pd.read_csv(layout["parent_data"] / "full_sample_observation_text_summary.csv", dtype=str),
            rescue_obs=corpora["obs"],
            targeted_firm_ids=set(self.targeted),
        )
        assemble_rescue_release(
            project_root=ROOT,
            processed_output=runner.output_dir,
            release_dir=layout["release"],
            parent_data=layout["parent_data"],
            candidate_csv=layout["candidate_csv"],
            rescue_config=layout["rescue_config"],
            full_sample_config=layout["full_sample_config"],
            targeted_firms=self.targeted,
            timepoints_targeted=sorted({c.target_timepoint for c in self.candidates}),
            decisions=decisions,
            discovery_log=layout["interim"] / "rescue_discovery_log.csv",
            counts={
                "primary": int(len(corpora["primary"])),
                "sensitivity_all": int(len(corpora["sens_all"])),
                "sensitivity_de": int(len(corpora["sens_de"])),
                "ready_primary": int((coverage["german_longitudinal_ready_primary"] == "TRUE").sum()),
                "ready_extended": int((coverage["german_longitudinal_ready_extended"] == "TRUE").sum()),
            },
            execution_environment="vm_or_local",
        )
        self.report()
        print(f"acceptance complete: release={layout['release']}")
        return 0

    def full(self) -> int:
        for stage in ("validate", "preflight", "discover", "crawl", "extract", "compare", "report", "acceptance"):
            rc = getattr(self, stage)()
            if rc:
                return rc
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase B targeted rescue orchestrator")
    parser.add_argument("--config", default="config/full_sample_rescue.yaml")
    parser.add_argument("--stage", choices=STAGES, default="validate")
    parser.add_argument("--resume-from", choices=RESUME_FROM, default=None)
    parser.add_argument("--firms", nargs="*", default=None, help="Optional firm_id filter")
    parser.add_argument("--timepoints", nargs="*", default=None, help="Optional timepoint filter")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args(argv)

    orch = RescueOrchestrator(
        config_path=(ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config),
        dry_run=args.dry_run,
        no_network=args.no_network,
        firms=args.firms,
        timepoints=args.timepoints,
    )

    if args.resume_from:
        order = list(RESUME_FROM)
        start = order.index(args.resume_from)
        for stage in order[start:]:
            rc = getattr(orch, stage)()
            if rc:
                return rc
        return 0

    return getattr(orch, args.stage)()


if __name__ == "__main__":
    raise SystemExit(main())
