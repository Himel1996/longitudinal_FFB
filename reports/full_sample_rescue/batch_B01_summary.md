# Batch B01 Summary — COMPLETED_WITH_LIMITATIONS

**Generated:** 2026-08-28 06:49 UTC  
**Branch:** `rescue_pass` @ `83f14f0` (plus uncommitted rescue-layer fetcher-lifecycle fix)  
**Firms:** 2 (Peter-Lacke), 11 (Harting), 12 (Rossmann)  
**Status:** `COMPLETED_WITH_LIMITATIONS`  
**Acceptance:** PASS (B01 invariants)  
**B02:** not started

---

## Latest resume (2026-08-28)

Transport gate: **2 consecutive PREFLIGHT_OK** (replay 100%, then 100%) before crawl.

Command:

```bash
PYTHONUNBUFFERED=1 python -u scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --resume-from crawl --firms 2 11 12 --resume \
  2>&1 | tee -a data/interim/full_sample_rescue/batch_B01.log
```

Prior crawl had completed page fetches, then extract crashed (`sqlite3.ProgrammingError: Cannot operate on a closed database`) because the rescue fetcher was closed before iframe/redirect expansion. Rescue-layer fix only: keep the cache DB open through extract; reopen if closed. Tests: **56 passed**. Core / tolerances / `full_sample_v1` unchanged.

Pipeline: `crawl complete: pages=2262` → `extract complete: observations=12` → `compare complete: decisions=13` → `acceptance complete`.

This resume: 2 circuit OPEN → cooldown 294s → CLOSED. Harting FETCHED stayed **103** (cache reuse; no extra completed-page refetch).

---

## Fetch / cache (final)

| Firm | Discovery selections | FETCHED | FETCH_FAILED_RESUMABLE | Notes |
|------|----------------------|---------|------------------------|-------|
| 2 Peter-Lacke | 4 | 103 | 2 | Started and finished this resume |
| 11 Harting | 4 | 103 | 0 | Unchanged vs prior pause |
| 12 Rossmann | 4 | 101 | 0 | Completed remaining pages |
| 10 B. Braun (cache/discovery) | 5 | 152 | 3 | Not recrawled |

- HTML cache files: **459**
- Remaining resumable (B01): Peter-Lacke `company.html` @ 20130425050731; GTM iframe @ 20180304082313 (`transport_connection_refused`)
- Parent SHA unchanged: `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`
- Validated core diff: NONE
- Decisions backup: `data/interim/full_sample_rescue/rescue_comparison_decisions_B01.csv`

### Selected rescue snapshots (unchanged)

| Firm | Timepoint | Timestamp | Domain |
|------|-----------|-----------|--------|
| 2 | pre_pre_event | 20110806103010 | peter-lacke.com |
| 2 | pre_event | 20130425050731 | peter-lacke.com |
| 2 | event | 20150709054523 | peter-lacke.com |
| 2 | post_post_event | 20190826043633 | peter-lacke.com |
| 11 | pre_pre_event | 20110713070400 | harting.de |
| 11 | pre_event | 20120621013032 | harting.de |
| 11 | post_event | 20180304082313 | harting.com |
| 11 | post_post_event | 20190724072426 | harting.com |
| 12 | pre_pre_event | 20170422114716 | rossmann.de |
| 12 | pre_event | 20190627052815 | rossmann.de |
| 12 | post_event | 20230629084845 | rossmann.de |
| 12 | post_post_event | 20250701125246 | rossmann.de |

Peter-Lacke has no `post_event` selection (4 of 5 timepoints).

---

## Decisions (13)

| Firm | Timepoint | Decision | Reason |
|------|-----------|----------|--------|
| 2 | pre_pre_event | retain_original | rescue not better German |
| 2 | pre_event | retain_original | rescue not better German |
| 2 | event | retain_original | rescue not better German |
| 2 | post_event | remain_unavailable | no selected rescue snapshot |
| 2 | post_post_event | **replace_with_rescue** | German where original lacked (4178 tokens) |
| 11 | pre_pre_event | **replace_with_rescue** | German where original lacked |
| 11 | pre_event | **replace_with_rescue** | German eligible, forced sensitivity (temporal very_low, 375d) |
| 11 | post_event | **replace_with_rescue** | German where original lacked |
| 11 | post_post_event | **replace_with_rescue** | German where original lacked |
| 12 | pre_pre_event | **replace_with_rescue** | German where original lacked (sensitivity) |
| 12 | pre_event | **replace_with_rescue** | better German within equal/better temporal (sensitivity) |
| 12 | post_event | **replace_with_rescue** | German where original lacked |
| 12 | post_post_event | **replace_with_rescue** | German where original lacked |

- Replaced: **9**
- Retained original: **3**
- Remain unavailable: **1**
- Forced sensitivity: **1** (Harting pre_event)
- No `archive_unavailable` conversions

---

## Coverage before → after (B01 firms)

Parent `german_longitudinal_ready`: 10 firms. After B01, `german_longitudinal_ready_primary` **12**, extended **13**.

| Firm | Parent ready | After primary | After extended | DE branding pages | Notes |
|------|--------------|---------------|----------------|-------------------|-------|
| 2 Peter-Lacke | FALSE (no post German) | **TRUE** | **TRUE** | 48 → 66 | post_post rescue; pre/event keep parent |
| 11 Harting | FALSE (0 German) | **TRUE** | **TRUE** | 0 → 75 | newly longitudinal-ready; pre_event sensitivity |
| 12 Rossmann | FALSE | FALSE | **TRUE** | 15 → 94 | post rescued to primary; pre stays sensitivity |

B01 German-eligible observations: 4 → 12. B01 `tokens_de`: 9,803 → 67,116.

Newly ready vs parent: primary **firm 2 + firm 11**; extended also **firm 12**.

---

## Batch acceptance checks

| Check | Result |
|-------|--------|
| No legal pages in DE branding corpus | PASS (0 legal category / URL hits; 1034 DE branding pages) |
| No within-timepoint canonical URL duplicates | PASS (0 extra dups in DE branding; B01 `duplicate_content_flag` all False) |
| German corpus remains German-only | PASS (`detected_language`/`text_language` = de for all 1034) |
| Token counts reconcile | PASS (obs `tokens_de` 455377 vs DE page tokens 455142; **same 235 residual as parent**) |
| Transport failures not converted to `archive_unavailable` | PASS |
| Snapshot tolerances not relaxed | PASS (Harting pre_event kept very_low → sensitivity, not promoted) |
| Persisted B01 selections not overwritten | PASS (timestamps above unchanged) |
| Non-B01 firms vs parent (overlapping coverage cols) | PASS (equal) |
| Parent release SHA | PASS `c54fc356…dd03352b6f34eee55304022d6c27` |
| Validated core unchanged | PASS |

Limitations (why not `COMPLETED`): 2 resumable fetch failures remain; Peter-Lacke `post_event` still unavailable; 3 Peter-Lacke timepoints retain parent; Rossmann not primary-ready; Harting pre_event is sensitivity-only.

### Sequential-compare note (not a B01 methodology fail)

Compare applies **current-batch decisions onto parent**. Processed corpora for firm 10 therefore match parent (English `bbraun.com`), not the smoke rescue. **Discovery SQLite (5× `bbraun.de`) and page cache (152 FETCHED) are intact.** Re-apply B. Braun (and later batches) at final assembly from persisted state; do not recrawl. B01 decisions copied to `rescue_comparison_decisions_B01.csv` so a later batch cannot lose them if the live decisions file is overwritten.

---

## Special-case notes

None in B01.

---

## Integrity

- Parent: unchanged
- Core (`pipeline` / `crawl` / `archive` / `extract` / `quality`, `config/full_sample.yaml`): unchanged
- Rescue-layer only: fetcher close deferred until after extract; SQLite store reconnects after close
