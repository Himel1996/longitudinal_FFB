# Family Firm Branding in Transition — Archived Web Pipeline

Longitudinal web-mining pilot for research on whether structural breaks in family firms are associated with recalibration of communicated family-branding signals on corporate websites.

## Research scope

This repository implements **data collection only** (not dictionary scoring). It measures communicated website signals from Internet Archive snapshots at five relative time points per firm.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Full pilot (first 5 firms from CSV)
python -m ffb_webminer run --config config/pilot.yaml

# Single firm validation (e.g. rank 5 = MSF-VATHAUER)
python -m ffb_webminer run --config config/pilot.yaml --firm-id 5

# Optional: homepage visual extraction (requires Playwright)
pip install -e ".[dev,visual]"
playwright install chromium
python -m ffb_webminer visuals --config config/pilot.yaml
```

## CLI commands

| Command | Description |
|---------|-------------|
| `prepare` | Load firms from CSV, build firm × timepoint grid |
| `discover-snapshots` | Query CDX API, select snapshots |
| `crawl` | Crawl archived pages and extract text/metadata |
| `extract` | Alias for `crawl` |
| `visuals` | Optional Playwright homepage color/font module |
| `report` | Quality summary, manual validation sample, manifest |
| `run` | Execute full pipeline |

## Temporal validity

Snapshot selection applies structured event-date metadata, temporal fit scoring, and adjacent-period checks. See [`reports/temporal_validity_report.md`](reports/temporal_validity_report.md) after running `discover-snapshots` or `run`.

Event-date overrides for the pilot live in [`config/event_dates.yaml`](config/event_dates.yaml) (e.g. MYRENNE April 2012).

## Outputs

| File | Description |
|------|-------------|
| `data/output/firms.csv` | Input firm/event metadata |
| `data/output/snapshots.csv` | One row per firm × timepoint (incl. future/unavailable) |
| `data/output/pages.csv` | Page-level crawl and extraction results |
| `data/output/quality_summary.csv` | Coverage by firm and timepoint |
| `data/output/manual_validation_sample.csv` | Human review sample |
| `data/output/homepage_visuals.csv` | Optional visual extraction |
| `data/output/run_manifest.json` | Config, versions, counts |
| `reports/pilot_quality_report.md` | Markdown quality report |

Raw HTML cached under `data/interim/html/`; CDX responses under `data/interim/cdx/`.

## Configuration

Edit `config/pilot.yaml` for snapshot selection rules, crawl limits, branding path heuristics, and quality thresholds. No source-code edits required for normal runs.

## Architecture

- **Decision C:** Modern independent pipeline; ARGUS kept unmodified in `external/ARGUS` as reference only.
- See [`reports/architecture_decision.md`](reports/architecture_decision.md) and [`reports/argus_technical_assessment.md`](reports/argus_technical_assessment.md).

## ARGUS citation

If referencing the upstream scraper methodology:

> Kinne, J., Lenz, D., & Wurst, J. (2020). ARGUS: A web scraping tool. *Scientometrics*. https://doi.org/10.1007/s11192-020-03726-9

`external/ARGUS` is GPLv3 and is not modified or redistributed as part of this pipeline.

## Tests

```bash
pytest -q
make test
```

## License

Pipeline code in `src/` is MIT-licensed unless otherwise specified. See `external/ARGUS/LICENSE` for the ARGUS reference copy.
