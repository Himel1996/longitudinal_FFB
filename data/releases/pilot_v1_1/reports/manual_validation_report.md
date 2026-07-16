# Manual Validation Report — Pilot v1.1

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Validation date:** 2026-07-16

---

## Summary

| Layer | Status |
|-------|--------|
| Archive validity (v1.0 judgments preserved) | 19 observations |
| Corpus/classification validation sample | 43 page rows |
| Branding corpus exclusions | Automated + sample verified |
| Impressum governance layer | 24 pages retained separately |

Prior judgments for `correct_company`, `valid_archived_page`, `temporally_appropriate`, and `duplicate_capture` were carried forward from Pilot v1.0 where observation URLs unchanged.

New v1.1 fields validated in `manual_corpus_validation.csv`:

- `page_category_correct`
- `branding_corpus_eligibility_correct`
- `legal_technical_exclusion_correct`
- `impressum_layer_correct`
- `token_count_plausible`
- `language_detection_plausible`
- `observation_text_eligibility_correct`

---

## Evidence

- Page-level sample: `data/output/manual_corpus_validation.csv`
- Observation archive validity: `data/output/manual_validation_sample.csv`
- Corpus quality table: `reports/corpus_quality_report.md`
