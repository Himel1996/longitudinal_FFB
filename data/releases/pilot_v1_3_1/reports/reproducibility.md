# Pilot v1.3.1 Reproducibility

**Run ID:** `6f4f1dd0-8f2a-42ca-ae1d-7f3067b47fc9`  
**Run date:** 2026-07-24  
**Git commit:** `565da6bfd8969793d64c80a4d2d68850a25e4191`

---

## Scope

Clean five-firm rebuild with final reserved-slot prioritization, including legal-path demotion under `/unternehmen/`.

v1.3 (pre-demotion crawl) is archived at `data/archive/pilot_v1_3_pre_final_priority_rebuild/`.

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
```

---

## Rebuild v1.3.1

```bash
export PYTHONPATH=src

# Optional: clear prior crawl/corpus outputs (keep data/interim/cdx and data/interim/html)
rm -f data/output/*.csv data/output/*.json data/output/*.parquet

python -m ffb_webminer prepare --config config/pilot.yaml
python -m ffb_webminer discover-snapshots --config config/pilot.yaml
python -m ffb_webminer crawl --config config/pilot.yaml
python -c "from pathlib import Path; from ffb_webminer.config import PipelineConfig; from ffb_webminer.pipeline.runner import PipelineRunner; r=PipelineRunner(PipelineConfig.from_yaml('config/pilot.yaml'), project_root=Path('.')); r.validate_and_export(); r.report()"
python scripts/run_manual_corpus_validation.py
python scripts/run_manual_scaling_validation.py
python scripts/check_pilot_consistency.py
python scripts/build_pilot_release.py
```

Expected release path: `data/releases/pilot_v1_3_1/`

`scripts/build_pilot_release.py` **fails** if pipeline code is dirty or drifted from `run_manifest.json`’s `git_commit`.

---

## Full 30-firm config (do not run until confirmed)

```bash
# config/full_sample.yaml  (top_n: 30)
```

Baseline release for scaling: **pilot_v1_3_1**.

---

## Tests

```bash
pytest tests/ -q
```

Expected: 66 passed.
