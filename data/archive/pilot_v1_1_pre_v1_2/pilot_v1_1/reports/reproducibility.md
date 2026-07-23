# Pilot v1.1 Reproducibility

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Run date:** 2026-07-16  
**Git commit:** `7dffd85c38626862c14a2022a9fc5ff119772498`

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
playwright install chromium
```

Dependency note: v1.1 requires `lingua-language-detector`.

---

## Clean build

```bash
rm -rf data/output data/interim reports
mkdir -p data/output data/interim reports
```

---

## Full pipeline (five firms)

```bash
export PYTHONPATH=src
python -m ffb_webminer prepare --config config/pilot.yaml
python -m ffb_webminer discover-snapshots --config config/pilot.yaml
python -m ffb_webminer crawl --config config/pilot.yaml
python -m ffb_webminer validate --config config/pilot.yaml
python -m ffb_webminer report --config config/pilot.yaml
python -m ffb_webminer visuals --config config/pilot.yaml
```

Post-crawl corpus refresh (re-applies classification without re-fetching):

```bash
python scripts/refresh_corpus_outputs.py
python scripts/run_manual_corpus_validation.py
python scripts/check_pilot_consistency.py
python scripts/build_pilot_release.py
```

---

## Expected outputs

- `data/output/pages.csv` with classification and language fields
- `data/output/observation_text_summary.csv`
- `data/output/branding_corpus_pages.csv`
- `data/output/branding_corpus_observations_primary.csv`
- `data/output/branding_corpus_observations_sensitivity.csv`
- `data/output/governance_metadata_pages.csv`
- `data/output/governance_metadata_observations.csv`
- `data/output/manual_corpus_validation.csv`
- `data/output/quality_summary.csv`
- `data/releases/pilot_v1_1/`

---

## Tests

```bash
pytest tests/ -q
```

Expected: all tests pass (40+).
