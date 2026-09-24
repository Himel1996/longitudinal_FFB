# Batch B03 Summary — COMPLETED_WITH_LIMITATIONS

**Generated:** 2026-09-10 ~14:04 UTC  
**Branch:** `rescue_pass` @ `79d2df9`  
**Firms:** 17 (Merck), 18 (Schaeffler), 19 (Heraeus)  
**Status:** `COMPLETED_WITH_LIMITATIONS`  
**Acceptance:** PASS (pipeline finished; release updated for targeted firms)  
**B04:** not started  
**B01/B02:** not reprocessed this run

---

## Latest resume (3rd transport-pause recovery → completion)

Transport gate: **2 consecutive PREFLIGHT_OK** (replay 100% both; exits 0).

Command:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full --firms 17 18 19 \
  --resume --resume-from discover \
  2>&1 | tee -a reports/full_sample_rescue/batch_B03_run.log
```

Pipeline: discover (reused) → crawl (cache + residual retries) → extract → compare → report → **acceptance complete** (~94 min wall clock from 12:30Z).

### Progress across resumes

| Firm | Campaign start | After pause 2 | **Final** | Resumable left |
|------|----------------|---------------|-----------|----------------|
| 17 Merck | 43 | 126 | **127** | 2 |
| 18 Schaeffler | 0 | 132 | **132** | 2 |
| 19 Heraeus | 0 | 6 | **50** | 5 |

Global HTML cache: **578** FETCHED / **49** FETCH_FAILED_RESUMABLE (includes prior batches).  
No `archive_unavailable` conversions. Cache/SQLite preserved.

Parent SHA unchanged: `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`  
Validated core: unchanged.

---

## Discovery (persisted; not re-run from scratch)

| Firm | Selected | Notes |
|------|----------|-------|
| 17 Merck | 5/5 | `merckgroup.com` |
| 18 Schaeffler | 5/5 | `schaeffler.de` |
| 19 Heraeus | 3/5 | `heraeus.com` — **missing pre_pre_event + event** |

### Selected rescue snapshots

| Firm | Timepoint | Timestamp | Domain |
|------|-----------|-----------|--------|
| 17 | pre_pre_event | 20170801064041 | merckgroup.com |
| 17 | pre_event | 20190719141851 | merckgroup.com |
| 17 | event | 20210609180252 | merckgroup.com |
| 17 | post_event | 20230701160411 | merckgroup.com |
| 17 | post_post_event | 20250806204111 | merckgroup.com |
| 18 | pre_pre_event | 20100723011723 | schaeffler.de |
| 18 | pre_event | 20120709062345 | schaeffler.de |
| 18 | event | 20140626163520 | schaeffler.de |
| 18 | post_event | 20160627103617 | schaeffler.de |
| 18 | post_post_event | 20180722050121 | schaeffler.de |
| 19 | pre_event | 20120825140213 | heraeus.com |
| 19 | post_event | 20151205105724 | heraeus.com |
| 19 | post_post_event | 20170703173749 | heraeus.com |

---

## Decisions (14)

| Firm | Timepoint | Decision | Reason / tokens_de (orig → rescue) | Role |
|------|-----------|----------|-------------------------------------|------|
| 17 | pre_pre_event | **replace_with_rescue** | German where original lacked (0 → 5812) | primary |
| 17 | pre_event | **replace_with_rescue** | German where original lacked (0 → 5959) | primary |
| 17 | event | **replace_with_rescue** | German where original lacked (0 → 10189) | sensitivity |
| 17 | post_event | **replace_with_rescue** | German where original lacked (0 → 6854) | primary |
| 17 | post_post_event | **replace_with_rescue** | German where original lacked (0 → 2290) | primary |
| 18 | pre_pre_event | **replace_with_rescue** | German where original lacked (0 → 3614) | sensitivity |
| 18 | pre_event | **replace_with_rescue** | German where original lacked (0 → 5275) | sensitivity |
| 18 | event | **replace_with_rescue** | German where original lacked (0 → 5506) | sensitivity |
| 18 | post_event | **replace_with_rescue** | German where original lacked (0 → 6168) | sensitivity |
| 18 | post_post_event | **replace_with_rescue** | German where original lacked (0 → 9652) | sensitivity |
| 19 | pre_pre_event | retain_original | rescue_not_selected_or_missing | — |
| 19 | pre_event | **replace_with_rescue** | forced sensitivity scope (0 → 2361); temporal very_low | sensitivity |
| 19 | event | *(not in decisions)* | not selected in discovery | — |
| 19 | post_event | rejected_insufficient_text | no_branding_pages | excluded |
| 19 | post_post_event | **replace_with_rescue** | German where original lacked (0 → 4482) | primary |

- **replace_with_rescue:** 12  
- **rejected_insufficient_text:** 1 (Heraeus post_event)  
- **retain_original:** 1 (Heraeus pre_pre_event)  
- **archive_unavailable / transport→unavailable:** 0  
- Forced sensitivity: 1 (Heraeus pre_event)

Rescue corpus role: primary 5 / sensitivity 7 / excluded 2.

Decisions backup: `data/interim/full_sample_rescue/rescue_comparison_decisions_B03.csv`

---

## Coverage (B03 firms)

| Firm | primary ready | extended ready | rescue_improved |
|------|---------------|----------------|-----------------|
| 17 Merck | **TRUE** | **TRUE** | TRUE |
| 18 Schaeffler | **FALSE** | **TRUE** | TRUE |
| 19 Heraeus | **TRUE** | **TRUE** | TRUE |

Limitations: Schaeffler stays sensitivity-only (no primary longitudinal); Heraeus missing discovery for pre_pre_event + event, with post_event rejected for insufficient branding text.

---

## Remaining FETCH_FAILED_RESUMABLE (not converted to unavailable)

### Firm 19 Heraeus (5)

| Timepoint | Timestamp | URL | Error |
|-----------|-----------|-----|-------|
| pre_event | 20120825140213 | `http://corporate.heraeus.com/de/karriere/wirbieten/unsereleistungen/2.3Your_benefits.aspx` | transport_connection_refused |
| pre_event | 20120825140213 | `http://corporate.heraeus.com/de/presse/termine/100_jahre_quarzglas/quarzglas.aspx` | transport_connection_refused |
| post_event | 20151205105724 | `https://www.heraeus.com/de/group/home/home.aspx` | transport_connection_refused |
| post_post_event | 20170703173749 | `https://www.heraeus.com/de/group/careers/your_advantage/your_advantage_at_a_glance/your_advantage.aspx` | transport_connection_refused |
| post_post_event | 20170703173749 | `https://www.heraeus.com/de/group/careers/your_employer/internationality/internationality.aspx` | transport_connection_refused |

### Firm 17 Merck (2)

| Timepoint | Timestamp | URL | Error |
|-----------|-----------|-----|-------|
| pre_pre_event | 20170801064041 | `https://www.merckgroup.com/de/company.html` | transport_connection_refused |
| pre_event | 20190719141851 | `https://www.merckgroup.com/de/company/responsibility/our-good-deeds.html` | transport_connection_refused |

### Firm 18 Schaeffler (2)

| Timepoint | Timestamp | URL | Error |
|-----------|-----------|-----|-------|
| pre_pre_event | 20100723011723 | `http://www.schaeffler.de/content.schaeffler.de/de/career/joining_us/dual_study/dual_study.jsp` | transport_connection_refused |
| pre_pre_event | 20100723011723 | `http://www.schaeffler.de/content.schaeffler.de/de/press/press-releases/press-details.jsp?id=3396992` | other (empty body) |

---

## Integrity

| Check | Result |
|-------|--------|
| Parent SHA unchanged | PASS |
| Validated core unchanged | PASS |
| Transport failures remain resumable | PASS |
| Existing cache/SQLite preserved | PASS |
| B04 not started | PASS |

---

## STOP

**B03 batch complete** (`COMPLETED_WITH_LIMITATIONS`).  
Do **not** start B04 without an explicit request.
