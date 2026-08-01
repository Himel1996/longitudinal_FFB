"""Rescue release assembly (writes only to full_sample_v1_1_rescue)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ffb_webminer.rescue.audit import assert_parent_unchanged, file_sha256, guard_release_destination
from ffb_webminer.rescue.paths import PARENT_RELEASE_NAME, RESCUE_RELEASE_NAME


def git_head(project_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=project_root, text=True
        ).strip()
    except Exception:
        return "unknown"


def assemble_rescue_release(
    *,
    project_root: Path,
    processed_output: Path,
    release_dir: Path,
    parent_data: Path,
    candidate_csv: Path,
    rescue_config: Path,
    full_sample_config: Path,
    targeted_firms: list[str],
    timepoints_targeted: list[str],
    decisions: pd.DataFrame,
    discovery_log: Path | None,
    counts: dict[str, Any],
    execution_environment: str = "unset",
) -> Path:
    guard_release_destination(release_dir, project_root)
    parent_check = assert_parent_unchanged(parent_data)

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
        sp = processed_output / src
        if sp.exists():
            shutil.copy2(sp, data_dir / dst)

    decisions.to_csv(data_dir / "rescue_comparison_decisions.csv", index=False)
    if discovery_log and discovery_log.exists():
        shutil.copy2(discovery_log, data_dir / "rescue_discovery_log.csv")
    shutil.copy2(candidate_csv, data_dir / "full_sample_url_rescue_candidates.csv")
    shutil.copy2(rescue_config, cfg_dir / "full_sample_rescue.yaml")
    shutil.copy2(full_sample_config, cfg_dir / "full_sample.yaml")

    manifest = {
        "parent_release": PARENT_RELEASE_NAME,
        "release_name": RESCUE_RELEASE_NAME,
        "run_type": "targeted_rescue",
        "rescue_candidate_file": "data/input/full_sample_url_rescue_candidates.csv",
        "rescue_candidate_file_hash": file_sha256(candidate_csv),
        "firms_targeted": targeted_firms,
        "timepoints_targeted": timepoints_targeted,
        "git_commit": git_head(project_root),
        "pipeline_version": "ffb_webminer",
        "extraction_logic_version": "full_sample_v1_frozen",
        "source_code_changed_for_core_rules": False,
        "validated_core_rules_changed": False,
        "core_logic_changed": False,
        "original_release_preserved": True,
        "parent_primary_sha256": parent_check["parent_primary_sha256"],
        "config_hash_full_sample": file_sha256(full_sample_config),
        "config_hash_rescue": file_sha256(rescue_config),
        "execution_environment": execution_environment,
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
    }
    (data_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return release_dir
