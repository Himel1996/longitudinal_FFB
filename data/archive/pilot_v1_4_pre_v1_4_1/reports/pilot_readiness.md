# Pilot v1.4 Readiness Report

**Release:** Pilot v1.4  
**Run ID:** `ab33b6f5-06a8-4981-a805-65bf3f6b3516`  
**Run date:** 2026-07-24  
**Git commit:** `1a1d7ba1832e780aa19be2804c996964e61ec35a`  
**Release bundle:** `data/releases/pilot_v1_4/`  
**Predecessor archive:** `data/archive/pilot_v1_3_1_pre_v1_4/`

---

## Executive summary

Pilot v1.4 is a **from-scratch top-5 verification rebuild** of the accepted scaling pipeline (dedup, hybrid language, reserved slots, legal-path demotion).

**Ready for your verification:** **YES**  
**Ready to scale remaining 25 firms:** **NO — verify v1.4 first**  
**Config for later full sample:** `config/full_sample.yaml`

---

## Key counts

| Metric | Value |
|--------|-------|
| Firms | 5 |
| Pages | 394 |
| Branding pages (all / de) | 249 / 243 |
| German primary observations | 14 |
| Sensitivity observations | 16 |
| Duplicate pages / tokens | 86 / 8,912 |
| Legal reserved-slot consumption | 0 |
| Consistency checks | PASSED |
| Tests | 66 passed |
| Manifest ↔ code git sync | PASSED |

---

## Suggested review files

1. `reports/v1_4_change_report.md`
2. `data/pages.csv`
3. `data/branding_corpus_observations_primary.csv`
4. `data/crawl_priority_summary.csv`
5. `data/duplicate_summary.csv`
6. `data/manual_scaling_validation.csv`
