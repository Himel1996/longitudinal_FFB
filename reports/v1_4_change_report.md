# Pilot v1.4 Change Report

**Date:** 2026-07-24  
**Release:** `data/releases/pilot_v1_4/`  
**Predecessor:** `data/archive/pilot_v1_3_1_pre_v1_4/`  
**Run ID:** `ab33b6f5-06a8-4981-a805-65bf3f6b3516`  
**Git commit:** `1a1d7ba1832e780aa19be2804c996964e61ec35a`

## Purpose

Fresh top-5 rebuild so you can verify that the accepted scaling pipeline (deduplication, hybrid language handling, reserved-slot prioritization, legal-path demotion) behaves as intended **before** running `config/full_sample.yaml` for all 30 firms.

No new research features were added for v1.4; this is a verification rebuild from cleared crawl/corpus outputs.

## Rebuild procedure

1. Archived v1.3.1 → `data/archive/pilot_v1_3_1_pre_v1_4/`
2. Cleared `data/output` crawl/corpus/snapshot artifacts (kept CDX + HTML caches)
3. Ran `prepare` → `discover-snapshots` → `crawl` → validate/export → reports
4. Manual corpus + scaling validation samples
5. Consistency checks + unit tests
6. Release bundling with git-commit sync enforcement

## Firms

1. BLUE MOON COMMUNICATION CONSULTANTS GMBH  
2. PETER-LACKE HOLDING GMBH  
3. ANLAGENTECHNIK LEICHTLE GMBH  
4. MYRENNE GMBH  
5. MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG  

## Key results

| Metric | Value |
|--------|-------|
| Pages | 394 |
| Usable pages | 384 |
| Branding pages (all / de / en / other) | 249 / 243 / 2 / 4 |
| German primary observations | 14 |
| Sensitivity observations | 16 |
| Duplicate rows / tokens removed | 86 / 8,912 |
| Branding token sum | 67,967 |
| Legal pages consuming reserved About slots | 0 |
| Foreign pages consuming reserved slots | 0 |
| Cross-timepoint content groups preserved | 61 |
| Consistency checks | PASSED |
| Tests | 66 passed |
| Manifest ↔ code git sync | PASSED |

## Verification focus (for you)

Suggested manual checks in `data/releases/pilot_v1_4/data/`:

1. `pages.csv` — reserved-slot fields; legal `/unternehmen/` paths not under reserved About slots  
2. `duplicate_summary.csv` — within-timepoint duplicates only  
3. `branding_corpus_observations_primary.csv` — German-only primary NLP corpus  
4. `branding_corpus_pages_de.csv` vs `_en.csv` / `_all_languages.csv`  
5. `crawl_priority_summary.csv` — high-priority vs secondary/broad mix  
6. `manual_scaling_validation.csv` — focused review sample  
7. `observation_text_summary.csv` — token sums and language tallies  

## Scaling

**Do not run the remaining 25 firms until this top-5 verification is accepted.**  
Baseline config for later scaling remains `config/full_sample.yaml`.
