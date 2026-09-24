# full_sample_v1_1_rescue_final

**Status:** `FROZEN`  
**Acceptance verdict:** `READY_TO_FREEZE_WITH_DOCUMENTED_LIMITATIONS`  
**Parent release:** `full_sample_v1` (unchanged)

## What this is

Authoritative **cumulative Phase B** German-language Wayback rescue release for the full 30-firm sample.

It starts from the frozen parent release `data/releases/full_sample_v1/` and applies accepted rescue decisions for the 19 firms that lacked German longitudinal coverage, including B. Braun plus batches B01–B06.

## Relationship to other releases

| Release | Role |
|---------|------|
| `full_sample_v1` | Frozen parent. **Do not modify.** Baseline for all non-rescued cells. |
| `full_sample_v1_1_rescue` | Intermediate batch-targeted packaging used during sequential Phase B runs. **Not** the authoritative cumulative product. |
| `full_sample_v1_1_rescue_final` | **This release.** Cumulative accepted Phase B output for analysis and publication. |

Parent primary corpus SHA-256:

`c54fc35698b2b2e962b40ed0a75170ba66d6dd03352b6f34eee55304022d6c27`

## Why targeted rescue was needed

The parent full-sample pipeline left 19 firms without usable German longitudinal branding observations (often English-only captures, wrong historical domain, or insufficient German text). Phase B re-selected German Wayback captures under the same validated extraction, language, legal-filtering, deduplication, and temporal-tolerance rules, then accepted replacements only where rescue improved German evidence without relaxing methodology.

## Corpus definitions

| File | Contents |
|------|----------|
| `data/full_sample_branding_corpus_observations_primary.csv` | **German PRIMARY** observations only |
| `data/full_sample_branding_corpus_observations_sensitivity_de.csv` | **German-only** sensitivity observations |
| `data/full_sample_branding_corpus_observations_sensitivity_all_languages.csv` | **All-language** sensitivity observations |
| `data/full_sample_branding_corpus_observations_sensitivity.csv` | Legacy alias of the all-language sensitivity corpus |
| `data/full_sample_branding_corpus_pages_de.csv` | **German-only** branding pages |
| `data/full_sample_branding_corpus_pages_all_languages.csv` | **All-language** branding pages |

**Primary** = German-eligible observations recommended for main analysis.  
**Sensitivity** = alternate / temporally weaker / migration- or entity-flagged paths retained for robustness checks.

## Longitudinal readiness

See `data/firm_longitudinal_coverage.csv`.

- **Primary ready:** ≥1 German primary observation pre-event **and** ≥1 post-event.
- **Extended ready:** ≥1 German-eligible observation pre-event **and** ≥1 post-event (primary or sensitivity path).

Accepted headline (recomputed at freeze):

- Primary ready: **10 → 22**
- Extended ready: **10 → 27**

Still not extended-ready:

- **8 — DM-DROGERIE MARKT GMBH + CO. KG** (not a Phase B rescue target)
- **24 — Viessmann** (entity-change / organizational comparability)
- **30 — Oetker** (entity-change / manual review)

## Special-case treatment

| Firm | Treatment in this release |
|------|---------------------------|
| 5 MSF | Minimum text-volume threshold enforced; extended-ready only |
| 21 Freudenberg | Sensitivity / migration treatment; extended-ready only |
| 22 STIHL | Sensitivity / migration treatment; extended-ready only |
| 24 Viessmann | `entity_change_flag` preserved; not longitudinally ready |
| 30 Oetker | `entity_change_flag` + manual-review decisions preserved; not longitudinally ready |

## Decisions and impact

- Cumulative accepted decisions: `data/rescue_comparison_decisions_FINAL.csv`
- Per-firm impact: `data/rescue_impact_by_firm.csv`
- Acceptance report: `reports/final_release_acceptance.md`
- Impact report: `reports/final_rescue_impact.md`
- Immutable freeze inventory: `freeze_manifest.json` (and `data/freeze_manifest.json`)

## Documented limitations

1. Remaining Wayback transport failures stay `FETCH_FAILED_RESUMABLE` in interim state; they were **not** converted to `archive_unavailable`.
2. Entity-change firms (Viessmann, Oetker) are deliberately not claimed as longitudinally comparable.
3. Some rescued firms are extended-ready only because of sensitivity/temporal rules.
4. Small observation vs page token residual remains (smaller than parent residual).
5. Cumulative assembly was offline (no Wayback contact). B02–B05 pages were reconstructed from local cache; B. Braun, B01, and B06 used accepted persisted extracts.

## Files for downstream analysis

Prefer:

1. German primary observations  
2. German sensitivity observations (if needed)  
3. `firm_longitudinal_coverage.csv`  
4. `rescue_comparison_decisions_FINAL.csv` / `rescue_impact_by_firm.csv`

Use all-language corpora only when explicitly studying non-German sensitivity paths.

## Reproducibility

- Parent config copy: `config/full_sample.yaml`
- Rescue config copy: `config/full_sample_rescue.yaml`
- Assembly was no-network and does not modify `full_sample_v1`
- File-level SHA-256 inventory is in `freeze_manifest.json`
