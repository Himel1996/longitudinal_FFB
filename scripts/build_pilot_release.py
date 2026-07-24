#!/usr/bin/env python3
"""Build pilot_v1_4_1 release bundle with git-commit sync enforcement."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig

RELEASE = "pilot_v1_4_1"
CSV_FILES = [
    "firms.csv",
    "snapshots.csv",
    "pages.csv",
    "observation_text_summary.csv",
    "branding_corpus_pages.csv",
    "branding_corpus_pages_all_languages.csv",
    "branding_corpus_pages_de.csv",
    "branding_corpus_pages_en.csv",
    "branding_corpus_pages_other.csv",
    "branding_corpus_observations.csv",
    "branding_corpus_observations_all_languages.csv",
    "branding_corpus_observations_de.csv",
    "branding_corpus_observations_en.csv",
    "branding_corpus_observations_other.csv",
    "branding_corpus_observations_primary.csv",
    "branding_corpus_observations_sensitivity.csv",
    "governance_metadata_pages.csv",
    "governance_metadata_observations.csv",
    "analysis_observations.csv",
    "analysis_observations_sensitivity.csv",
    "manual_validation_sample.csv",
    "manual_corpus_validation.csv",
    "manual_scaling_validation.csv",
    "firm_coverage_matrix.csv",
    "homepage_visuals.csv",
    "quality_summary.csv",
    "crawl_priority_summary.csv",
    "duplicate_summary.csv",
    "run_manifest.json",
]

REPORT_FILES = [
    "pilot_readiness.md",
    "manual_validation_report.md",
    "pilot_quality_report.md",
    "corpus_quality_report.md",
    "v1_1_change_report.md",
    "v1_2_change_report.md",
    "v1_3_change_report.md",
    "v1_3_1_change_report.md",
    "v1_4_change_report.md",
    "v1_4_1_change_report.md",
    "temporal_validity_report.md",
    "extraction_validation_report.md",
    "reproducibility.md",
    "release_acceptance_audit.md",
]

CONFIG_FILES = [
    "config/pilot.yaml",
    "config/full_sample.yaml",
    "config/event_dates.yaml",
]

TRACKED_GLOBS = (
    "src/",
    "config/",
    "scripts/",
    "tests/",
    "pyproject.toml",
)


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _dirty_pipeline_paths() -> list[str]:
    raw = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    )
    dirty: list[str] = []
    for line in raw.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if any(path.startswith(prefix) or path == prefix.rstrip("/") for prefix in TRACKED_GLOBS):
            dirty.append(path)
    return dirty


def _assert_git_sync(manifest_commit: str | None) -> None:
    dirty = _dirty_pipeline_paths()
    if dirty:
        raise SystemExit(
            "FAIL: working tree has uncommitted pipeline changes; "
            f"commit them before release.\n  - " + "\n  - ".join(dirty[:40])
        )
    if not manifest_commit:
        raise SystemExit("FAIL: run_manifest.json missing git_commit")
    head = _git_head()
    code_diff = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            f"{manifest_commit}..{head}",
            "--",
            "src",
            "config",
            "scripts",
            "tests",
            "pyproject.toml",
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    if code_diff:
        raise SystemExit(
            f"FAIL: pipeline code changed since run_manifest git_commit {manifest_commit}.\n"
            f"Changed paths:\n{code_diff}"
        )
    try:
        subprocess.check_call(
            ["git", "cat-file", "-e", f"{manifest_commit}^{{commit}}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"FAIL: manifest git_commit {manifest_commit!r} is not a valid commit") from exc
    print(f"Git sync check: PASSED (manifest={manifest_commit[:12]} head={head[:12]})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/pilot.yaml")
    args = parser.parse_args()

    config = PipelineConfig.from_yaml(ROOT / args.config)
    out = ROOT / config.run.output_dir
    release_dir = ROOT / "data" / "releases" / RELEASE

    manifest_path = out / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    _assert_git_sync(manifest.get("git_commit"))

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)

    data_dir = release_dir / "data"
    data_dir.mkdir()
    for fname in CSV_FILES:
        src = out / fname
        if src.exists():
            shutil.copy2(src, data_dir / fname)

    reports_dir = release_dir / "reports"
    reports_dir.mkdir()
    for fname in REPORT_FILES:
        src = ROOT / "reports" / fname
        if src.exists():
            shutil.copy2(src, reports_dir / fname)

    # Also copy acceptance audit JSON into release reports if present
    audit_json = ROOT / "data/interim/release_acceptance_audit.json"
    if audit_json.exists():
        shutil.copy2(audit_json, reports_dir / "release_acceptance_audit.json")
        shutil.copy2(audit_json, data_dir / "release_acceptance_audit.json")

    for sub in ("validation_screenshots", "evidence"):
        src = out / sub
        if src.exists():
            shutil.copytree(src, release_dir / sub)

    cfg_dir = release_dir / "config"
    cfg_dir.mkdir()
    for rel in CONFIG_FILES:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, cfg_dir / Path(rel).name)

    readme = f"""# FFB Pilot Dataset v1.4.1

**Release date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  
**Run ID:** `{manifest.get('run_id', 'unknown')}`  
**Git commit:** `{manifest.get('git_commit', 'unknown')}`

## Contents

Targeted acceptance fix rebuild of the top-five pilot:

- segment-aware reserved-slot path matching (no broad-substring `unternehmen` false positives)
- language-appropriate analysis token counts (`token_count` == `analysis_token_count`)

See `reports/v1_4_1_change_report.md` and `reports/release_acceptance_audit.md`.

Family Firm Branding in Transition — Archived Web Pipeline (Pilot v1.4.1)
"""
    (release_dir / "README.md").write_text(readme, encoding="utf-8")
    print(f"Release built: {release_dir}")
    print(f"Run ID: {manifest.get('run_id')}")
    print(f"Commit: {manifest.get('git_commit')}")
    print("Git sync check: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
