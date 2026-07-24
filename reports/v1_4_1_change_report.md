# Pilot v1.4.1 Change Report

**Date:** 2026-07-24  
**Release:** `data/releases/pilot_v1_4_1/`  
**Predecessor:** `data/archive/pilot_v1_4_pre_v1_4_1/`  
**Run ID:** `95bac495-6940-47be-b3ff-339fd97afa3e`  
**Git commit:** `5a5fec78333d7baead292037b2be2a94f6733366`

## Purpose

Targeted release-acceptance fix for the two blockers found in `pilot_v1_4`:

1. Reserved-slot misclassification from unrestricted substring matching of `unternehmen`
2. Zero-token usable Chinese page (`token_count == 0` with substantive text)

No remaining-25 scaling. Snapshot selection, legal filtering, governance scope, deduplication, language corpus rules, and observation eligibility were left unchanged except where required by these two fixes.

## Token policy (choice A)

`token_count` is redefined as **`analysis_token_count`**.

| Field | Meaning |
|-------|---------|
| `character_count` | Normalized character length |
| `word_count` | Word-like units for the chosen tokenizer |
| `lexical_token_count` | Latin/German regex tokens |
| `analysis_token_count` | Language-appropriate tokens used in aggregation |
| `token_count` | Alias of `analysis_token_count` |
| `tokenization_method` | `latin_lexical_regex` or `unicode_cjk_chars` |
| `tokenization_status` | `ok` / `empty` / `no_tokens` |

CJK pages use deterministic Unicode ideograph counts (`unicode_cjk_chars`). German primary corpora continue to use German-compatible lexical tokens only via language eligibility gates.

## Rebuild procedure

1. Archived `pilot_v1_4` → `data/archive/pilot_v1_4_pre_v1_4_1/`
2. Cleared crawl/corpus outputs; reused CDX + HTML caches
3. `prepare` → `discover-snapshots` → `crawl` → validate/export → reports
4. Manual corpus + scaling validation samples
5. Consistency checks + unit tests (81 passed)
6. Release acceptance audit + release bundle

## Comparison vs pilot_v1_4

### Reserved-slot assignments

| Change | Count |
|--------|------:|
| Reserved selections removed | 4 |
| Reserved selections added | 3 |

**False `company_about` reserved assignments removed:**

- Blue Moon press slug containing “unternehmen” as article text
- Peter-Lacke `/unternehmen/news.html`
- Peter-Lacke `/unternehmen/karriere/...` (pre_pre_event, pre_event)

**True high-priority pages newly selected under reserved slots:**

- Peter-Lacke `/unternehmen/philosophie.html` (event)
- Peter-Lacke `/unternehmen/unternehmensgruppe/...` (pre_pre_event, pre_event)

### Crawl / corpus

| Metric | v1.4 | v1.4.1 |
|--------|-----:|-------:|
| Pages | 394 | 394 |
| Page URL churn (added/removed) | — | 49 / 49 |
| Usable pages | 384 | 376 |
| Branding pages (all / de / en / other) | 249 / 243 / 2 / 4 | 242 / 234 / 4 / 4 |
| German primary observations | 14 | 14 |
| Sensitivity observations | 16 | 16 |
| Duplicate rows / tokens removed | 86 / 8,912 | 93 / 9,456 |
| Branding token sum | 67,967 | 66,770 |
| Tokens DE sum | 67,398 | 63,986 |

### Chinese Peter-Lacke page

`http://www.peter-lacke.de/chn/peter-lacke/company/company.html`

| Field | v1.4 | v1.4.1 |
|-------|------|-------|
| `character_count` | 809 | 809 |
| `lexical_token_count` | (n/a / 0) | 0 |
| `analysis_token_count` / `token_count` | 0 | **716** |
| `tokenization_method` | — | `unicode_cjk_chars` |
| `usable_for_analysis` | true (invalid) | true (valid) |
| `german_corpus_eligible` | false | false |

## Tests and acceptance

- Unit tests: **81 passed**
- Consistency checks: **PASSED**
- Manifest ↔ code git sync: **PASSED** (manifest commit = `5a5fec7…`)
- Release acceptance audit: **READY TO SCALE**

See `reports/release_acceptance_audit.md` for the full audit verdict.

## Scaling

**READY TO SCALE** for the remaining 25 firms via `config/full_sample.yaml` (run only when you explicitly choose to).
Baseline config for later scaling remains `config/full_sample.yaml`.
