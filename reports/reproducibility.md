# Pilot v1.3 Reproducibility

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Run date:** 2026-07-24  
**Git commit:** see `data/output/run_manifest.json`

---

## Scope

v1.3 rebuilds the first five firms with:

1. within firm × timepoint content deduplication
2. hybrid language handling (path priority + post-extraction German primary corpus)
3. reserved-slot staged crawl prioritization

v1.2 is archived at `data/archive/pilot_v1_2_pre_v1_3/`.

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
```

---

## Rebuild v1.3 (five firms)

```bash
export PYTHONPATH=src
# Keep existing snapshot selection; re-crawl with reserved slots
python -m ffb_webminer crawl --config config/pilot.yaml
python -c "from pathlib import Path; from ffb_webminer.config import PipelineConfig; from ffb_webminer.pipeline.runner import PipelineRunner; r=PipelineRunner(PipelineConfig.from_yaml('config/pilot.yaml'), project_root=Path('.')); r.validate_and_export(); r.report()"
python scripts/run_manual_corpus_validation.py
python scripts/run_manual_scaling_validation.py
python scripts/check_pilot_consistency.py
python scripts/build_pilot_release.py
```

Expected release path: `data/releases/pilot_v1_3/`

---

## Refresh corpora without re-crawl

```bash
python scripts/refresh_corpus_outputs.py
python scripts/check_pilot_consistency.py
```

---

## Full 30-firm config (do not run until v1.3 accepted)

```bash
# config/full_sample.yaml  (top_n: 30)
# Explicitly requested after verification only
```

---

## Tests

```bash
pytest tests/ -q
```

Expected: all tests pass (66+).
