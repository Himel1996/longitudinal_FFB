# Full-Sample Reproducibility

**Run ID:** `508f1903-71e7-4aab-aba6-000fed4d8b7d`  
**Run date:** 2026-07-25  
**Git commit:** `cbdd849197cb139b7e3c228c0ec962d8ed16d254`  
**Predecessor:** `data/releases/pilot_v1_4_1/`  
**Config hash (SHA-256):** `2e3c987c0cb13b2c248d75275d4cacf16370741d791085b43f65079a9622c58b` (`config/full_sample.yaml`)

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
```

## Baseline freeze

See `reports/full_sample_baseline_freeze.md`.

## Rebuild (batched)

```bash
export PYTHONPATH=src

# Keep data/interim/cdx and data/interim/html
rm -rf data/output && mkdir -p data/output data/interim/full_sample_batches

python -m ffb_webminer prepare --config config/full_sample.yaml

scripts/run_full_sample_batch.sh 01_firms_1_5 1 2 3 4 5
scripts/run_full_sample_batch.sh 02_firms_6_10 6 7 8 9 10
scripts/run_full_sample_batch.sh 03_firms_11_15 11 12 13 14 15
scripts/run_full_sample_batch.sh 04_firms_16_20 16 17 18 19 20
scripts/run_full_sample_batch.sh 05_firms_21_25 21 22 23 24 25
scripts/run_full_sample_batch.sh 06_firms_26_30 26 27 28 29 30

# If QC fails, repair the offending firm(s) then re-gate:
# scripts/run_full_sample_batch.sh repair_firm_N N
python scripts/full_sample_batch_qc.py --batch-label final_gate

python scripts/run_full_sample_stratified_validation.py --config config/full_sample.yaml
python scripts/run_manual_corpus_validation.py --config config/full_sample.yaml
python scripts/run_manual_scaling_validation.py --config config/full_sample.yaml
python scripts/check_pilot_consistency.py --config config/full_sample.yaml
```

Batch logs/QC JSON: `data/interim/full_sample_batches/`.

## Outputs

Working copies: `data/output/full_sample_*.csv`  
Release bundle: `data/releases/full_sample_v1/`

## Tests

```bash
pytest tests/ -q
```
