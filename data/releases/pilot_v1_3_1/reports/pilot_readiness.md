# Pilot v1.3.1 Readiness Report

**Release:** Pilot v1.3.1  
**Run ID:** `6f4f1dd0-8f2a-42ca-ae1d-7f3067b47fc9`  
**Run date:** 2026-07-24  
**Git commit:** `565da6bfd8969793d64c80a4d2d68850a25e4191`  
**Release bundle:** `data/releases/pilot_v1_3_1/`  
**Predecessor archive:** `data/archive/pilot_v1_3_pre_final_priority_rebuild/`

---

## Executive summary

Pilot v1.3.1 is the clean, code-synchronized rebuild of the accepted v1.3 scaling architecture, with legal-path demotion applied **during** crawl.

**Ready to share with Christian:** **YES**  
**Definitive scaling baseline for `config/full_sample.yaml`:** **YES**  
**Run remaining 25 firms yet:** **NO — wait for Christian confirmation**

---

## Key counts

| Metric | Value |
|--------|-------|
| Branding pages (all languages) | 249 |
| Branding pages (German) | 243 |
| Branding pages (English) | 2 |
| Duplicate pages flagged | 86 |
| Duplicate tokens removed | 8,912 |
| German primary observations | 14 |
| Sensitivity observations | 16 |
| Legal pages consuming reserved About slots | 0 |
| Consistency checks | PASSED |
| Tests | 66 passed |
| Manifest ↔ code git sync | PASSED |

---

## Suggested review files

1. `reports/v1_3_1_change_report.md`
2. `crawl_priority_summary.csv`
3. `duplicate_summary.csv`
4. `branding_corpus_observations_primary.csv`
5. `manual_scaling_validation.csv`
6. `pages.csv` (filter `/unternehmen/` + impressum/agb)
