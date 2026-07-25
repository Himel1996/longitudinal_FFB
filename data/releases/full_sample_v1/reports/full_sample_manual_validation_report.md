# Full-Sample Manual Validation Report

**Run ID:** `508f1903-71e7-4aab-aba6-000fed4d8b7d`  
**Sample file:** `data/output/full_sample_manual_validation.csv`  
**Method:** Stratified sample (not full manual review), scored from pipeline evidence (extraction/HTML/status). Playwright screenshots were not re-run for all 30 firms in this pass.

## Sample design

Target **40** observations, stratified across:

- firms (prefer ≥1 per firm when selected snapshots exist)
- timepoints
- event types
- language classes
- include / sensitivity / exclude recommendations
- duplicate-heavy observations
- low-usable / thin observations
- Playwright-dependent extraction methods
- page-category presence (about, history, news, impressum, careers)

## Results (pipeline-evidence scoring)

| Check | True | Rate |
|-------|-----:|-----:|
| Sample size | 40 | — |
| Distinct firms | 27 | — |
| Correct company | 39 | 97.5% |
| Valid archived page | 39 | 97.5% |
| Content extraction usable | 32 | 80.0% |
| Temporally appropriate | 30 | 75.0% |

Timepoint mix in sample: event 11 · pre_event 11 · pre_pre_event 9 · post_post_event 6 · post_event 3.

## Interpretation

- High company/archive validity shows snapshot selection and domain targeting remain stable at 30 firms.
- Content-usable rate of 80% reflects thin/homepages-only and failed Wayback fetches retained in the grid.
- Temporal appropriateness below 100% is expected under the existing tolerance / future / event-unavailable rules (not a new regression).

## Supporting samples

Also regenerated:

- `manual_corpus_validation.csv` (93 rows)
- `manual_scaling_validation.csv` (61 rows)

Consistency checks: **PASSED**.
