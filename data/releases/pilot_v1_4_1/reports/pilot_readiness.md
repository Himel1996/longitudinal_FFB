# Pilot v1.4.1 Readiness Report

**Release:** Pilot v1.4.1  
**Run ID:** `95bac495-6940-47be-b3ff-339fd97afa3e`  
**Run date:** 2026-07-24  
**Git commit:** `5a5fec78333d7baead292037b2be2a94f6733366`  
**Release bundle:** `data/releases/pilot_v1_4_1/`  
**Predecessor archive:** `data/archive/pilot_v1_4_pre_v1_4_1/`

---

## Executive summary

Pilot v1.4.1 is a **targeted acceptance-fix rebuild** addressing reserved-slot substring misclassification and zero-token usable non-Latin pages.

**Ready for your verification:** **YES**  
**Ready to scale remaining 25 firms:** **READY TO SCALE**  
**Config for later full sample:** `config/full_sample.yaml`

---

## Key counts

| Metric | Value |
|--------|-------|
| Firms | 5 |
| Pages | 394 |
| Branding pages (all / de / en / other) | 242 / 234 / 4 / 4 |
| German primary observations | 14 |
| Sensitivity observations | 16 |
| Duplicate pages / tokens | 93 / 9,456 |
| Legal reserved-slot consumption | 0 |
| Usable pages with zero analysis tokens | 0 |
| Consistency checks | PASSED |
| Tests | 81 passed |
| Manifest ↔ code git sync | PASSED |

---

## Suggested review files

1. `reports/v1_4_1_change_report.md`
2. `reports/release_acceptance_audit.md`
3. `data/pages.csv` (priority match + tokenization fields)
4. `data/branding_corpus_observations_primary.csv`
5. `data/crawl_priority_summary.csv`
6. `data/manual_scaling_validation.csv`
