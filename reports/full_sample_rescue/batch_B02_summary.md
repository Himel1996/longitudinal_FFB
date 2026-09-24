# Batch B02 Summary — COMPLETED

**Generated:** 2026-09-09 ~12:36 UTC  
**Branch:** `rescue_pass` @ `79d2df9` (`batch1`)  
**Firms:** 14 (CLAAS), 15 (Faber-Castell), 16 (Henkel)  
**Status:** `COMPLETED`  
**Acceptance:** PASS (B02 invariants)  
**B03:** not started  
**Firm 10 (B. Braun):** not recrawled

---

## Local context

This laptop had **no** prior page/discovery SQLite/HTML cache for B02 (empty `html/`, missing state DBs). B02 ran fresh under `--resume` semantics after a transport gate.

Parent SHA (unchanged):

`c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`

Validated core / `config/full_sample.yaml` / `data/releases/full_sample_v1/`: **unchanged**.

Tests before run: **56 passed** (`test_rescue_phase_b`, `test_rescue_transport`, `test_rescue_discovery_state`).

---

## Transport gate

| Attempt | Result | Notes |
|---------|--------|-------|
| Preflight 1 | FAIL | CDX 0/2 (503 + timeout); replay 5/5 |
| Preflight 2 (after ~3 min) | **PREFLIGHT_OK** | CDX 1/2; replay 5/5 |
| Preflight 3 (after ~2.5 min) | **PREFLIGHT_OK** | CDX 2/2; replay 5/5 |

Embedded preflight inside an initial `--stage full --resume` then failed (connection refused spike). After cool-down, B02 continued with:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --resume --resume-from discover \
  --firms 14 15 16 \
  2>&1 | tee -a data/interim/full_sample_rescue/batch_B02_run.log
```

Pipeline finished: discover → crawl → extract → compare → report → **acceptance complete**.

---

## Discovery (15/15 selected)

| Firm | Timepoint | Timestamp | Domain |
|------|-----------|-----------|--------|
| 14 CLAAS | pre_pre_event | 20150624111706 | claas-gruppe.com |
| 14 | pre_event | 20170707063719 | claas-gruppe.com |
| 14 | event | 20190716022107 | claas-gruppe.com |
| 14 | post_event | 20210701104556 | claas-gruppe.com |
| 14 | post_post_event | 20230704073533 | claas-gruppe.com |
| 15 Faber-Castell | pre_pre_event | 20130630131120 | faber-castell.de |
| 15 | pre_event | 20150629012847 | faber-castell.de |
| 15 | event | 20170603221218 | faber-castell.de |
| 15 | post_event | 20190625095359 | faber-castell.de |
| 15 | post_post_event | 20210624222513 | faber-castell.de |
| 16 Henkel | pre_pre_event | 20160703113103 | henkel.de |
| 16 | pre_event | 20180625122911 | henkel.de |
| 16 | event | 20200630112845 | henkel.de |
| 16 | post_event | 20220701113824 | henkel.de |
| 16 | post_post_event | 20240701021813 | henkel.de |

All five timepoints selected per firm. Seeds used historical/locale candidates (`claas-gruppe.com`, `faber-castell.de`, `henkel.de`) — no parent-domain fallback replacement of successful rescue snapshots.

---

## Fetch / cache (final)

| Firm | Discovery selections | FETCHED | FETCH_FAILED_RESUMABLE |
|------|----------------------|---------|------------------------|
| 14 CLAAS | 5 | 89 | 12 |
| 15 Faber-Castell | 5 | 88 | 13 |
| 16 Henkel | 5 | 92 | 15 |
| **Total** | **15** | **269** | **40** |

- HTML cache files: **269**
- Dominant resumable error: `transport_connection_refused` (39); `other` (1, HTTP 500)
- Circuit breaker operated throughout (many OPEN → cooldown ~294s → HALF_OPEN probes → CLOSED). Health-probe failures extended cooldown when needed. Run did **not** exit `RESCUE_PAUSED_TRANSPORT_UNSTABLE`.
- Cache/state preserved under `data/interim/full_sample_rescue/{html,state}/`
- Decisions backup: `data/interim/full_sample_rescue/rescue_comparison_decisions_B02.csv`

---

## Decisions (15)

| Firm | Timepoint | Decision | Reason / tokens_de (orig → rescue) |
|------|-----------|----------|-------------------------------------|
| 14 | pre_pre_event | **replace_with_rescue** | German where original lacked (0 → 11259) |
| 14 | pre_event | **replace_with_rescue** | German where original lacked (0 → 11560) |
| 14 | event | rejected_insufficient_text | no_branding_pages |
| 14 | post_event | **replace_with_rescue** | German where original lacked (0 → 11143) |
| 14 | post_post_event | **replace_with_rescue** | German where original lacked (0 → 12847) |
| 15 | pre_pre_event | **replace_with_rescue** | better German (678 → 4394) |
| 15 | pre_event | **replace_with_rescue** | better German (983 → 5951) |
| 15 | event | rejected_insufficient_text | no_branding_pages |
| 15 | post_event | **replace_with_rescue** | German where original lacked (0 → 5649) |
| 15 | post_post_event | **replace_with_rescue** | German where original lacked (0 → 7164) |
| 16 | pre_pre_event | **replace_with_rescue** | German where original lacked (0 → 8084) |
| 16 | pre_event | **replace_with_rescue** | German where original lacked (0 → 9676) |
| 16 | event | **replace_with_rescue** | German where original lacked (0 → 17645) |
| 16 | post_event | rejected_insufficient_text | no_branding_pages |
| 16 | post_post_event | **replace_with_rescue** | German where original lacked (0 → 16961) |

- **replace_with_rescue:** 12  
- **rejected_insufficient_text:** 3 (CLAAS event, Faber event, Henkel post_event)  
- **archive_unavailable / transport→unavailable:** 0  
- Forced sensitivity: 0  

Rescue corpus role: primary 11 / sensitivity 1 / excluded 3.

---

## Coverage before → after (B02 firms)

| Firm | Parent `german_longitudinal_ready` | After primary | After extended | Parent tokens_de | Rescue tokens_de |
|------|-------------------------------------|---------------|----------------|------------------|------------------|
| 14 CLAAS | FALSE | **TRUE** | **TRUE** | 0 | 46,809 |
| 15 Faber-Castell | FALSE | **TRUE** | **TRUE** | 1,661 | 23,158 |
| 16 Henkel | FALSE | **TRUE** | **TRUE** | 0 | 52,366 |

All three firms newly **primary-ready** and **extended-ready**.  
B02 firm German branding page tokens (processed DE corpus): **122,333** (obs `tokens_de` sum **122,333** — exact reconcile for these firms).

---

## Batch acceptance checks

| Check | Result |
|-------|--------|
| Parent SHA unchanged | PASS (`c54fc356…`) |
| Validated core unchanged | PASS (no diffs under pipeline/crawl/archive/extract/quality / full_sample.yaml / full_sample_v1) |
| Transport failures not converted to `archive_unavailable` | PASS |
| German DE branding corpus language | PASS (`text_language`/`detected_language` = de for 232 B02 pages) |
| Legal pages in DE branding corpus | PASS (0 legal/impressum category hits among B02 DE branding pages) |
| Token counts reconcile (B02 firms) | PASS (pages 122333 = obs 122333) |
| Authoritative selections survived | PASS (15/15 selected captures retained through compare) |
| No B. Braun / B03 execution | PASS |
| Snapshot tolerances / extraction methodology | PASS (unchanged; 3 timepoints correctly excluded for insufficient branding text) |

---

## Limitations / notes

- Intermittent Wayback **connection refused** caused frequent circuit opens; progress continued via cooldown + probes + page-level resume cache.
- Three observations remain without usable branding text (`rejected_insufficient_text`) but do not block longitudinal readiness because adjacent PRE/POST timepoints supply German material.
- `config/full_sample_rescue.yaml` was refreshed by the orchestrator with targeted-firm metadata (expected); not a methodology change.

---

## STOP

**B02 complete. Do not start B03.**  
Preserve `data/interim/full_sample_rescue/` cache and SQLite state for future resumes.
