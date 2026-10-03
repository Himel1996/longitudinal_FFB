# Final Rescue Impact — full_sample_v1_1_rescue_final_dm

**Generated:** 2026-10-03 21:25 UTC  
**Base final:** `full_sample_v1_1_rescue_final`  
**Definitive release:** `full_sample_v1_1_rescue_final_dm`  
**Parent primary SHA:** `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`  
**Network during assembly:** none

## Headline (recomputed)

| Metric | Prior final | After dm addendum |
|--------|------------:|------------------:|
| Primary-ready firms | 22 | **22** |
| Extended-ready firms | 27 | **28** |
| Still not extended-ready | 3 (8, 24, 30) | **2 (24, 30)** |

### Still not longitudinally ready (extended FALSE)
- **24 — Viessmann** (entity-change)
- **30 — Oetker** (entity-change / manual review)

### dm (firm 8) outcome
- post_event: `replace_with_rescue` → German **sensitivity** (5,069 tokens_de / 17 pages; fit `very_low`, Δ=441d)
- post_post_event: `retain_original` (no in-tolerance About/history capture)
- primary ready: **FALSE**
- extended ready: **TRUE**

## Decision totals (20 rescue firms incl. dm)

| Decision | Count |
|----------|------:|
| replace_with_rescue | 63 |
| retain_original | 8 |
| add_as_sensitivity_alternative | 7 |
| rejected_insufficient_text | 5 |
| remain_unavailable | 4 |
| manual_review_required | 2 |

## Methodological note

Phase B originally targeted **19** non-ready firms listed in
`full_sample_url_rescue_candidates.csv`. Post-acceptance review found firm **8 (dm)**
was the sole non-ready parent firm unintentionally absent from that candidate set.
dm was subsequently tested under **exactly the same** rescue methodology (no tolerance
or eligibility relaxation) via an isolated DM_FINAL addendum. dm gained
**extended/sensitivity** longitudinal coverage only; Viessmann and Oetker remain the
only unresolved longitudinal cases.
