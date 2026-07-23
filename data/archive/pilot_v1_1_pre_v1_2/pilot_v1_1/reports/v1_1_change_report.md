# Pilot v1.1 Change Report

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Date:** 2026-07-16  
**Git commit:** `7dffd85c38626862c14a2022a9fc5ff119772498`

---

## requested changes

1. **Exclude legal/technical boilerplate from the main NLP corpus** — implemented transparent `page_category` classification with default exclusions for privacy, AGB, cookies, legal/technical, search, navigation-only, and low-substance contact pages.
2. **Retain Impressum separately for governance validation** — added `governance_metadata_pages.csv` and `governance_metadata_observations.csv` with rule-based field extraction and raw-text fallback.
3. **Add observation-level text eligibility and corpus outputs** — added `observation_text_summary.csv`, `branding_corpus_pages.csv`, and primary/sensitivity observation corpora with explicit quality bands and exclusion reasons.
4. **Fix quality-summary and token-count inconsistencies** — corrected aggregation metrics and centralized tokenizer/language detection across all extraction paths.

---

## Implementation decisions

- Classification combines normalized path, title, headings, meta description, visible text, and navigation heuristics; no single-keyword decisions.
- Branding eligibility is applied only after extraction usability checks; Impressum never enters the branding corpus.
- Language detection uses offline `lingua-language-detector` with configurable confidence threshold (`analysis.language_confidence_threshold: 0.80`).
- Token counts use one centralized regex tokenizer in `extract/text_utils.py` with HTML-entity decoding and German-character support.
- Eligibility thresholds are config-driven (`analysis.min_branding_pages`, `analysis.min_branding_tokens`, `analysis.preferred_branding_tokens`).

---

## Files changed

- `src/ffb_webminer/config.py`, `config/pilot.yaml`
- `src/ffb_webminer/pipeline/schemas.py`, `corpus_outputs.py`, `runner.py`
- `src/ffb_webminer/quality/page_classification.py`, `checks.py`, `page_validation.py`
- `src/ffb_webminer/extract/text_utils.py`, `language_detection.py`, `text.py`
- `src/ffb_webminer/governance/extraction.py`
- `scripts/refresh_corpus_outputs.py`, `run_manual_corpus_validation.py`, `check_pilot_consistency.py`, `build_pilot_release.py`
- Tests: `test_page_classification.py`, `test_text_processing.py`, `test_corpus_outputs.py`

---

## Before / after corpus statistics


| Metric                                | v1.0           | v1.1  |
| ------------------------------------- | -------------- | ----- |
| Total page rows                       | 394            | 394   |
| Pages usable for extraction           | 358            | 374   |
| Branding-corpus-eligible pages        | n/a            | 231   |
| Impressum/governance pages retained   | mixed in pages | 24    |
| Observation text-analysis eligible    | n/a            | 15    |
| Token_count = 0 with non-empty text   | present        | **0** |
| Quality-summary count inconsistencies | present        | **0** |


---

## Pages excluded by category


| Category                | Pages        | In branding corpus                      |
| ----------------------- | ------------ | --------------------------------------- |
| privacy_policy          | 71           | 0                                       |
| search_archive          | 35           | 0                                       |
| navigation_only         | 26           | 0                                       |
| impressum               | 24           | 0                                       |
| contact (low substance) | subset of 76 | excluded when below substance threshold |
| technical_system        | 4            | 0                                       |


Legal/technical categories are excluded by default; substantive branding pages remain in `branding_corpus_pages.csv`.

---

## Impressum pages retained

- **24** impressum-classified pages retained in `governance_metadata_pages.csv`
- **25** observation-level governance summaries in `governance_metadata_observations.csv`
- Raw Impressum text preserved when structured fields cannot be extracted reliably

---

## Observations newly eligible / ineligible


| Pool                                             | Text-analysis eligible |
| ------------------------------------------------ | ---------------------- |
| All observations                                 | 15 / 25                |
| Primary (`include`)                              | 13 / 16                |
| Sensitivity (`include` + `sensitivity_analysis`) | 15 / 19                |


Exclusion reasons:

- `no_valid_snapshot`: 5
- `insufficient_branding_tokens`: 2
- `no_branding_pages`: 2
- `duplicate_capture`: 1

---

## Quality-summary bug: cause and fix

**Root cause**

1. `pages_success` counted only `http_status == 200`, while `pages_usable` could include pages marked usable after failed HTTP handling.
2. `validate_page_for_analysis()` reset `usable = True` instead of preserving `check_page()` exclusions.
3. On CSV round-trips, `NaN` in `fetch_error` was treated as truthy, falsely marking successful fetches as failed.

**Fix**

- Renamed and clarified metrics: `pages_fetch_success`, `pages_fetch_failed`, `pages_extraction_usable`, `pages_branding_eligible`.
- Added `page_fetch_success()` and `has_fetch_error()` helpers with explicit null/NaN handling.
- Preserved extraction usability only when fetch, HTTP status, domain, and text-length checks pass.

---

## Token-count issue: cause and fix

**Cause:** `token_count` was derived from naive `text.split()` inside extraction only; punctuation-only and entity-encoded text could yield inconsistent zero counts.

**Fix:** centralized `compute_text_stats()` used by all extraction outputs; `token_count_reason` recorded when no lexical tokens remain.

---

## Language-detection coverage


| Language      | Pages |
| ------------- | ----- |
| de            | 335   |
| en            | 44    |
| unknown       | 7     |
| missing/short | 8     |


Observation-level primary language is token-weighted from branding-eligible pages.

---

## Remaining limitations

1. Wayback intermittency still affects crawl completeness; mitigated by retries.
2. Governance field extraction is regex/rule-based v1.1 only; nulls are expected where Impressum text is ambiguous.
3. Contact-page substance threshold may need manual review for edge cases.
4. Playwright remains required for a subset of dynamic archived pages.

