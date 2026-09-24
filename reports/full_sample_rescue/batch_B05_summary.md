# Batch B05 Summary — COMPLETED_WITH_LIMITATIONS

**Generated:** 2026-09-23 ~03:49 UTC  
**Firms:** 21 (Freudenberg), 22 (STIHL), 24 (Viessmann)  
**Status:** `COMPLETED_WITH_LIMITATIONS`  
**Acceptance:** PASS (pipeline finished)  
**B01–B04:** not reprocessed  
**B06:** not started

---

## Keep-trying campaign

2× `PREFLIGHT_OK` each round → `--resume --resume-from discover` until acceptance.  
Log: `reports/full_sample_rescue/batch_B05_keeptrying.log`  
Completed round 4 (`keeptrying_exit=0`, ~6.75h wall clock).

### Final fetch counts

| Firm | FETCHED | Resumable |
|------|---------|-----------|
| 21 Freudenberg | **50** | 1 |
| 22 STIHL | **102** | 1 |
| 24 Viessmann | **79** | 8 |

Discovery selected: Freudenberg 3, STIHL 4, Viessmann 4.  
No `archive_unavailable`. Parent SHA unchanged: `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`

---

## Decisions (13)

| Decision | Count |
|----------|------:|
| replace_with_rescue | 6 |
| add_as_sensitivity_alternative | 3 |
| retain_original | 2 |
| remain_unavailable | 2 |

Roles: sensitivity 11 / excluded 2 / primary 0 (forced sensitivity / entity-change scope).  

Decisions backup: `data/interim/full_sample_rescue/rescue_comparison_decisions_B05.csv`

---

## Coverage before → after

| Firm | primary | extended | rescue_improved |
|------|---------|----------|-----------------|
| 21 Freudenberg | FALSE → **FALSE** | FALSE → **TRUE** | TRUE |
| 22 STIHL | FALSE → **FALSE** | FALSE → **TRUE** | TRUE |
| 24 Viessmann | FALSE → **FALSE** | FALSE → **FALSE** | TRUE |

Limitations: all three remain primary-FALSE (expected sensitivity/entity-change special cases). Freudenberg + STIHL gained extended readiness; Viessmann still not longitudinally ready.

---

## Integrity

| Check | Result |
|-------|--------|
| Parent SHA unchanged | PASS |
| Transport failures remain resumable | PASS |
| B06 not started | PASS |

---

## STOP

**B05 batch complete** (`COMPLETED_WITH_LIMITATIONS`).  
Do **not** start B06 without an explicit request.  
Remaining candidates: 5 (MSF), 27 (Douglas), 30 (Oetker).
