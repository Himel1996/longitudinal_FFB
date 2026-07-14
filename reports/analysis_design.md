# Pilot Analysis Design

**Project:** Family Firm Branding in Transition  
**Stage:** Descriptive pilot — no dictionary scoring, no causal inference  
**Data source:** `data/output/analysis_observations.csv` (primary) and `data/output/analysis_observations_sensitivity.csv` (extended pool)

---

## Research question (pilot)

How do communicated family-branding signals on corporate websites differ between valid pre-event and post-event archived observations around ownership or leadership transitions?

This pilot establishes whether archived web data supports descriptive before/after comparison at firm level. It does **not** estimate causal effects of transitions on branding.

---

## Unit of analysis

- **Observation:** one firm × one relative timepoint (`pre_pre_event`, `pre_event`, `event`, `post_event`, `post_post_event`) with a selected Wayback snapshot.
- **Page-level extraction:** homepage and focused branding-relevant subpages within each observation, tagged by `observation_scope`.
- **Event timing:** `event_date_final` from verified config (`config/event_dates.yaml`) when available; label parsing yields `event_date_inferred` only and does not silently become verified.

---

## Primary strategy: nearest valid pre vs nearest valid post

**Goal:** Maximize temporal validity while keeping a simple two-point comparison per firm.

1. For each firm, select the **nearest valid pre-event** observation:
   - `observation_recommendation == include`
   - `analysis_eligible == True`
   - `relative_timepoint` in `{pre_pre_event, pre_event}`
   - Prefer `pre_event`; use `pre_pre_event` only if `pre_event` is unavailable or excluded.

2. Select the **nearest valid post-event** observation:
   - Same eligibility filters
   - `relative_timepoint` in `{post_event, post_post_event}`
   - Prefer `post_event`; use `post_post_event` if needed.

3. Compare extracted text fields (`main_text`, metadata, headings) descriptively between the two selected timepoints.

**Exclusions from primary analysis:**
- Duplicate archive captures (`exclude_duplicate_capture`) — only the theoretically closest timepoint is analysis-eligible.
- Observations outside temporal tolerance or marked `exclude`.
- `event_unavailable` at the event timepoint (e.g. no homepage capture within tolerance of verified event date).

---

## Secondary strategy: full five-point trajectories

Where **three or more** timepoints are `include` and `analysis_eligible`, describe trajectories across all five relative timepoints:

| Timepoint | Role |
|-----------|------|
| `pre_pre_event` | Earliest baseline |
| `pre_event` | Immediate pre-transition |
| `event` | Transition window (often month/year precision) |
| `post_event` | Immediate post-transition |
| `post_post_event` | Longer-run post-transition |

Use for visual inspection of continuity, step changes, and missing periods. Do not impute missing timepoints.

---

## Sensitivity strategy

Use `analysis_observations_sensitivity.csv`, which adds observations with `observation_recommendation == sensitivity_analysis`:

- Low temporal fit (`very_low`) where flagged for sensitivity only
- Adjacent-period overlap (same firm, captures closer than minimum gap)
- Subpage-only observations (`observation_scope == subpages_only`)
- Event snapshots captured before verified event date

Re-run descriptive comparisons including these rows to assess robustness. Label all sensitivity outputs explicitly; never merge silently into primary results.

---

## Observation scope handling

| Scope | Interpretation |
|-------|----------------|
| `homepage_plus_subpages` | Homepage and branding subpages crawled |
| `homepage_only` | Homepage only |
| `subpages_only` | No usable homepage; subpages provide partial signal |
| `unavailable` | No crawlable archived content for this timepoint |

Primary tables should prefer `homepage_plus_subpages` and `homepage_only`. Subpage-only rows appear only in sensitivity analyses unless manually validated.

---

## Text fields (no NLP scoring yet)

Per page, keep separate fields for downstream coding:

- `main_text` — trafilatura (or readability fallback) body extraction
- `visible_text` — full visible DOM text
- `headings_json`, `document_title`, meta/OG fields — structured metadata

**Not in scope for this pilot:** dictionary-based family-branding scores, sentiment models, or automated theme classification.

---

## Quality gates before analysis

1. Manual validation: complete `manual_validation_sample.csv` for all include and sensitivity observations.
2. Confirm `correct_company`, `valid_archived_page`, `temporally_appropriate`, `content_extraction_usable`.
3. Confirm no duplicate capture enters analysis twice (`duplicate_capture` / `duplicate_capture_flag`).
4. Review `firm_coverage_matrix.csv` for per-firm temporal gaps.

---

## Reporting standards

- Report counts of included, sensitivity, and excluded observations.
- Report observation scope distribution.
- Describe changes descriptively (presence/absence of terms, section headings, visual cues from optional screenshots).
- **No inferential claims** about transition effects at this stage.
- Flag firms with incomplete trajectories rather than forcing balanced panels.

---

## File reference

| File | Purpose |
|------|---------|
| `analysis_observations.csv` | Primary analysis pool (`include` only) |
| `analysis_observations_sensitivity.csv` | Primary + sensitivity pool |
| `firm_coverage_matrix.csv` | Per-firm recommendation by timepoint |
| `manual_validation_sample.csv` | Full manual review checklist |
| `pages.csv` | Page-level extraction with eligibility flags |
| `snapshots.csv` | Snapshot selection with temporal validity metadata |
