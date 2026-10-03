# dm Final Targeted Rescue — Firm 8

**Generated:** 2026-10-03  
**Run type:** `dm_final_targeted_rescue` (isolated)  
**Config:** `config/full_sample_rescue_dm.yaml`  
**Candidates:** `data/input/dm_final_targeted_rescue_candidates.csv`  
**Interim:** `data/interim/full_sample_rescue_dm/`  
**Staging release (not final):** `data/releases/full_sample_v1_1_rescue_dm/`  
**Parent:** `full_sample_v1` (unchanged)  
**Accepted final:** `full_sample_v1_1_rescue_final` (unchanged / provisional)

## Verdict

dm **partially** recovers German post coverage under unchanged Phase B rules:

| Timepoint | Decision | German eligible | Corpus bucket | Notes |
|-----------|----------|-----------------|---------------|-------|
| post_event | **replace_with_rescue** | TRUE (5,069 tokens_de / 17 pages) | **sensitivity** (forced) | Seed `https://dm.de/unternehmen/ueber-uns`, capture 2020-04-16, Δ=441d → fit `very_low` |
| post_post_event | **retain_original** | FALSE | excluded | No in-tolerance CDX capture for About/history seeds |

| Readiness | Before (parent / final) | After dm isolated run |
|-----------|-------------------------|------------------------|
| Primary longitudinal | FALSE | **FALSE** |
| Extended longitudinal | FALSE | **TRUE** |

Primary remains FALSE because the only recovered post observation is forced into sensitivity (temporal fit `very_low`). Extended becomes TRUE because pre German primary + post German sensitivity now exist.

---

## 1. Isolation and integrity

| Artifact | SHA-256 after run | Status |
|----------|-------------------|--------|
| `data/input/full_sample_url_rescue_candidates.csv` | `d28b44180c44eabaefca54ecc1322493b144fe63a39cd4e56e51dc2140530120` | **unchanged** |
| Parent primary corpus | `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27` | **unchanged** |
| `full_sample_v1_1_rescue_final/freeze_manifest.json` | `8c0bb4436a4158996fd89e2c9b825848980c55eb5a4d83995a208a981fb2aa69` | **unchanged** |
| `config/full_sample_rescue.yaml` | `d22113b0f9eaad6c04857bbb51accc09b919031c39fc9e4109ce1caa947146b0` | **unchanged** |

- Other 19 rescue firms: **not reprocessed**
- Validated core extraction rules: **not modified**
- Tolerances / thresholds: **not relaxed** (`tolerance_days=548`, `min_branding_tokens=100`, concurrency=1)

---

## 2. Seeds and archive evidence (CDX, not invented)

Authorized same-domain seeds from parent crawl evidence + CDX under existing tolerances:

| Seed | Priority (final) | CDX result |
|------|------------------|------------|
| `https://dm.de/unternehmen/ueber-uns` | 1 | 19 HTML captures; **post_event** in-tolerance: `20200416175348` (Δ=441d); **post_post_event** nearest **exceeds 548d** |
| `https://dm.de/unternehmen/ueber-uns/historie` | 2 | 11 HTML captures; nearest exceeds **548d** for both post windows → rejected |
| `https://dm.de/unternehmen` (pass 1–2 only) | — | In-tolerance captures `20210714123757` / `20230618132844` (Δ=13d) but archived HTML = **navigation_only**, 0 branding tokens; demoted/removed so closer empty shell would not block About seed |

Parent-path evidence (pre_pre/pre/event German branding) justified trying these seeds; post-window archive claims were filled only after CDX.

---

## 3. Selected captures and temporal fit

| Timepoint | Target | Selected capture | Δ days | Fit | Seed |
|-----------|--------|------------------|-------:|-----|------|
| post_event | 2021-07-01 | 2020-04-16 (`20200416175348`) | 441 | **very_low** | `https://dm.de/unternehmen/ueber-uns` |
| post_post_event | 2023-07-01 | *(none within tolerance)* | — | — | About/history rejected |

Parent homepage captures remain temporally strong (post Δ=12 / 0) but content-empty.

---

## 4. Crawl / pages / tokens (post_event rescue)

| Metric | Value |
|--------|------:|
| Pages fetched (snapshot cap) | 25 |
| Fetch success | 23 |
| Branding-eligible pages | 17 |
| tokens_de (observation) | 5,069 |
| High-priority discovered / fetched | 69 / 22 |
| Crawl limit reached | TRUE |

Pass-1 unternehmen-only crawl (archived under `pass1_unternehmen_nav_only/`): 1 page/timepoint, navigation_only, 0 tokens — documents why company-section root was insufficient.

---

## 5. Decisions (normal compare policy)

```
post_event      → replace_with_rescue
                  reason: rescue_german_eligible_forced_sensitivity_scope
                  forced_sensitivity_treatment: TRUE  (rescue temporal_fit=very_low)
post_post_event → retain_original
                  reason: rescue_not_selected_keep_original_structure
```

No `archive_unavailable` classification for transport pauses. Decision backup:

`data/interim/full_sample_rescue_dm/decisions_backup/dm_final_rescue_comparison_decisions.csv`

---

## 6. Transport

- Required **2 consecutive PREFLIGHT_OK** before each discovery/crawl wave (logs under `data/interim/full_sample_rescue_dm/preflight_*.log`).
- During pass-3 crawl: CDX/replay **503 / connection refused**; circuit opened; run paused with  
  `RESCUE_PAUSED_TRANSPORT_UNSTABLE` (20 pages cached, 3 pending).
- Resumed with `--resume --resume-from crawl` after cooldown; crawl completed.
- Discovery also saw intermittent CDX timeouts on historie (logged as `transport_failure_resumable`, then successful/rejected CDX responses).

Transport failures were **not** treated as archive gaps.

---

## 7. Before / after readiness (firm 8)

| Metric | Parent / current final | After dm isolated acceptance |
|--------|------------------------|------------------------------|
| n_pre German eligible | 2 | 2 |
| n_post German eligible | 0 | **1** (sensitivity) |
| n_post German primary | 0 | 0 |
| Primary ready | FALSE | FALSE |
| Extended ready | FALSE | **TRUE** |
| Gap | `missing_post` | `none` (extended); primary still blocked by sensitivity-only post |

---

## 8. Remaining limitations

1. **No primary-ready post observation** — recovered post_event is sensitivity-only due to Δ=441d / `very_low` fit.
2. **post_post_event unrecovered** — About/history seeds have archive hits outside 548d; cannot use without relaxing tolerance.
3. **Company-section root in 2021/2023 is a JS/navigation shell** — closer temporally, but zero branding text under validated extraction.
4. Staging release `full_sample_v1_1_rescue_dm` is an isolated artifact only; **accepted final was not mutated**.

---

## 9. Parent / core integrity

- `full_sample_v1`: blocked by write guards; SHA unchanged.
- `full_sample_v1_1_rescue_final`: blocked by write guards; freeze manifest SHA unchanged.
- 19-firm candidate CSV: not modified.
- Shared Phase B validation/impact report templates: not overwritten (`isolated_run` skips template rewrite).

---

## 10. Successor cumulative release (NOT executed)

dm rescue **succeeded for extended readiness**. Do **not** mutate `full_sample_v1_1_rescue_final` in place.

To create a successor cumulative release containing the accepted 19-firm final **plus** dm:

1. Keep `full_sample_v1_1_rescue_final` immutable as the 19-firm baseline.
2. Treat dm decisions as batch **`DM_FINAL`**  
   (`data/interim/full_sample_rescue_dm/decisions_backup/dm_final_rescue_comparison_decisions.csv`).
3. Extend the offline assembler (same pattern as `scripts/assemble_full_sample_rescue_final.py`) to:
   - start from `full_sample_v1_1_rescue_final` (or parent + all accepted batch backups including DM_FINAL);
   - apply only firm-8 post decisions (`replace_with_rescue` for post_event sensitivity; retain post_post);
   - re-extract firm-8 post_event pages from `data/interim/full_sample_rescue_dm/html` (cache-only);
   - write a **new** release directory, e.g. `data/releases/full_sample_v1_1_rescue_final_dm/`;
   - regenerate corpora, coverage, impact, freeze manifest.
4. Expected headline deltas vs current final:
   - extended-ready firms: 27 → **28**
   - still not extended-ready: drop firm 8; remain Viessmann (24) + Oetker (30)
   - primary-ready firms: **unchanged** (dm post stays sensitivity)
5. Re-run acceptance audits; do not reopen the other 19 firms.

If a successor is **not** assembled, `full_sample_v1_1_rescue_final` can stand unchanged with dm documented as:

- extended gap **closed in isolated staging** (sensitivity post_event),
- primary gap **still open**,
- post_post_event still an unresolved in-tolerance archive/content gap under current rules.

---

## 11. Commands used (reference)

```bash
# Preflight (2× consecutive OK required)
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage preflight --firms 8 --timepoints post_event post_post_event

# Discovery / crawl / extract / compare / acceptance
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage discover --firms 8 --timepoints post_event post_post_event

python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage crawl --firms 8 --timepoints post_event post_post_event

# After transport pause:
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage crawl --firms 8 --timepoints post_event post_post_event \
  --resume --resume-from crawl

python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage extract --firms 8 --timepoints post_event post_post_event --resume

python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage compare --firms 8 --timepoints post_event post_post_event --resume

python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue_dm.yaml \
  --stage acceptance --firms 8 --timepoints post_event post_post_event --resume
```

STOP: no dictionary work; no GitHub push; accepted final not modified.
