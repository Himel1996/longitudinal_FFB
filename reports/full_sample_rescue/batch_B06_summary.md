# Batch B06 Summary — COMPLETED_WITH_LIMITATIONS

**Generated:** 2026-09-23 ~18:15 UTC  
**Firms:** 5 (MSF), 27 (Douglas), 30 (Oetker)  
**Status:** `COMPLETED_WITH_LIMITATIONS`  
**Acceptance:** PASS (pipeline finished; `keeptrying_exit=0`)  
**Scope note:** Final Phase B batch. Firm 24 (Viessmann) was **not** reprocessed (already done in executed B05).  
**Final release assembly:** not started (awaiting authorization).

---

## Keep-trying campaign

2× `PREFLIGHT_OK` each round → `--resume --resume-from discover` until acceptance.  
Logs: `reports/full_sample_rescue/batch_B06_keeptrying.log`, `batch_B06_run.log`  

Early attempts with `--resume` alone re-ran embedded preflight and exited before discover; restarted with B05 pattern (`--resume --resume-from discover`) after gate.  
Restart loop: Round 1–4 with transport pauses; acceptance on Round 4 (~18:15 UTC; ~8h wall from restart).

### Final fetch counts

| Firm | FETCHED | Resumable |
|------|--------:|----------:|
| 5 MSF | **51** | 5 |
| 27 Douglas | **100** | 1 |
| 30 Oetker | **78** | 0 |

Discovery selected: MSF 4, Douglas 5, Oetker 3 (no Oetker `pre_pre_event` / `event` selection).  
Firm crawl order is string `firm_id` groupby (27 → 30 → 5), so MSF started after Douglas/Oetker progressed.  
Parent SHA unchanged: `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`

---

## Decisions (13)

| Decision | Count |
|----------|------:|
| replace_with_rescue | 5 |
| add_as_sensitivity_alternative | 3 |
| manual_review_required | 2 |
| retain_original | 1 |
| rejected_insufficient_text | 1 |
| remain_unavailable | 1 |

Decisions backup: `data/interim/full_sample_rescue/rescue_comparison_decisions_B06.csv`

### By firm

| Firm | Outcomes |
|------|----------|
| **5 MSF** | 2× replace, 1× retain_original (post_event), 1× sensitivity alt (post_post; weaker temporal fit). Branding tokens on retained/replaced paths well above threshold (175–3394). |
| **27 Douglas** | 3× replace, 1× sensitivity alt (forced_sensitivity / very_low fit), 1× rejected_insufficient_text (pre_pre; no branding pages). |
| **30 Oetker** | `entity_change_flag=True` on all rows. 2× manual_review_required (post/post_post; entity_change_comparability), 1× sensitivity alt (pre_event; entity_change_accepted_as_sensitivity), 1× remain_unavailable (pre_pre; not selected). |

---

## Coverage before → after

Parent had all three `german_longitudinal_ready=FALSE`.

| Firm | primary | extended | rescue_improved |
|------|---------|----------|-----------------|
| 5 MSF | FALSE → **FALSE** | FALSE → **TRUE** | TRUE |
| 27 Douglas | FALSE → **TRUE** | FALSE → **TRUE** | TRUE |
| 30 Oetker | FALSE → **FALSE** | FALSE → **FALSE** | TRUE |

---

## Special-case outcomes

| Case | Result |
|------|--------|
| **MSF text-volume threshold** | Enforced via existing compare rule; no below-threshold auto-promote. Usable rescues carried substantial branding tokens; post_event retained original as stronger German evidence. |
| **Oetker entity_change** | Flag preserved (`True`). Post/post_post require manual review (comparability not assumed); pre_event accepted only as sensitivity alternative; pre_pre remain_unavailable. Direct longitudinal primary/extended readiness not claimed. |

---

## Unresolved / limitations

- Oetker: not primary/extended ready; 2 observations need manual entity-change review; pre_pre unavailable.
- MSF: extended ready but not primary; 5 resumable fetch failures remain.
- Douglas: primary+extended ready; 1 resumable failure; pre_pre rejected (insufficient text).
- Live release outputs are batch-targeted; **B01–B05 decision backups must be re-merged at final assembly**.

---

## Integrity

| Check | Result |
|-------|--------|
| Parent SHA `c54fc356…` | PASS (unchanged) |
| Validated core / `full_sample_v1` / `full_sample.yaml` | PASS (no diffs) |
| Transport failures resumable | PASS |
| Firm 24 not re-crawled | PASS |
| Final assembly | **not run** |

---

## STOP

**B06 batch complete** (`COMPLETED_WITH_LIMITATIONS`).  
Do **not** perform final release assembly without an explicit request.  
All Phase B firm batches (B01–B06) have now completed acceptance for their executed firm sets.
