# B. Braun Smoke Test — Phase B (Discovery-State Fix Rerun)

**Generated:** 2026-08-11 15:50 UTC  
**Branch:** `rescue_pass` @ `dd708dd0b726deaa56c6200975daab48893a873d` (+ rescue-layer fixes)  
**Firm:** 10 / B. BRAUN SE  
**Network:** Christian’s Mac default connection (no hotspot / no VPN)  
**Final status:** `SMOKE_TEST_PASSED`

---

## 1. Preflight attempts

| # | Timestamp (UTC) | CDX ok/fail | Replay ok/fail | Replay % | connection_refused | Result |
|---|-----------------|-------------|----------------|----------|--------------------|--------|
| 1 | 10:35:22 | 2/0 | 5/0 | 100% | 0 | `PREFLIGHT_OK` |
| 2 | 10:39:24 | 2/0 | 5/0 | 100% | 0 | `PREFLIGHT_OK` (consecutive #1) |
| 3 | 10:40:40 (embedded in `--stage full`) | 1/1 | 0/5 | 0% | 6 | `PREFLIGHT_FAILED_TRANSPORT` |
| 4 | 10:53:39 | 2/0 | 5/0 | 100% | 0 | `PREFLIGHT_OK` |
| 5 | 10:57:14 | 1/1 | 5/0 | 100% | 0 | `PREFLIGHT_OK` (consecutive #2) |
| 6–… | intermittent failures / waits | — | — | — | — | waited 10–15 min between clusters |
| cycle3 | 12:29 / 12:32 | 2/0 ; 2/0 | 5/0 ; 4/1 | 100% / 80% | 0 | **2× consecutive OK** → crawl |
| cycle4 | 13:07 / 13:10 | OK / OK | 100% | — | 0 | **2× consecutive OK** → crawl (parquet dtype crash) |
| cycle5 | 13:19 fail → 13:32 / 13:36 | fail then OK/OK | 40% then ≥80% | — | — | **2× consecutive OK** → crawl completed |

**Two consecutive healthy preflights achieved:** yes (multiple cycles). Crawl launched only after 2× `PREFLIGHT_OK`.

---

## 2. Persisted selections (authoritative)

All five survived the entire session (never erased by transport):

| Timepoint | Capture | Domain | Status |
|-----------|---------|--------|--------|
| pre_pre_event | 20160329173241 | bbraun.de | selected |
| pre_event | 20170701101545 | bbraun.de | selected |
| event | 20190704175027 | bbraun.de | selected |
| post_event | 20210706194317 | bbraun.de | selected |
| post_post_event | 20230701145021 | bbraun.de | selected |

---

## 3. Cache / crawl

| Metric | Value |
|--------|-------|
| Cache before this session | 74 FETCHED |
| Matching reusable (post + post_post) | ~49 |
| Orphan pre_event (bbraun.com @ 20160409012834) | 25 (not attributed to current selection) |
| Final FETCHED | **152** |
| FETCH_FAILED_RESUMABLE | **3** |
| HTML files | 152 |
| Circuit openings | many (transport hardening worked) |
| Cooldowns | 294s / 599s extended |
| Transport pauses | 1× `RESCUE_PAUSED_TRANSPORT_UNSTABLE` mid-crawl; resumed later |
| New network fetches | ~78 (74→152) |

---

## 4. Pipeline completion

`crawl complete` → `extract complete: observations=5` → `compare complete: decisions=5` → `acceptance complete`

Logic fixes applied during this session (rescue layer only):

1. **Parquet dtype normalize** — mixed str/float/int object columns after firm-filtered merges  
2. **Enrichment refresh on persisted discovery rows** — CDX rows lacked `analysis_eligible` / temporal fit  
3. **Same-timestamp enrichment re-persist allowed** — store previously rejected equal-distance updates  
4. **`extract` calls `validate()`** — `self.targeted` was empty and wiped firm-10 pages  

Validated core / tolerances / SSL / circuit thresholds unchanged.

---

## 5. Final five B. Braun observations

| Timepoint | Target | Capture date | Seed | Domain | Dist (d) | Fit | DE pages | DE tokens | Eligible | Decision |
|-----------|--------|--------------|------|--------|----------|-----|----------|-----------|----------|----------|
| pre_pre_event | 2015-07-01 | 2016-03-29 | bbraun.de/de.html | bbraun.de | 272 | low | 21 | 4827 | TRUE | **replace_with_rescue** |
| pre_event | 2017-07-01 | 2017-07-01 | bbraun.de/de.html | bbraun.de | 0 | high | 17 | 3091 | TRUE | **replace_with_rescue** |
| event | 2019-07-01 | 2019-07-04 | bbraun.de/de.html | bbraun.de | 3 | high | 19 | 4038 | TRUE | **replace_with_rescue** |
| post_event | 2021-07-01 | 2021-07-06 | bbraun.de/de.html | bbraun.de | 5 | high | 1 | 277 | TRUE | **replace_with_rescue** |
| post_post_event | 2023-07-01 | 2023-07-01 | bbraun.de/de.html | bbraun.de | 0 | high | 23 | 5795 | TRUE | **replace_with_rescue** |

All five: `rescue_primary_or_sensitivity = primary`, reason `rescue_provides_german_where_original_lacked`.

---

## 6. German tokens / readiness before vs after

| Metric | Before (parent) | After (rescue) |
|--------|-----------------|----------------|
| German-eligible observations | 0 | **5** (all timepoints) |
| German branding tokens | 0 | **18028** (reconciles primary) |
| `german_longitudinal_ready_primary` | FALSE | **TRUE** |
| `german_longitudinal_ready_extended` | FALSE | **TRUE** |
| `rescue_improved_coverage` | — | **TRUE** |
| pre German eligible | 0 | 2 |
| post German eligible | 0 | 2 |

---

## 7. Discovery persistence end-to-end (8 checks)

| # | Check | Result |
|---|-------|--------|
| 1 | Five bbraun.de selections survived crawl | **PASS** |
| 2 | Survived extract | **PASS** |
| 3 | Reached compare | **PASS** |
| 4 | `rescue_snapshots.csv` not overwritten by parent bbraun.com | **PASS** |
| 5 | Transport failures did not erase selections | **PASS** |
| 6 | Cached DE pages attributed only to matching captures | **PASS** (orphans unused) |
| 7 | Parent vs rescue observations distinct | **PASS** |
| 8 | Compare replacement policy applied | **PASS** (5× replace_with_rescue) |

**Prior discovery-overwrite bug: fixed end-to-end.**

---

## 8. Integrity

- Parent SHA unchanged: `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`
- `config/full_sample.yaml` unchanged  
- Validated core (`pipeline/`, `crawl/`, `archive/`, `extract/`, `quality/`) unchanged  
- Non-targeted firms unchanged in primary corpus counts  
- No legal pages in DE branding corpus (0 impressum/datenschutz matches)  
- No within-timepoint URL duplicates  
- DE branding pages: 81, language `de` only  
- Token sums reconcile: obs `tokens_de` sum = primary `tokens_de` sum = 18028  

---

## 9. Recommendation for remaining 18 firms

**A. READY_FOR_19_FIRM_RESCUE** — with operational caveats:

1. Require **two consecutive** `PREFLIGHT_OK` before each firm/batch crawl.  
2. Prefer `--resume-from crawl` after health gate (avoid burning the window on a third embedded preflight).  
3. Expect circuit open/cooldown/`RESCUE_PAUSED_TRANSPORT_UNSTABLE`; resume without clearing state.  
4. Do **not** run remaining firms until you explicitly approve.

If Wayback stays hostile on this network for long stretches, switch to a mobile hotspot before the 18-firm pass (ask before changing network).

---

## Resume command (reference)

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full --firms 10 --resume
```

---

## Notes

Discovery was **not** re-run after authoritative selections existed. Crawl used resume + page cache. Extract/compare/acceptance completed after rescue-layer fixes for parquet dtypes, enrichment re-persist, and extract targeting.
