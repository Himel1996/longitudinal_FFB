# Pilot v1.1 Readiness Report

**Release:** Pilot v1.1  
**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Run date:** 2026-07-16  
**Git commit:** `7dffd85c38626862c14a2022a9fc5ff119772498`  
**Release bundle:** `data/releases/pilot_v1_1/`

---

## Executive Summary

Pilot v1.1 adds a clean branding corpus, separate governance metadata layer, observation-level text eligibility, corrected quality metrics, centralized tokenization, and offline language detection. The five-firm dataset regenerates reproducibly from the accepted v1.0 architecture.

**Ready to share with Christian:** **YES** — with documented limitations below.

**Ready to scale to remaining 25 firms:** **YES, with caution** — after Christian reviews corpus exclusions and governance-layer coverage on this pilot.

---

## Dataset Statistics


| Metric                                          | Value |
| ----------------------------------------------- | ----- |
| Firms                                           | 5     |
| Snapshot observations                           | 25    |
| Page rows                                       | 394   |
| Extraction-usable pages                         | 374   |
| Branding-corpus pages                           | 231   |
| Governance metadata pages                       | 24    |
| Primary text-analysis eligible observations     | 13    |
| Sensitivity text-analysis eligible observations | 15    |
| Manual corpus validation rows                   | 43    |


---

## Corpus Quality

- Legal/technical pages excluded from branding corpus by default
- Impressum retained separately for governance validation
- Quality-summary inconsistencies: **0**
- Non-empty analyzable text with `token_count = 0`: **0**
- Language detection populated for **386 / 394** pages (remaining short/empty)

---

## Manual Validation Status

Prior archive-validity judgments (`correct_company`, `valid_archived_page`, `temporally_appropriate`, `duplicate_capture`) were preserved from v1.0.

New corpus-validation sample in `manual_corpus_validation.csv` covers branding-included pages, legal exclusions, Impressum pages, unknown categories, and low-text observations.

---

## Remaining Limitations

1. Wayback connection instability during crawl/visual steps
2. Rule-based governance extraction leaves some structured fields null
3. Two observations excluded for insufficient branding tokens; two for no branding pages
4. Contact-page substance heuristic may require spot checks

---

## Recommendation

Pilot v1.1 meets the release definition of done for the first five firms. Proceed with review of `branding_corpus_observations_primary.csv` and `governance_metadata_observations.csv` before scaling.