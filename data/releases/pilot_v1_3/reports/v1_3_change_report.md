# Pilot v1.3 Change Report

**Date:** 2026-07-24  
**Scope:** First five firms only  
**Predecessor:** Pilot v1.2 (`data/archive/pilot_v1_2_pre_v1_3/`)

## Motivation

Christian Schröder’s final technical points for scaling readiness:

1. Within firm × timepoint deduplication (www/non-www and equivalent URL/content variants).
2. Hybrid language handling (crawl-time path deprioritization + post-extraction inclusion).
3. Reserved-slot prioritization so news/product/foreign sections cannot crowd out branding pages.

Family-branding dictionary work remains out of scope.

## Changes

### 1. URL canonicalization + within-observation deduplication

- New module: `src/ffb_webminer/crawl/url_canonical.py`
- New module: `src/ffb_webminer/quality/deduplication.py`
- Canonicalize www/non-www, default ports, HTTP/HTTPS identity, trailing/index paths, fragments, empty queries, Wayback wrappers.
- Deduplicate on normalized content hash **within** `firm_id × relative_timepoint` only.
- Cross-timepoint identical content is retained (longitudinal signal).
- Duplicate rows remain in `pages.csv` with `branding_corpus_eligible=false` and `branding_corpus_exclusion_reason=duplicate_within_observation`.
- New outputs: `duplicate_summary.csv`.

### 2. Hybrid language handling

- New module: `src/ffb_webminer/crawl/language_paths.py`
- New module: `src/ffb_webminer/quality/language_inclusion.py`
- Crawl-time path hints (`preferred_german` / `neutral_or_unknown` / `foreign_language_deprioritized`).
- Page-level language detector remains final authority for corpus inclusion.
- Language-specific page/observation corpora:
  - `branding_corpus_pages_{all_languages,de,en,other}.csv`
  - `branding_corpus_observations_{all_languages,de,en,other}.csv`
- `branding_corpus_observations_primary.csv` is **German-only** (`primary_corpus_language: de`).

### 3. Reserved-slot staged crawl

- New module: `src/ffb_webminer/crawl/priority.py`
- Reworked `src/ffb_webminer/crawl/crawler.py` staged selection:
  1. homepage
  2. reserved high-value branding categories (German preferred; foreign paths cannot consume reserved slots)
  3. flexible secondary / broad / overflow unused reserved
- New output: `crawl_priority_summary.csv`

### 4. Configuration for full sample

- `config/full_sample.yaml` ready for 30 firms (not executed yet).
- Pilot config extended with reserved slots, deduplication, and German corpus thresholds.

## Consistency rules enforced

1. No identical normalized content twice within a firm × timepoint branding corpus.
2. Cross-timepoint identical content is not removed globally.
3. German primary pages must not be confidently non-German.
4. Observation branding token totals match deduplicated eligible page token sums.
5. Duplicate rows excluded from aggregated branding text.
6. Language corpora URLs traceable to `pages.csv`.

## Tests

New coverage:

- `tests/test_deduplication.py`
- `tests/test_language_corpus.py`
- `tests/test_crawl_priority.py`

Full suite: see completion report after rebuild.

## Rebuild notes

- Archived v1.2 → `data/archive/pilot_v1_2_pre_v1_3/`
- Re-crawled first five firms with reserved-slot prioritization (HTML/CDX caches retained).
- Regenerated corpora, quality summaries, governance outputs, manual scaling validation, and release bundle under `data/releases/pilot_v1_3/`.

## Completion metrics (five firms)

| Metric | Value |
|--------|-------|
| Duplicate pages flagged/removed from branding | 83 |
| Duplicate tokens removed | 8,640 |
| MYRENNE pre_event branding tokens before (v1.2) | 6,639 |
| MYRENNE pre_event branding tokens after (v1.3) | 3,682 |
| MYRENNE pre_event duplicate pages within observation | 10 |
| Cross-time MYRENNE content groups preserved | 5 |
| Branding pages all / de / en / other | 235 / 230 / 2 / 3 |
| German primary corpus observations | 14 |
| German text-analysis eligible observations | 16 |
| High-priority pages fetched (sum over observations) | 146 |
| Secondary / broad pages fetched | 113 / 130 |
| Foreign paths deprioritized (discovered) | 4 |
| Consistency checks | PASSED |
| Tests | 66 passed |

## Scaling readiness

`config/full_sample.yaml` is ready for the remaining 25 firms. Do **not** run it until Christian confirms v1.3.

Note: during this rebuild, some `/unternehmen/*` legal URLs were still scored as high-priority before a late legal-path demotion fix. That fix is now in `crawl/priority.py` and covered by tests; the next crawl will no longer reserve slots for Impressum/AGB/privacy paths.