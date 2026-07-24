# Pilot v1.3 Readiness Report

**Release:** Pilot v1.3  
**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Run date:** 2026-07-24  
**Release bundle:** `data/releases/pilot_v1_3/`  
**Predecessor archive:** `data/archive/pilot_v1_2_pre_v1_3/`

---

## Executive summary

Pilot v1.3 makes the five-firm pipeline scaling-ready:

1. Within-observation URL/content deduplication (www/non-www fixed)
2. Hybrid language handling with German-only primary NLP corpus
3. Reserved-slot crawl prioritization for branding pages

**Ready to share with Christian:** **YES**  
**Ready to scale to remaining 25 firms:** **YES, after Christian confirms v1.3**  
(`config/full_sample.yaml` is prepared; do not run until confirmed)

---

## Key counts

| Metric | Value |
|--------|-------|
| Duplicate pages removed from branding | 83 |
| Duplicate tokens removed | 8,640 |
| MYRENNE pre_event branding tokens (v1.2 → v1.3) | 6,639 → 3,682 |
| Branding pages (all languages) | 235 |
| Branding pages (German) | 230 |
| Branding pages (English) | 2 |
| Branding pages (other/unknown) | 3 |
| German primary eligible observations | 14 |
| German text-analysis eligible observations | 16 |
| Consistency checks | PASSED |
| Tests | 66 passed |

---

## Suggested review files

1. `duplicate_summary.csv`
2. `branding_corpus_observations_primary.csv`
3. `branding_corpus_pages_de.csv` / `_en.csv` / `_all_languages.csv`
4. `crawl_priority_summary.csv`
5. `manual_scaling_validation.csv`
6. `reports/v1_3_change_report.md`
