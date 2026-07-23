# Pilot v1.2 Reproducibility

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Run date:** 2026-07-23  
**Git commit:** `40284949bcf3e42355fcdf7fd93bacd00610c6f7`

---

## Scope

v1.2 reclassifies and regenerates corpus outputs from accepted v1.1 extractions. Full Wayback re-crawl is not required for these integrity fixes.

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
```

---

## Regenerate v1.2 corpus outputs from existing pages

```bash
export PYTHONPATH=src
python scripts/refresh_corpus_outputs.py
python scripts/run_manual_corpus_validation.py
python scripts/check_pilot_consistency.py
python scripts/build_pilot_release.py
```

Expected release path: `data/releases/pilot_v1_2/`

---

## Optional full clean pipeline (same five firms)

```bash
python -m ffb_webminer prepare --config config/pilot.yaml
python -m ffb_webminer discover-snapshots --config config/pilot.yaml
python -m ffb_webminer crawl --config config/pilot.yaml
python -m ffb_webminer validate --config config/pilot.yaml
python -m ffb_webminer report --config config/pilot.yaml
python scripts/refresh_corpus_outputs.py
python scripts/run_manual_corpus_validation.py
python scripts/check_pilot_consistency.py
python scripts/build_pilot_release.py
```

---

## Tests

```bash
pytest tests/ -q
```

Expected: all tests pass (47+).
