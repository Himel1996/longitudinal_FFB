#!/usr/bin/env python3
"""Build pilot_v1_1 release bundle."""

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

RELEASE = "pilot_v1_1"
CSV_FILES = [
    "firms.csv",
    "snapshots.csv",
    "pages.csv",
    "observation_text_summary.csv",
    "branding_corpus_pages.csv",
    "branding_corpus_observations.csv",
    "branding_corpus_observations_primary.csv",
    "branding_corpus_observations_sensitivity.csv",
    "governance_metadata_pages.csv",
    "governance_metadata_observations.csv",
    "analysis_observations.csv",
    "analysis_observations_sensitivity.csv",
    "manual_validation_sample.csv",
    "manual_corpus_validation.csv",
    "firm_coverage_matrix.csv",
    "homepage_visuals.csv",
    "quality_summary.csv",
    "run_manifest.json",
]

REPORT_FILES = [
    "pilot_readiness.md",
    "manual_validation_report.md",
    "pilot_quality_report.md",
    "corpus_quality_report.md",
    "v1_1_change_report.md",
    "temporal_validity_report.md",
    "extraction_validation_report.md",
    "reproducibility.md",
]

CONFIG_FILES = [
    "config/pilot.yaml",
    "config/event_dates.yaml",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/pilot.yaml")
    args = parser.parse_args()

    config = PipelineConfig.from_yaml(ROOT / args.config)
    out = ROOT / config.run.output_dir
    release_dir = ROOT / "data" / "releases" / RELEASE

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)

    # CSV + manifest
    data_dir = release_dir / "data"
    data_dir.mkdir()
    for fname in CSV_FILES:
        src = out / fname
        if src.exists():
            shutil.copy2(src, data_dir / fname)

    # Reports
    reports_dir = release_dir / "reports"
    reports_dir.mkdir()
    for fname in REPORT_FILES:
        src = ROOT / "reports" / fname
        if src.exists():
            shutil.copy2(src, reports_dir / fname)

    # Screenshots + evidence
    for sub in ("validation_screenshots", "evidence"):
        src = out / sub
        if src.exists():
            shutil.copytree(src, release_dir / sub)

    # Config
    cfg_dir = release_dir / "config"
    cfg_dir.mkdir()
    for rel in CONFIG_FILES:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, cfg_dir / Path(rel).name)

    # README
    manifest = json.loads((data_dir / "run_manifest.json").read_text()) if (data_dir / "run_manifest.json").exists() else {}
    readme = f"""# FFB Pilot Dataset v1.1

**Release date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  
**Run ID:** `{manifest.get('run_id', 'unknown')}`  
**Git commit:** `{manifest.get('git_commit', 'unknown')}`

## Contents

| Path | Description |
|------|-------------|
| `data/firms.csv` | 5 pilot firms |
| `data/snapshots.csv` | 25 firm × timepoint observations |
| `data/pages.csv` | Crawled pages with extraction |
| `data/observation_text_summary.csv` | Observation-level text eligibility and volume |
| `data/branding_corpus_pages.csv` | Page-level branding corpus |
| `data/branding_corpus_observations.csv` | Aggregated branding text by observation |
| `data/branding_corpus_observations_primary.csv` | Primary branding observation corpus |
| `data/branding_corpus_observations_sensitivity.csv` | Sensitivity branding observation corpus |
| `data/governance_metadata_pages.csv` | Impressum/governance page layer |
| `data/governance_metadata_observations.csv` | Observation-level governance summary |
| `data/analysis_observations.csv` | Primary analysis pool |
| `data/analysis_observations_sensitivity.csv` | Extended sensitivity pool |
| `data/manual_validation_sample.csv` | Human-validated observations |
| `data/manual_corpus_validation.csv` | Corpus/classification validation sample |
| `data/firm_coverage_matrix.csv` | Coverage by firm and timepoint |
| `data/homepage_visuals.csv` | Optional visual extraction |
| `data/quality_summary.csv` | Quality metrics |
| `data/run_manifest.json` | Run metadata |
| `validation_screenshots/` | Browser validation PNGs |
| `evidence/` | Screenshot URL manifest |
| `config/` | Pipeline configuration |
| `reports/` | Quality and validation reports |

## Reproduce

See `reports/reproducibility.md` for exact commands from a clean clone.

## Citation

Family Firm Branding in Transition — Archived Web Pipeline (Pilot v1.1)
"""
    (release_dir / "README.md").write_text(readme, encoding="utf-8")

    commit = manifest.get("git_commit", "unknown")
    print(f"Release built: {release_dir}")
    print(f"Run ID: {manifest.get('run_id')}")
    print(f"Commit: {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
