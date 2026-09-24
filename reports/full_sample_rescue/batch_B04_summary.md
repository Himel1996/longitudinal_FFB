# Batch B04 Summary — COMPLETED

**Generated:** 2026-09-22 ~18:23 UTC  
**Branch:** `rescue_pass` @ `79d2df9` (+ uncommitted rescue-layer no-alias/CSV sync fix)  
**Firms:** 20 (Bahlsen), 23 (Vaillant), 25 (Birkenstock)  
**Status:** `COMPLETED`  
**Acceptance:** PASS (pipeline finished; release updated for targeted firms)  
**B05:** not started  
**B01–B03:** not reprocessed this run

---

## Keep-trying campaign (2026-09-21 08:24 → 2026-09-22 18:23 UTC)

Transport gate each round: **2 consecutive PREFLIGHT_OK**, then crawl `--resume --resume-from crawl`.  
Loop log: `reports/full_sample_rescue/batch_B04_keeptrying.log`  
Final round reached **acceptance complete** (`keeptrying_exit=0`).

### Final fetch counts

| Firm | FETCHED | Resumable |
|------|---------|-----------|
| 20 Bahlsen | **125** | 0 |
| 23 Vaillant | **102** | 1 |
| 25 Birkenstock | **130** | 2 |

No `archive_unavailable`. Cache/SQLite preserved.  
Parent SHA unchanged: `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`

---

## Discovery (14 selected)

| Firm | Selected | Notes |
|------|----------|-------|
| 20 Bahlsen | 5/5 | `thebahlsenfamily.com` |
| 23 Vaillant | 4/5 | `vaillant-group.com` — no `event` rescue alias |
| 25 Birkenstock | 5/5 | `birkenstock.com` |

---

## Decisions (14)

| Firm | replace_with_rescue | add_as_sensitivity_alternative |
|------|---------------------|--------------------------------|
| 20 Bahlsen | 5 | 0 |
| 23 Vaillant | 3 | 1 |
| 25 Birkenstock | 5 | 0 |

- **replace_with_rescue:** 13  
- **add_as_sensitivity_alternative:** 1  
- Roles: primary 12 / sensitivity 2  

Decisions backup: `data/interim/full_sample_rescue/rescue_comparison_decisions_B04.csv`

---

## Coverage before → after

| Firm | primary (before → after) | extended (before → after) | rescue_improved |
|------|--------------------------|---------------------------|-----------------|
| 20 Bahlsen | FALSE → **TRUE** | FALSE → **TRUE** | TRUE |
| 23 Vaillant | FALSE → **TRUE** | FALSE → **TRUE** | TRUE |
| 25 Birkenstock | FALSE → **TRUE** | FALSE → **TRUE** | TRUE |

---

## Integrity

| Check | Result |
|-------|--------|
| Parent SHA unchanged | PASS |
| Validated core unchanged | PASS |
| Transport failures remain resumable | PASS |
| B05 not started | PASS |

---

## STOP

**B04 batch complete.** Do **not** start B05 without an explicit request.
