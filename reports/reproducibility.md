# Pilot v1.0 Reproducibility Guide

**Release:** `data/releases/pilot_v1/`  
**Run ID:** `a48bc35c-844b-4358-afb4-290410db7f5d`  
**Run date:** 2026-07-15  
**Git commit:** `e1d11cb16d0b99309dae50f1893e2051e735fdae`

---

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,visual]"
playwright install chromium
```

Python **3.11+** required.

---

## Clean build (from fresh clone)

```bash
# Remove prior generated outputs (keep config + design docs)
rm -rf data/output/* data/interim/* data/releases/pilot_v1
mkdir -p data/output data/interim/{html,cdx,state,screenshots}

# Archive prior reports except design documentation
mkdir -p data/archive/previous_run/reports
mv reports/pilot_*.md reports/manual_validation_report.md \
   reports/temporal_validity_report.md reports/extraction_validation_report.md \
   reports/reproducibility.md data/archive/previous_run/reports/ 2>/dev/null || true
```

---

## Full pipeline (5 firms)

Run from repository root:

```bash
export PYTHONPATH=src

python -m ffb_webminer prepare --config config/pilot.yaml
python -m ffb_webminer discover-snapshots --config config/pilot.yaml
python -m ffb_webminer crawl --config config/pilot.yaml
python -m ffb_webminer validate --config config/pilot.yaml
python -m ffb_webminer report --config config/pilot.yaml
python -m ffb_webminer visuals --config config/pilot.yaml
```

**Notes:**
- `crawl` includes text extraction (multi-stage A→E).
- `validate` refreshes snapshot metadata, re-crawls, and exports analysis tables. For a single crawl pass, use:

```bash
python - <<'PY'
from pathlib import Path
from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline.runner import PipelineRunner
r = PipelineRunner(PipelineConfig.from_yaml(Path("config/pilot.yaml")), project_root=Path("."))
r.refresh_snapshot_metadata()
r.validate_and_export()
PY
```

---

## Manual validation

```bash
python scripts/run_manual_validation.py --config config/pilot.yaml
python scripts/check_pilot_consistency.py --config config/pilot.yaml
```

---

## Release bundle

```bash
python scripts/build_pilot_release.py --config config/pilot.yaml
```

---

## Expected outputs

| File | Expected |
|------|----------|
| `data/output/firms.csv` | 5 rows |
| `data/output/snapshots.csv` | 25 rows (5 firms × 5 timepoints) |
| `data/output/pages.csv` | ~350–450 page rows |
| `data/output/analysis_observations.csv` | 16 rows (include only) |
| `data/output/analysis_observations_sensitivity.csv` | 19 rows |
| `data/output/manual_validation_sample.csv` | 19 rows |
| `data/output/firm_coverage_matrix.csv` | 5 rows |
| `data/output/homepage_visuals.csv` | 20 rows (may include failed renders) |
| `data/output/run_manifest.json` | Run metadata + git commit |
| `data/output/validation_screenshots/` | 19 PNG files |
| `data/output/evidence/validation_screenshot_urls.json` | URL manifest |

---

## Package versions (pinned at release)

See `data/releases/pilot_v1/data/run_manifest.json` for runtime config.

Key packages (`pip freeze` excerpt):

```
ffb-webminer @ e1d11cb16d0b99309dae50f1893e2051e735fdae
pandas>=2.2,<3
trafilatura>=1.9,<2
readability-lxml>=0.8,<1
playwright>=1.44,<2
httpx>=0.27,<1
beautifulsoup4>=4.12,<5
lxml>=5.2,<6
```

Full lock: run `pip freeze > requirements-release.txt` after install.

---

## Runtime notes

- **Wayback availability:** Internet Archive returns intermittent `[Errno 61] Connection refused`. Config `crawl.retries: 5` mitigates this.
- **Playwright:** Required for modern JS-heavy homepages (~60% of validation observations).
- **MSF/Myrenne frames:** JS redirect + frameset expansion in `html_preprocess.py`; frame child fetches may need retry.
- **Crawl duration:** ~90–120 minutes for 5 firms (focused crawl, 25 pages/snapshot max).

---

## Verification

```bash
pytest -q
python scripts/check_pilot_consistency.py
```

All 31 tests should pass; consistency check should report **PASSED**.
