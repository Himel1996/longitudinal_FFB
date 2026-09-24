# Final Release Acceptance — full_sample_v1_1_rescue_final

**Generated:** 2026-09-24  
**Release:** `data/releases/full_sample_v1_1_rescue_final/`  
**Parent:** `data/releases/full_sample_v1/`  
**Parent primary SHA:** `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`  
**Network during assembly:** none  
**Verdict:** `READY_TO_FREEZE_WITH_DOCUMENTED_LIMITATIONS`

---

## Scorecard

| # | Check | Result |
|---|-------|--------|
| 1 | Cumulative decision reconstruction | **PASS** — 87 decisions / 19 firms; unique firm×timepoint; backups B.Braun+B01–B06 |
| 2 | B. Braun preservation | **PASS** — 5× replace; 18,028 DE tokens; primary+extended TRUE |
| 3 | Legal exclusion (branding) | **PASS** — 0 legal/impressum/privacy hits in DE branding pages |
| 4 | Governance scope | **PASS** — governance pages restricted to impressum/legal/ownership/affiliation/representatives |
| 5 | Observation eligibility | **PASS** — primary rows german-eligible; corpora regenerated via validated builders |
| 6 | Within-timepoint dedup | **PASS** — 0 duplicate canonical_page_url groups in DE branding pages |
| 7 | Cross-timepoint preservation | **PASS** — identical content across timepoints retained by design (dedup is within-observation only) |
| 8 | German-language purity | **PASS** — primary + sensitivity_de use german eligibility; all-language sensitivity separate |
| 9 | Token consistency | **PASS WITH DOCUMENTED LIMITATION** — obs tokens_de 800,451 vs DE page tokens 800,327 (Δ=124); parent residual was Δ=235 |
| 10 | Quality summary | **PASS** — no pages_success/pages_usable aggregation regression observed in regenerated corpora |
| 11 | Temporal tolerances | **PASS** — accepted decisions retained sensitivity where temporal fit required; no tolerance relaxation |
| 12 | Special-case handling | **PASS** — MSF/Freudenberg/STIHL/Viessmann/Oetker flags & decisions preserved |
| 13 | Transport-failure semantics | **PASS** — 0 `archive_unavailable` snapshots; resumable FETCH_FAILED remain in SQLite only |
| 14 | Non-targeted regression | **PASS** — 11 parent-only firms immutable vs parent obs |
| 15 | Parent integrity | **PASS** — SHA unchanged |
| 16 | Core integrity | **PASS** — no diffs under validated core paths / `full_sample.yaml` / `full_sample_v1` |
| 17 | Corpus reconciliation | **PASS** — exports named and generated; primary=DE, sens_all=all languages, sens_de=DE |
| 18 | Longitudinal coverage reconciliation | **PASS** — all 19 expectation checks match recomputed coverage |

---

## Assembly provenance

| Source | Artifact |
|--------|----------|
| B. Braun | git `6b28230` release slice → `assembly_sources/bbraun_smoke/` |
| B01 | git `79d2df9` release slice → `assembly_sources/b01_batch1/` (+ `rescue_comparison_decisions_B01.csv`) |
| B02–B05 | decision backups + offline cache-only re-extract from local HTML/SQLite |
| B06 | decision backup + live interim `rescue_pages.csv` / snapshots (preferred) |
| Inventory | `data/interim/full_sample_rescue/final_assembly_inventory.csv` |
| Cumulative decisions | `rescue_comparison_decisions_FINAL.csv` (interim + final release) |

---

## Coverage (recomputed)

| Metric | Before | After |
|--------|-------:|------:|
| Parent `german_longitudinal_ready` | 10 | — |
| Primary ready | 10* | **22** |
| Extended ready | 10* | **27** |

\*Parent exposed a single readiness flag.

**Still not extended-ready:** firms **8**, **24 (Viessmann)**, **30 (Oetker)**.  
Firm 8 was never a Phase B rescue target.

---

## Special cases

| Firm | Outcome |
|------|---------|
| MSF (5) | Text-volume rule held; post_event retain_original; extended TRUE / primary FALSE |
| Freudenberg (21) | Sensitivity/migration treatment preserved; extended TRUE / primary FALSE |
| STIHL (22) | Sensitivity/migration treatment preserved; extended TRUE / primary FALSE |
| Viessmann (24) | `entity_change_flag=TRUE`; not longitudinally ready |
| Oetker (30) | `entity_change_flag=TRUE`; 2× manual_review_required; not longitudinally ready |

---

## Documented limitations (do not block freeze)

1. Remaining `FETCH_FAILED_RESUMABLE` pages in interim SQLite (not converted to archive_unavailable; accepted observations stand).
2. Oetker / Viessmann organizational comparability — not primary/extended ready by design.
3. Some firms extended-only (Rossmann, Schaeffler, Freudenberg, STIHL, MSF) due to sensitivity/temporal/entity rules.
4. Token Δ=124 between observation and DE page aggregates (smaller than parent Δ=235).
5. B02–B05 page corpora rebuilt offline from cache (same methodology, no network); B.Braun/B01/B06 used accepted persisted extracts.

---

## Freeze verdict

**READY_TO_FREEZE_WITH_DOCUMENTED_LIMITATIONS**
