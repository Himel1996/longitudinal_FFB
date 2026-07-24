# Pilot v1.4 Reproducibility

**Run ID:** `ab33b6f5-06a8-4981-a805-65bf3f6b3516`  
**Run date:** 2026-07-24  
**Git commit:** `1a1d7ba1832e780aa19be2804c996964e61ec35a`

---

## Scope

From-scratch top-5 verification rebuild of the accepted scaling pipeline.

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
```

---

## Rebuild v1.4

```bash
export PYTHONPATH=src

# Clear prior crawl/corpus outputs (optional; keep data/interim/cdx and data/interim/html)
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

Expected release path: `data/releases/pilot_v1_4/`

`scripts/build_pilot_release.py` fails if pipeline code is dirty or drifted from `run_manifest.json`’s `git_commit`.

---

## Full 30-firm config (do not run until v1.4 is verified)

```bash
# config/full_sample.yaml  (top_n: 30)
```

---

## Tests

```bash
pytest tests/ -q
```

Expected: 66 passed.
