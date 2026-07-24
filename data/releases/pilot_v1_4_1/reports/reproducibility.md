# Pilot v1.4.1 Reproducibility

**Run ID:** `95bac495-6940-47be-b3ff-339fd97afa3e`  
**Run date:** 2026-07-24  
**Git commit:** `5a5fec78333d7baead292037b2be2a94f6733366`

---

## Scope

Targeted acceptance-fix rebuild of the top-five pilot:

- segment-aware reserved-slot path matching
- analysis-token policy with `token_count == analysis_token_count` (choice A)

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
```

---

## Rebuild v1.4.1

```bash
export PYTHONPATH=src

# Archive prior release, clear crawl/corpus outputs; keep CDX + HTML caches
# mv data/releases/pilot_v1_4 data/archive/pilot_v1_4_pre_v1_4_1
# rm -f data/output/*.csv data/output/*.json

python -m ffb_webminer prepare --config config/pilot.yaml
python -m ffb_webminer discover-snapshots --config config/pilot.yaml
python -m ffb_webminer crawl --config config/pilot.yaml
python -c "from pathlib import Path; from ffb_webminer.config import PipelineConfig; from ffb_webminer.pipeline.runner import PipelineRunner; r=PipelineRunner(PipelineConfig.from_yaml('config/pilot.yaml'), project_root=Path('.')); r.validate_and_export(); r.report()"
python scripts/run_manual_corpus_validation.py
python scripts/run_manual_scaling_validation.py
python scripts/check_pilot_consistency.py
python scripts/build_pilot_release.py
python scripts/audit_pilot_v1_4_1_acceptance.py
```

Expected release path: `data/releases/pilot_v1_4_1/`

`scripts/build_pilot_release.py` fails if pipeline code is dirty or drifted from `run_manifest.json`’s `git_commit`.

---

## Full 30-firm config (do not run until READY TO SCALE)

```bash
# config/full_sample.yaml  (top_n: 30)
```

---

## Tests

```bash
pytest tests/ -q
```
