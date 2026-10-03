# Final Release Acceptance — full_sample_v1_1_rescue_final_dm

**Generated:** 2026-10-03 21:25 UTC  
**Release:** `data/releases/full_sample_v1_1_rescue_final_dm/`  
**Base:** `data/releases/full_sample_v1_1_rescue_final/`  
**Parent primary SHA:** `c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`  
**Network during assembly:** none  
**Release status:** `FROZEN`  
**Verdict:** `READY_TO_FREEZE_WITH_DOCUMENTED_LIMITATIONS`

---

## Scorecard

| Check | Result |
|-------|--------|
| cumulative_decisions | **PASS** |
| prior_19_decisions_preserved | **PASS** |
| bbraun_preservation | **PASS** |
| legal_exclusion | **PASS** |
| governance_scope | **PASS_WITH_NOTES** |
| primary_german_purity | **PASS** |
| sensitivity_de_german_purity | **PASS** |
| within_timepoint_dedup | **PASS** |
| token_consistency | **PASS** |
| dm_temporal_very_low | **PASS** |
| tolerance_not_relaxed | **PASS** |
| transport_not_archive_unavailable | **PASS** |
| non_targeted_regression | **PASS** |
| parent_sha | **PASS** |
| base_final_untouched | **PASS** |
| nineteen_firm_candidate_csv_untouched | **PASS** |
| dm_incorporation | **PASS** |
| headline_primary_22 | **PASS** |
| headline_extended_28 | **PASS** |
| headline_not_ready_24_30 | **PASS** |
| special_cases | **PASS** |

## Coverage

| Metric | Prior final | After |
|--------|------------:|------:|
| Primary ready | 22 | **22** |
| Extended ready | 27 | **28** |

**Still not extended-ready:** 24, 30

## dm addendum

- Initial Phase B targeted 19 firms from Christian’s candidate CSV.
- Post-acceptance review identified dm (firm 8) as the sole non-ready parent firm
  unintentionally absent from that set.
- dm was tested under the same rescue methodology (isolated DM_FINAL).
- dm gained extended/sensitivity longitudinal coverage (post_event only).
- No methodology or tolerance was changed.
- Viessmann (24) and Oetker (30) remain the only unresolved longitudinal cases.

## Documented limitations

- dm post_event is sensitivity-only (`very_low` temporal fit, Δ=441d).
- dm post_post_event unrecovered (About/history captures outside 548d).
- Viessmann / Oetker entity-change / manual-review constraints unchanged.
- Observation vs DE page token residual Δ=124.

**Hard fails:** none
