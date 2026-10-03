# full_sample_v1_1_rescue_final_dm

Definitive Phase B cumulative rescue release.

## Provenance

1. Starts from frozen `full_sample_v1_1_rescue_final` (19-firm accepted Phase B rescue).
2. Offline-merges the accepted **DM_FINAL** addendum for firm 8 (dm) only.
3. Regenerates all derived corpora/coverage offline (no Wayback / crawl / discovery).

## Why dm appears here

Phase B originally targeted the **19** firms in
`data/input/full_sample_url_rescue_candidates.csv`. Post-acceptance review found
**dm (firm 8)** was the sole non-ready parent firm unintentionally absent from that
candidate set. dm was subsequently tested under **exactly the same** rescue
methodology. No temporal tolerance, text threshold, language, deduplication, legal
filtering, or prioritization rule was relaxed.

## dm outcome

- `post_event`: replace_with_rescue → German **sensitivity** (5,069 tokens_de / 17 pages;
  seed `https://dm.de/unternehmen/ueber-uns`; capture `20200416175348`; Δ=441d; fit `very_low`)
- `post_post_event`: retain_original
- primary longitudinal ready: **FALSE**
- extended longitudinal ready: **TRUE**

## Headline

| Metric | Count |
|--------|------:|
| Primary-ready | 22 / 30 |
| Extended-ready | 28 / 30 |
| Still not extended-ready | 24, 30 |

## Corpus definitions

- `full_sample_branding_corpus_observations_primary.csv` — German PRIMARY only
- `full_sample_branding_corpus_observations_sensitivity_all_languages.csv` — ALL languages sensitivity
- `full_sample_branding_corpus_observations_sensitivity_de.csv` — German-only sensitivity
- `full_sample_branding_corpus_pages_all_languages.csv` — ALL language branding pages
- `full_sample_branding_corpus_pages_de.csv` — German-only branding pages

Parent `full_sample_v1` and prior final `full_sample_v1_1_rescue_final` were not modified.
