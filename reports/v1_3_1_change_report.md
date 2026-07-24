# Pilot v1.3.1 Change Report

**Date:** 2026-07-24  
**Release:** `data/releases/pilot_v1_3_1/`  
**Predecessor archive:** `data/archive/pilot_v1_3_pre_final_priority_rebuild/`  
**Run ID:** `6f4f1dd0-8f2a-42ca-ae1d-7f3067b47fc9`  
**Git commit (pipeline code):** `565da6bfd8969793d64c80a4d2d68850a25e4191`

## Why v1.3.1

v1.3 accepted the scaling architecture, but legal-path demotion under `/unternehmen/` was added **after** the v1.3 crawl. Code and released crawl outputs were therefore out of sync.

v1.3.1 is a **clean five-firm rebuild** with final prioritization applied during crawl.

## What changed in prioritization

Legal/privacy/terms path markers (`impressum`, `agb`, `datenschutz`, `privacy`, `cookie`, …) are forced to tier 3 and cannot receive reserved About/company slots, even when nested under `/unternehmen/` or `/über-uns/`.

## Rebuild procedure

1. Archived `data/releases/pilot_v1_3/` → `data/archive/pilot_v1_3_pre_final_priority_rebuild/`
2. Cleared crawl/corpus outputs (kept CDX + immutable HTML caches)
3. Ran `prepare` → `discover-snapshots` → `crawl` → validate/export → reports
4. Consistency checks + tests + release bundling with git-commit sync enforcement

## Confirmation checks

| Check | Result |
|-------|--------|
| Legal `/unternehmen/` pages consume reserved company/About slots | **0** (was 11 reserved-slot / 5 company-category cases in v1.3) |
| Foreign-language pages consume reserved slots | **0** |
| Within-timepoint content duplicates removed from branding | **PASS** |
| Cross-timepoint identical content preserved | **61** multi-timepoint hash groups retained |
| German primary corpus only eligible German observations | **PASS** (14 primary) |
| Observation token sums == deduplicated eligible page tokens | **PASS** |
| Consistency script | **PASSED** |
| Tests | **66 passed** |
| Manifest git commit matches pipeline code | **PASS** (`565da6b…`) |

## v1.3 → v1.3.1 comparison

| Metric | v1.3 | v1.3.1 | Δ |
|--------|------|--------|---|
| Page rows | 394 | 394 | 0 |
| Distinct page URLs swapped | — | +21 / −21 | frontier changed |
| Branding pages (all languages) | 235 | 249 | +14 |
| Branding pages (de) | 230 | 243 | +13 |
| Primary observations | 14 | 14 | 0 |
| Sensitivity observations | 16 | 16 | 0 |
| Duplicate summary rows | 83 | 86 | +3 |
| Duplicate tokens removed | 8,640 | 8,912 | +272 |
| Branding token sum (all obs) | 63,122 | 67,967 | +4,845 |
| German tokens (obs sum) | 62,585 | 67,398 | +4,813 |
| High-priority fetched (sum) | 146 | 140 | −6* |
| High-priority missing (sum) | 107 | 101 | −6 |
| MYRENNE pre_event branding tokens | 3,682 | 3,878 | +196 |

\*High-priority counts fall partly because legal `/unternehmen/*` URLs are **no longer counted as high-priority discoveries**, which is the intended demotion.

### Legal pages demoted / displaced from crawl selection

Examples removed from the selected frontier vs v1.3:

- `http://www.peter-lacke.de/unternehmen/impressum.html`
- `http://www.peter-lacke.de/unternehmen/agb.html`
- `http://www.peter-lacke.de/unternehmen/standorte/agb.html`
- `https://www.bluemoon.de/impressum` (multiple timepoints)
- `http://myrenne.com/de/impressum.html`

### High-priority pages newly included (examples)

- `http://www.peter-lacke.de/kontakt/unternehmen/philosophie.html` (event)
- Additional `/unternehmen/` non-legal pages that previously lost slots to Impressum/AGB

## Scaling baseline

**`pilot_v1_3_1` is the definitive scaling baseline** for `config/full_sample.yaml`.

Do not scale the remaining 25 firms from the unsynchronized v1.3 crawl.
