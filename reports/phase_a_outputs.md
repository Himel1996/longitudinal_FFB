# Phase A Outputs — `full_sample_v1`

**Generated:** 2026-07-29 06:39 UTC  
**Mode:** metadata / reporting only  
**Extraction pipeline modified:** **No**  
**Crawler modified:** **No**  
**Existing corpus CSV contents modified:** **No**

## Files created

- `data/releases/full_sample_v1/data/full_sample_branding_corpus_observations_sensitivity_de.csv`
- `data/output/full_sample_branding_corpus_observations_sensitivity_de.csv`
- `data/releases/full_sample_v1/data/firm_longitudinal_coverage.csv`
- `data/output/firm_longitudinal_coverage.csv`
- `data/releases/full_sample_v1/reports/firm_longitudinal_coverage_summary.md`
- `reports/firm_longitudinal_coverage_summary.md`
- `reports/phase_a_outputs.md`
- `data/releases/full_sample_v1/reports/phase_a_outputs.md`

## Observation counts

| Corpus | Language scope | N |
|--------|----------------|--:|
| Primary | German only | 51 |
| Sensitivity | All languages | 84 |
| Sensitivity (German) | German only | 61 |

German longitudinal-ready firms: **10** / 30

## Validation checks

| Check | Status |
|-------|--------|
| German sensitivity export only German-eligible | PASS |
| Observation counts reconcile with release | PASS |
| Existing sensitivity_all file unchanged | PASS |
| No observation regeneration | PASS |
| No crawl / extraction rerun | PASS |

All validation checks passed.

## Documentation updates (labels only)

- `reports/full_sample_quality_report.md`
- `data/releases/full_sample_v1/reports/full_sample_quality_report.md`
- `reports/full_sample_readiness.md`
- `data/releases/full_sample_v1/reports/full_sample_readiness.md`
- `reports/full_sample_reproducibility.md`
- `data/releases/full_sample_v1/reports/full_sample_reproducibility.md`

## Confirmation

Phase A produces additional analytical exports from the frozen `full_sample_v1` release.
It does **not** alter validated extraction logic, crawler behavior, snapshot selection,
deduplication, language detection, tokenization, governance/branding extraction, or
observation eligibility rules.
