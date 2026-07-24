# Pilot v1.2 Change Report

**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Date:** 2026-07-23  
**Git commit:** `40284949bcf3e42355fcdf7fd93bacd00610c6f7`  
**Release bundle:** `data/releases/pilot_v1_2/`

---

## Christian’s three requested fixes

1. **Strict legal-page precedence** — URL/title/H1/canonical evidence must classify Impressum, Datenschutz, AGB, cookie, and related legal pages *before* broader branding categories such as `news_press`, `contact`, or `products_services`.
2. **Corpus outputs must follow observation eligibility** — `branding_corpus_observations_primary.csv` / `_sensitivity.csv` may only contain observations with `text_analysis_eligible = true`.
3. **Restrict governance / Impressum layer** — keep only direct legal/governance evidence pages (Impressum / legal notice / strong management-legal or affiliation evidence), not broader company/product pages.

---

## Root causes (v1.1)

| Issue | Root cause |
|-------|------------|
| Legal pages in branding corpus | Classification scored path + title + **body/visible text** together. Footer mentions of Impressum/Datenschutz/AGB, or mixed page content, could lose to higher `news_press` / `products_services` hits. |
| Ineligible observations in primary corpus | `build_branding_corpus_observations()` filtered by `observation_recommendation` only, ignoring `text_analysis_eligible`. |
| Broad governance layer | `governance_metadata_eligible` was true for all `impressum` **or** `management_leadership` pages, including weak “management”/company content matches. |

---

## Implementation changes

### 1. Deterministic classification precedence

Order:

1. strict legal / administrative URL+title rules (`privacy_policy`, `terms_conditions`, `cookie_notice`, `legal_other`)
2. strict technical / search / navigation-only rules
3. Impressum / legal-notice rules
4. config allow-list + dedicated governance evidence (management-legal, affiliation, ownership) on URL/title/H1 only
5. substantive branding categories
6. fallback / unknown

New page fields:

- `classification_rule_priority`
- `classification_rule_id`
- `governance_inclusion_reason`
- `governance_rule_id`
- `governance_evidence_type`

Footer-only legal words no longer reclassify a normal page.

Concrete cases now forced out of branding:

- Blue Moon `/impressum`
- Peter-Lacke `impressum.html`
- Peter-Lacke `agb.html`

### 2. Observation eligibility as export authority

- Primary corpus: `observation_recommendation == "include"` **and** `text_analysis_eligible == true`
- Sensitivity corpus: recommendation in `{include, sensitivity_analysis}` **and** `text_analysis_eligible == true`
- Added export columns: `observation_recommendation`, `text_analysis_exclusion_reason`
- Branding page export also requires eligible observations and never banned legal categories

### 3. Restricted governance layer

`governance_metadata_eligible = true` only for:

- Impressum / legal-notice (URL/title/H1)
- dedicated management/legal-representative pages with strong URL/title/H1 evidence
- corporate affiliation / ownership disclosure with strong URL/title/H1 evidence
- optional config allow-list (`analysis.governance_url_allowlist`)

Broader company/product/management body keywords alone are insufficient.

---

## Before / after counts

| Metric | v1.1 | v1.2 |
|--------|------|------|
| Branding corpus pages | 231 | **290** |
| Branding pages with Impressum/AGB/Datenschutz URL | 11 / 2 / 4 | **0 / 0 / 0** |
| Governance metadata pages | 24 | **19** |
| Primary observation corpus rows | 16 | **14** (all eligible) |
| Sensitivity observation corpus rows | 19 | **16** (all eligible) |
| `text_analysis_eligible` observations | 15–16 | **16** |

Notes:

- Branding page count rose because many pages previously false-tagged as privacy/legal via footer/body text are now correctly classified as substantive branding pages.
- Primary/sensitivity row counts now reconcile exactly with eligible rows in `observation_text_summary.csv`.

---

## Legal pages removed from branding corpus

From v1.1 branding URLs that contained legal path tokens:

- **11** Impressum URLs removed
- **2** AGB URLs removed
- **4** Datenschutz URLs removed

Banned categories currently in `branding_corpus_pages.csv`: **0**.

---

## Governance pages retained / excluded

- Retained: **19** pages (`impressum` 17, `corporate_affiliation` 2)
- Removed vs v1.1: broader management/company candidates no longer eligible without strong legal/governance URL/title evidence

---

## Final NLP-eligible observation counts

- Primary NLP corpus: **14**
- Sensitivity NLP corpus: **16**

---

## Consistency checks

Hard release checks now fail if:

1. branding corpus contains impressum/privacy/terms/cookie/legal_other
2. primary/sensitivity corpora contain `text_analysis_eligible != true`
3. primary/sensitivity counts/keys disagree with `observation_text_summary.csv`
4. governance observation URLs are not traceable to governance pages

Result for this build: **PASSED**.

---

## Tests

- New/updated classification tests for Blue Moon impressum, Peter-Lacke impressum.html, Peter-Lacke agb.html, footer non-reclassification, governance body-keyword rejection
- New corpus export tests reproducing the ineligible-observation bug and legal-page export filter
- Full suite: **47 passed**

---

## Remaining limitations

1. Classification remains rule-based; ambiguous hybrid pages may still need spot checks.
2. Governance structured fields remain regex/rule-based and may be null when Impressum text is sparse.
3. Wayback intermittency and archive chrome in `visible_text` are unchanged from prior releases.
4. Two `corporate_affiliation` governance pages are included on strong URL/title evidence; Christian may prefer Impressum-only — easy to tighten further via config/rules.

---

## Recommendation on scaling

**YES, with a short confirmation pass from Christian** on:

1. `branding_corpus_observations_primary.csv` (14 eligible observations)
2. zero legal URLs in `branding_corpus_pages.csv`
3. `governance_metadata_pages.csv` restricted set (19 pages)

If those three look correct, scale to the remaining 25 firms under the same v1.2 rules.
