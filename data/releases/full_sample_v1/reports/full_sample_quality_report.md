# Full-Sample Quality Report

**Run ID:** `508f1903-71e7-4aab-aba6-000fed4d8b7d`  
**Run date:** 2026-07-25  
**Git commit:** `cbdd849197cb139b7e3c228c0ec962d8ed16d254`  
**Config:** `config/full_sample.yaml`  
**Predecessor:** `data/releases/pilot_v1_4_1/`  
**Release data:** `data/releases/full_sample_v1/`

## Scope

30-firm extraction from the accepted `pilot_v1_4_1` scaling baseline. Batches of 5 firms with post-batch QC gates. CDX/HTML caches reused.

## Coverage

| Metric | Value |
|--------|------:|
| Firms completed | 30 |
| Observations (firm × timepoint) | 150 |
| Snapshots selected | 100 |
| Beyond tolerance | 45 |
| Future unavailable | 4 |
| Event unavailable | 1 |
| Pages fetched (rows) | 2,073 |
| HTTP 200 | 1,790 |
| Usable for analysis | 1,756 |

### Observation recommendations

| Recommendation | N |
|----------------|--:|
| include | 77 |
| sensitivity_analysis | 21 |
| exclude | 50 |
| exclude_duplicate_capture | 2 |

## Corpora

| Metric | Value |
|--------|------:|
| Branding pages (all languages) | 1,376 |
| Branding pages (DE) | 862 |
| Branding token sum | 692,429 |
| Tokens DE sum | 398,064 |
| Primary NLP observations (German only) | 51 |
| Sensitivity NLP observations (all languages) | 84 |
| Sensitivity NLP observations (German only) | 61 |
| German-text-eligible observations | 61 |
| Text-analysis-eligible observations | 84 |

### Language distribution (branding all-language pages)

| Language | N |
|----------|--:|
| de | 864 |
| en | 507 |
| unknown | 5 |

## Branding observation corpora (language scope)

| Corpus | File | Language scope |
|--------|------|----------------|
| Primary | `full_sample_branding_corpus_observations_primary.csv` | **German only** |
| Sensitivity | `full_sample_branding_corpus_observations_sensitivity.csv` | **All languages** |
| Sensitivity (German) | `full_sample_branding_corpus_observations_sensitivity_de.csv` | **German only** |

Phase A added the German sensitivity export and firm longitudinal coverage tables without
modifying extraction outputs.

## Governance

| Metric | Value |
|--------|------:|
| Governance metadata pages | 27 |
| Governance observation rows | 150 |

## Deduplication

| Metric | Value |
|--------|------:|
| Duplicate summary rows | 333 |
| Tokens removed | 97,840 |

## Reserved-slot / crawl priority

| Reserved category selected | N |
|----------------------------|--:|
| company_about | 144 |
| homepage | 100 |
| values_responsibility | 20 |
| history_heritage | 16 |
| management_leadership | 12 |

High-priority pages fetched (tier 1, rebuilt from page fields): **804**  
Secondary (tier 2): **366** · Broad (tier ≥3): **903**

Final QC gate: **PASS** (0 invariant failures), including after Canyon `terms-conditions` legal-path demotion repair.

## Archive / fetch failures (top)

| Reason | N |
|--------|--:|
| Connection refused | 128 |
| HTTP 404 | 97 |
| Connection reset | 2 |
| HTTP 500 | 2 |
| HTTP 400 / 410 / 429 / 521 | 1 each |

Failures are retained in `pages.csv` (not silently dropped).

## Batch QC

| Batch | Firms | Result |
|-------|------:|--------|
| 01 | 1–5 | PASS |
| 02 | 6–10 | PASS |
| 03 | 11–15 | PASS |
| 04 | 16–20 | PASS |
| 05 | 21–25 | PASS |
| 06 | 26–30 | FAIL → repaired (Canyon terms) |
| 06b | 28 | PASS |
| final_gate | 1–30 | PASS |
