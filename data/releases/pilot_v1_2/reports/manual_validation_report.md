# Manual Validation Report — Pilot v1.2

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Validation date:** 2026-07-23

---

## Focus

Focused corpus-integrity validation after regeneration:

- impressum / privacy / terms / cookie classifications
- governance_metadata_eligible pages
- observations with `text_analysis_eligible = false`
- sample branding pages previously at risk of legal misclassification

Evidence file: `data/output/manual_corpus_validation.csv`

New review fields:

- `strict_legal_classification_correct`
- `branding_exclusion_correct`
- `governance_inclusion_correct`
- `observation_export_correct`

Archive-validity judgments from earlier releases remain in `manual_validation_sample.csv`.

---

## Outcome

Automated consistency checks for legal exclusion, observation-export eligibility, and governance URL traceability: **PASSED**.
