# Firm Longitudinal Coverage Summary — `full_sample_v1`

**Phase:** A (analytical exports only; no extraction changes)  
**Generated:** 2026-07-29 06:39 UTC  
**Source release:** `data/releases/full_sample_v1/`

## Headline

| Metric | Value |
|--------|------:|
| Total firms | 30 |
| German longitudinal-ready firms | 10 |
| Non-ready firms | 20 |

**Definition:** `german_longitudinal_ready = TRUE` iff the firm has ≥1 German text-eligible
observation in {`pre_pre_event`, `pre_event`} **and** ≥1 in {`post_event`, `post_post_event`}.

## Distribution of German eligible observations (pre + post slots)

Counts are `n_pre_event_german_eligible + n_post_event_german_eligible` per firm.

| Count | Firms |
|------:|------:|
| 0 | 9 |
| 1 | 5 |
| 2 | 6 |
| 3 | 7 |
| 4 | 3 |

## Distribution of primary observations per firm

| Count | Firms |
|------:|------:|
| 0 | 12 |
| 1 | 3 |
| 2 | 4 |
| 3 | 6 |
| 4 | 3 |
| 5 | 2 |

## Distribution of sensitivity observations (all-language) per firm

| Count | Firms |
|------:|------:|
| 0 | 4 |
| 1 | 4 |
| 2 | 6 |
| 3 | 3 |
| 4 | 6 |
| 5 | 7 |

## Firms requiring rescue (not German longitudinal-ready)

| firm_id | company | pre_DE | post_DE | primary | sensitivity_all | notes |
|--------:|---------|-------:|--------:|--------:|----------------:|-------|
| 2 | PETER-LACKE HOLDING GMBH | 2 | 0 | 2 | 3 | `missing_post` |
| 5 | MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG | 0 | 2 | 2 | 2 | `missing_pre` |
| 8 | DM-DROGERIE MARKT GMBH + CO. KG | 2 | 0 | 3 | 3 | `missing_post` |
| 10 | B. BRAUN SE | 0 | 0 | 0 | 2 | `no_german;missing_pre;missing_post` |
| 11 | HARTING TECHNOLOGY GROUP | 0 | 0 | 0 | 0 | `no_german;missing_pre;missing_post` |
| 12 | DIRK ROSSMANN GMBH | 1 | 0 | 1 | 1 | `missing_post` |
| 14 | CLAAS KGAA MBH | 0 | 0 | 0 | 0 | `no_german;missing_pre;missing_post;unavailable` |
| 15 | FABER-CASTELL AG | 2 | 0 | 2 | 5 | `missing_post` |
| 16 | HENKEL AG & CO. KGAA | 0 | 0 | 0 | 4 | `no_german;missing_pre;missing_post` |
| 17 | MERCK KGAA | 0 | 0 | 0 | 0 | `no_german;missing_pre;missing_post;unavailable` |
| 18 | SCHAEFFLER AG | 0 | 0 | 0 | 0 | `no_german;missing_pre;missing_post;unavailable` |
| 19 | HERAEUS GROUP | 1 | 0 | 1 | 1 | `missing_post` |
| 20 | BAHLSEN GMBH & CO. KG | 0 | 0 | 0 | 2 | `no_german;missing_pre;missing_post` |
| 21 | FREUDENBERG GROUP | 0 | 1 | 0 | 4 | `missing_pre;sensitivity_only` |
| 22 | ANDREAS STIHL AG & CO. KG | 0 | 0 | 0 | 2 | `no_german;missing_pre;missing_post` |
| 23 | VAILLANT GROUP | 1 | 0 | 1 | 5 | `missing_post` |
| 24 | VIESSMANN CLIMATE SOLUTIONS / VIESSMANN GROUP | 0 | 0 | 0 | 1 | `no_german;missing_pre;missing_post` |
| 25 | BIRKENSTOCK GROUP | 2 | 0 | 2 | 2 | `missing_post` |
| 27 | DOUGLAS HOLDING / DOUGLAS GROUP | 0 | 1 | 0 | 1 | `missing_pre;sensitivity_only` |
| 30 | DR. AUGUST OETKER KG / OETKER-GRUPPE | 0 | 2 | 0 | 2 | `missing_pre;sensitivity_only` |

## Notes

- German eligibility uses the existing release flag `german_text_analysis_eligible`.
- Sensitivity observation counts refer to the all-language sensitivity export.
- This summary does not modify extraction outputs.
