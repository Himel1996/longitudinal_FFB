# Final Rescue Impact

**Generated:** 2026-09-24 07:35 UTC  
**Parent:** `full_sample_v1`  
**Final release:** `full_sample_v1_1_rescue_final`  
**Parent primary SHA:** `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`

## Headline (recomputed)

| Metric | Before (parent) | After (final) |
|--------|----------------:|--------------:|
| German longitudinal-ready (parent single flag / primary) | 10 | 22 primary |
| German extended-ready | 10 (same parent flag) | 27 |
| Newly primary-ready firms | — | 12 |
| Newly extended-ready firms | — | 17 |
| Firms still not extended-ready | — | 3: 8 DM-DROGERIE MARKT, 24 Viessmann, 30 Oetker |

Parent readiness used the single column `german_longitudinal_ready` (10 firms). Final release splits primary vs extended.

### Newly primary-ready
2, 10, 11, 14, 15, 16, 17, 19, 20, 23, 25, 27

### Newly extended-ready (vs parent ready set)
2, 5, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 27

### Still not longitudinally ready (extended FALSE)
- **8 — DM-DROGERIE MARKT GMBH + CO. KG** (not a Phase B rescue target)
- **24 — Viessmann** (entity-change)
- **30 — Oetker** (entity-change / manual review)

## Decision totals (19 rescue firms)

| Decision | Count |
|----------|------:|
| replace_with_rescue | 62 |
| add_as_sensitivity_alternative | 7 |
| retain_original | 7 |
| remain_unavailable | 4 |
| manual_review_required | 2 |
| rejected_* | 5 |

## Per-firm impact

See `data/releases/full_sample_v1_1_rescue_final/data/rescue_impact_by_firm.csv`.

| Firm | Batch | Prim before→after | Ext before→after | Replace | Sens-alt | Limits |
|------|-------|-------------------|------------------|--------:|---------:|--------|
| 2 | B01 | FALSE→**TRUE** | FALSE→**TRUE** | 1 | 0 | unavailable |
| 5 | B06 | FALSE→**FALSE** | FALSE→**TRUE** | 2 | 1 | extended_only |
| 10 | B_BRAUN_SMOKE | FALSE→**TRUE** | FALSE→**TRUE** | 5 | 0 | — |
| 11 | B01 | FALSE→**TRUE** | FALSE→**TRUE** | 4 | 0 | — |
| 12 | B01 | FALSE→**FALSE** | FALSE→**TRUE** | 4 | 0 | extended_only |
| 14 | B02 | FALSE→**TRUE** | FALSE→**TRUE** | 4 | 0 | — |
| 15 | B02 | FALSE→**TRUE** | FALSE→**TRUE** | 4 | 0 | — |
| 16 | B02 | FALSE→**TRUE** | FALSE→**TRUE** | 4 | 0 | — |
| 17 | B03 | FALSE→**TRUE** | FALSE→**TRUE** | 5 | 0 | — |
| 18 | B03 | FALSE→**FALSE** | FALSE→**TRUE** | 5 | 0 | extended_only |
| 19 | B03 | FALSE→**TRUE** | FALSE→**TRUE** | 2 | 0 | — |
| 20 | B04 | FALSE→**TRUE** | FALSE→**TRUE** | 5 | 0 | — |
| 21 | B05 | FALSE→**FALSE** | FALSE→**TRUE** | 2 | 1 | unavailable;extended_only |
| 22 | B05 | FALSE→**FALSE** | FALSE→**TRUE** | 4 | 0 | extended_only |
| 23 | B04 | FALSE→**TRUE** | FALSE→**TRUE** | 3 | 1 | — |
| 24 | B05 | FALSE→**FALSE** | FALSE→**FALSE** | 0 | 2 | unavailable;entity_change;not_ready |
| 25 | B04 | FALSE→**TRUE** | FALSE→**TRUE** | 5 | 0 | — |
| 27 | B06 | FALSE→**TRUE** | FALSE→**TRUE** | 3 | 1 | — |
| 30 | B06 | FALSE→**FALSE** | FALSE→**FALSE** | 0 | 1 | manual_review;unavailable;entity_change;not_ready |
