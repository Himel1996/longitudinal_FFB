# Full-Sample Release Acceptance Audit — `full_sample_v1`

**Audit date:** 2026-07-25  
**Release:** `data/releases/full_sample_v1/`  
**Run ID:** `508f1903-71e7-4aab-aba6-000fed4d8b7d`  
**Extraction git commit (manifest):** `cbdd849197cb139b7e3c228c0ec962d8ed16d254`  
**Repo HEAD at audit:** `9e68fc1dc530185bf29d0eca32fdbccf710ef6cc` (packaging/tooling only; no `src/` drift)  
**Config SHA-256:** `2e3c987c0cb13b2c248d75275d4cacf16370741d791085b43f65079a9622c58b`  
**Predecessor:** `pilot_v1_4_1`  
**Machine-readable results:** `data/interim/full_sample_release_acceptance.json`  
**Audit script:** `scripts/audit_full_sample_v1_acceptance.py`

---

## Recommendation

# READY TO FREEZE

**FULL SAMPLE EXTRACTION ACCEPTED.**

This release is suitable to freeze and use as the basis for dictionary development and subsequent longitudinal family-branding analyses.

No hard-fail invariant from Christian’s success criteria failed. No crawler or extraction-rule changes were required during this audit.

---

## 1. Christian requirements — PASS / FAIL

| # | Requirement | Result |
|---|-------------|--------|
| 1 | Reproducibility (bundle, commit/config, run_id, no stale outputs) | **PASS** |
| 2 | Snapshot quality / temporal policy | **PASS** |
| 3 | Legal pages excluded from branding corpus | **PASS** |
| 4 | Governance layer restricted to governance intents | **PASS** |
| 5 | Primary/sensitivity corpora eligibility filtering | **PASS** |
| 6 | Duplicate handling (within timepoint / www / scheme; longitudinal preserved) | **PASS** |
| 7 | German-only DE corpus; language partitions reconcile | **PASS** |
| 8 | Reserved-slot prioritization; legal/foreign consume 0 reserved slots | **PASS** |
| 9 | Tokenization policy (no usable zero-token pages; method by language) | **PASS** |
| 10 | Quality summary consistency | **PASS** |
| 11 | Branding corpus quality flags (review, not hard fail) | **PASS** (informational) |
| 12 | Governance quality (page present or explicitly unavailable) | **PASS** |
| 13 | Stratified manual sample | **PASS** |
| 14 | Regression vs `pilot_v1_4_1` | **PASS** |
| 15 | Final freeze decision | **READY TO FREEZE** |

### Hard-fail checklist (must all be clear)

| Hard fail | Status |
|-----------|--------|
| Legal pages in branding | Clear |
| Governance contains marketing pages | Clear |
| Ineligible observations in primary | Clear |
| Duplicates within firm × timepoint | Clear |
| German corpus contains foreign-language pages | Clear |
| Reserved slots consumed by legal/foreign | Clear |
| Usable page with zero analysis tokens | Clear |
| Quality summary inconsistent | Clear |
| Outputs not reproducible / metadata inconsistent | Clear (see §1 note) |

---

## 2. Statistics

### Sample / snapshots
| Metric | Value |
|--------|------:|
| Firms | 30 |
| Observations | 150 |
| Selected | 100 |
| Beyond tolerance | 45 |
| Future unavailable | 4 |
| Event unavailable | 1 |
| Unavailable total | 50 |
| Include recommendations | 77 |
| Sensitivity recommendations | 21 |
| Exclude (+ duplicate-capture exclude) | 52 |

### Corpora
| Metric | Value |
|--------|------:|
| Branding pages (all languages) | 1,376 |
| Branding pages (DE file) | 862 |
| DE pages in all-languages file | 864 |
| DE pages gated into DE file via `german_text_analysis_eligible` | 862 |
| EN / unknown in all-languages | 507 / 5 |
| Primary branding observations | 51 |
| Sensitivity branding observations | 84 |
| Governance pages | 27 |
| Governance observations with ≥1 page | 22 |
| Governance explicitly unavailable | 128 |
| Impressum-available observations | 9 |

### Duplicates
| Metric | Value |
|--------|------:|
| Duplicate summary rows | 333 |
| Duplicate tokens removed | 97,840 |
| Within-timepoint duplicate groups in branding | 0 |
| Branding pages still flagged duplicate | 0 |
| Preserved longitudinal duplicate groups | 112 |
| Top reasons | host variant 277; near-duplicate 56 |

### Tokens / reserved slots
| Metric | Value |
|--------|------:|
| Observation `tokens_de` sum | 398,064 |
| German eligible branding page token sum | 398,064 |
| DE branding file token sum | 397,829 |
| Reserved coverage (selected under slot) | homepage 100; company_about 144; values 20; history 16; management 12 |
| Legal pages consuming reserved slots | 0 |
| Foreign-language pages consuming reserved slots | 0 |
| High-priority pages fetched (crawl summary) | 804 |

### Tokenization methods (pages table)
| Method | Count |
|--------|------:|
| `latin_lexical_regex` | 1,864 |
| `unicode_cjk_chars` | 7 |
| none / NA | 22 / 180 |

Policy verified: `token_count == analysis_token_count` (choice A). Zero usable pages with `analysis_token_count == 0`.

---

## 3. Evidence by section

### Section 1 — Reproducibility — PASS
- Required release CSVs and reports present under `data/releases/full_sample_v1/`.
- All output CSVs share run_id `508f1903-71e7-4aab-aba6-000fed4d8b7d`.
- Config hash matches freeze documentation.
- Manifest commit ≠ HEAD, but **packaging-only drift**: comment change in `config/full_sample.yaml`; **zero** `src/` / `event_dates` / `pyproject` diff since the extraction commit. Reproducible rebuild uses the documented commit + config hash.

### Section 2 — Snapshot quality — PASS
- No selected snapshot missing archive timestamp (no silent substitution).
- No future observation incorrectly selected.
- Beyond-tolerance / future / event-unavailable statuses populate the unavailable pool as configured.

### Section 3 — Legal exclusion — PASS
- Zero branding pages with legal categories (`impressum`, privacy, AGB/cookie/disclaimer/terms/legal_other/technical).
- Zero path/title legal violations remaining in branding after category+URL+title+H1 checks.
- Spot-check: Leichtle Impressum opens correctly as legal content and is **absent** from branding (0 branding URLs containing `impressum`).

### Section 4 — Governance layer — PASS
- Categories only: `corporate_affiliation` (14), `impressum` (7), `management_legal_representatives` (4), `legal_notice` (2).
- Zero marketing/products/careers/history/about violations.

### Section 5 — Observation eligibility — PASS
- Primary: 51 rows, all `text_analysis_eligible == True`.
- Sensitivity: 84 rows, eligibility consistent.

### Section 6 — Duplicates — PASS
- No within firm×timepoint normalized-content duplicates in branding.
- WWW/scheme host variants and near-duplicates removed (333 summary rows).
- 112 longitudinal duplicate groups preserved across timepoints.

### Section 7 — Language — PASS
- DE file contains **only** `detected_language == de` (862 pages).
- English/unknown absent from DE file.
- Partition reconciles exactly when applying the pipeline gate: German pages in all-languages ∩ `german_corpus_eligible` ∩ observation `german_text_analysis_eligible` → DE file.
- Two German pages remain in all-languages only (Bahlsen homepage; Viessmann `/de.html`) because those observations are EN-primary (`german_text_analysis_eligible=False`) — intentional, not contamination.
- Observation `tokens_de` equals sum of German branding page tokens (398,064).

### Section 8 — Reserved slots — PASS
- Legal and foreign-language pages consume **0** reserved slots.
- No news/careers/products crowding of reserved categories under segment-aware matching.
- No `unternehmen` substring false-positive `company_about` hits.

### Section 9 — Tokenization — PASS
- No usable analysis page with zero `analysis_token_count`.
- CJK pages use `unicode_cjk_chars`; Latin pages use `latin_lexical_regex`.
- Observation token totals reconcile with page totals.

### Section 10 — Quality summary — PASS
- 150 rows; no impossible counts; aggregations reconcile.

### Section 11 — Branding quality flags (review) — PASS / informational
- **66** observations flagged for review (not hard fails).
- Flag mix: `branding_pages_zero` (63), `branding_tokens_below_threshold` (66).
- Dominated by unavailable / thin / non-selected observations — expected under temporal policy; dictionary work should use primary + documented sensitivity sets, not all 150 grid cells.

### Section 12 — Governance quality — PASS
- Every observation has ≥1 governance page **or** is explicitly unavailable (`impressum_available=False` / empty sources / non-selected snapshot).
- Note: `impressum_available` only marks impressum/legal-notice; affiliation/ownership/representative pages may exist with `impressum_available=False` — those still satisfy “has governance page.”

### Section 13 — Manual sample — PASS
- Stratified sample: 40 observations (`full_sample_manual_validation.csv`); 27 firms.
- Automated evidence checks: 0 structural issues.
- Pipeline-evidence rates: correct company 97.5%; valid archive 97.5%; content usable 80%; temporally appropriate 75%.
- Live Wayback spot-checks (2026-07-25):
  - BLUE MOON DE homepage `20201101073754` — German branding homepage; correct firm/language.
  - Leichtle Impressum `20190723` — governance/legal; correctly **not** in branding.
  - PETER-LACKE sensitivity homepage `20150522` — correct firm; Impressum/AGB links present as legal exits, not branding inclusions.
- Screenshot artifact: `data/interim/full_sample_acceptance_screenshots/full_sample_v1_audit_impressum_leichtle.png`

### Section 14 — Regression vs pilot_v1_4_1 — PASS
All previously fixed invariants still hold at 30 firms:

| Check | Holds |
|-------|:-----:|
| Legal exclusion | ✓ |
| Governance restriction | ✓ |
| Eligibility filtering | ✓ |
| Duplicate handling | ✓ |
| German-only corpus | ✓ |
| Reserved slots | ✓ |
| Token policy | ✓ |
| Quality summary | ✓ |

---

## 4. Files inspected

### Release bundle
- `data/releases/full_sample_v1/data/run_manifest.json`
- `data/releases/full_sample_v1/data/firms.csv`
- `data/releases/full_sample_v1/data/full_sample_snapshots.csv`
- `data/releases/full_sample_v1/data/full_sample_pages.csv`
- `data/releases/full_sample_v1/data/full_sample_branding_corpus_pages_all_languages.csv`
- `data/releases/full_sample_v1/data/full_sample_branding_corpus_pages_de.csv`
- `data/releases/full_sample_v1/data/full_sample_branding_corpus_observations_primary.csv`
- `data/releases/full_sample_v1/data/full_sample_branding_corpus_observations_sensitivity.csv`
- `data/releases/full_sample_v1/data/full_sample_governance_metadata_pages.csv`
- `data/releases/full_sample_v1/data/full_sample_governance_metadata_observations.csv`
- `data/releases/full_sample_v1/data/full_sample_observation_text_summary.csv`
- `data/releases/full_sample_v1/data/full_sample_quality_summary.csv`
- `data/releases/full_sample_v1/data/full_sample_duplicate_summary.csv`
- `data/releases/full_sample_v1/data/full_sample_crawl_priority_summary.csv`
- `data/releases/full_sample_v1/data/full_sample_manual_validation.csv`
- `data/releases/full_sample_v1/config/full_sample.yaml`
- `data/releases/full_sample_v1/reports/*`

### Supporting
- `data/releases/pilot_v1_4_1/data/*` (regression baseline)
- `reports/full_sample_{quality,manual_validation,readiness,reproducibility,baseline_freeze}.md`
- `data/interim/full_sample_release_acceptance.json`
- Working outputs under `data/output/` (byte-reconciled to release tables)

---

## 5. Manual validation summary

| Item | Result |
|------|--------|
| Stratified sample size | 40 |
| Automated sample issues | 0 |
| Live Wayback DE homepage | Confirmed (BLUE MOON) |
| Live Wayback governance Impressum | Confirmed (Leichtle); excluded from branding |
| Live Wayback sensitivity observation | Confirmed (PETER-LACKE) |
| Legal links on branding homepages | Present as site chrome; not ingested as branding pages |

Temporal appropriateness <100% in the sample reflects configured tolerance / future / unavailable rules — not a regression.

---

## 6. Remaining limitations

1. **Manifest commit ≠ current HEAD** by one packaging commit; extraction code is frozen at the manifest commit. Rebuild instructions should pin that commit (already documented in `full_sample_reproducibility.md`).
2. **Governance coverage is sparse** (27 pages / 22 observations with pages). Most cells are explicitly unavailable — expected for archived sites without Impressum capture, but limits governance validation power.
3. **Thin / zero-branding cells** (66 review flags) remain in the observation grid for unavailable or low-yield snapshots; dictionary development should use primary (51) and sensitivity (84) corpora, not the full 150-cell grid indiscriminately.
4. **Two German pages** sit only in the all-languages branding file because parent observations are EN-primary; DE analysis denominators correctly exclude them.
5. **Wayback `id_` replay** often strips CSS; visual screenshots are text-heavy but sufficient for category/language/legal checks.
6. **No dictionary scoring** was performed in this audit (by design).

---

## 7. Final decision

**READY TO FREEZE**

FULL SAMPLE EXTRACTION ACCEPTED.

This release is suitable to freeze and use as the basis for dictionary development and subsequent longitudinal family-branding analyses.

Do **not** modify snapshot, legal, governance, dedup, language, reserved-slot, token, or eligibility rules unless a new blocking defect is discovered. Proceed to dictionary development on the frozen `full_sample_v1` corpora.
