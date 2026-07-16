# Architecture Decision Record: ARGUS vs New Pipeline

**Date:** 2026-07-13  
**Status:** Accepted  
**Decision:** **C — Build a modern independent pipeline while reusing/adapting specific ARGUS concepts**

---

## Context

The pilot requires longitudinal archived-web data collection for five family firms across five relative time points (25 observations), with CDX-based snapshot selection, Wayback replay crawling, page-level text/metadata extraction, quality assurance, and optional homepage visual analysis.

ARGUS was audited in [`argus_technical_assessment.md`](argus_technical_assessment.md).

---

## Decision

Implement **`ffb_webminer`** as a new Python 3.11+ package in `src/`, with ARGUS kept unmodified in `external/ARGUS` as a methodological benchmark only.

---

## Rationale

| Criterion | ARGUS (A/B) | New pipeline (C) |
|-----------|-------------|------------------|
| Wayback / CDX support | Missing (`webarchive` spider absent) | Native module |
| Cross-platform | Windows-only paths, scrapyd GUI | macOS/Linux/Windows CLI |
| Provenance fields | Single `url`, download timestamp | Original + replay URL, snapshot timestamp, distance |
| Future time points | Not modeled | Explicit `future_unavailable` rows |
| Dependency health | Scrapy 1.x patterns, pandas 1.x APIs | Pinned modern stack |
| Visual extraction | Not possible | Optional Playwright module |
| Publication reproducibility | scrapyd + GUI + manual postprocessing | Config-driven CLI + manifest |
| License isolation | GPLv3 coupling if extended | Clean separation from GPL code |

ARGUS concepts reused **without copying GPL code**:

- Page-level (not firm-aggregated) output rows
- Same-registrable-domain crawl scope with explicit subdomain tracking
- Short-URL and language-path prioritization heuristics
- Transparent exclusion logging rather than silent drops

---

## Alternatives Considered

### A. Extend ARGUS directly

**Rejected.** Would require rewriting domain logic, adding CDX client, replacing Windows orchestration, and implementing missing `webarchive` spider. Effectively a fork under GPLv3 with high maintenance cost and no working archive baseline.

### B. Wrap ARGUS as one component

**Rejected.** ARGUS cannot crawl Wayback replay URLs reliably (domain parsing treats `web.archive.org` as the site). Wrapping would still require a parallel archive layer that duplicates most crawl logic. Two coupled systems increase failure modes.

### D. ARGUS as benchmark only

**Accepted as complement to C.** ARGUS output schema and Kinne et al. (2020) methodology inform field design but are not executed in the pilot.

---

## Chosen Architecture

```
src/ffb_webminer/
  archive/          # CDX client, snapshot selection, Wayback URL helpers
  crawl/            # Focused site crawl, link policy, HTTP fetcher
  extract/          # Text, metadata, domain parsing, optional visuals
  pipeline/         # Orchestration, schemas, I/O
  quality/          # Automated checks, validation samples
  config.py         # YAML loading
  __main__.py       # CLI entry points
```

**Data flow:**

1. `prepare` — read CSV, emit `firms.csv`, generate firm × timepoint grid
2. `discover-snapshots` — CDX queries per observation, emit `snapshots.csv`
3. `crawl` — fetch pages from selected replay URLs, store raw HTML
4. `extract` — parse HTML → `pages.csv`
5. `visuals` — optional Playwright homepage analysis → `homepage_visuals.csv`
6. `report` — quality summary, manual validation sample, markdown report

**Caching:** `data/interim/cdx/`, `data/interim/html/`, `data/interim/state/` for resume support.

---

## Maintenance Implications

- **Owned codebase:** Full control over bug fixes and field additions.
- **Dependency updates:** Managed via `pyproject.toml` version constraints.
- **ARGUS upstream:** No merge burden; reference only.
- **Internet Archive API changes:** Isolated in `archive/` module.

---

## Reproducibility Implications

- `run_manifest.json` records config hash, package versions, git commit, run timestamp.
- CDX responses and HTML cached by content-addressed paths.
- Snapshot selection rules fully specified in `config/pilot.yaml`.
- No GUI or manual postprocessing steps.

---

## Licensing Implications

- `external/ARGUS` remains GPLv3, unmodified.
- `src/ffb_webminer` developed independently; license chosen by research team (default: project README notes ARGUS citation only).
- No GPL code copied into `src/`.

---

## Compatibility Assessment

| Requirement | Supported |
|-------------|-----------|
| Wayback CDX discovery | Yes — `archive/cdx_client.py` |
| Snapshot relative to event year | Yes — `archive/snapshot_selector.py` |
| Focused archived crawl | Yes — `crawl/crawler.py` + `link_policy.py` |
| Text/metadata extraction | Yes — trafilatura + BeautifulSoup |
| Homepage computed styles | Yes — optional `extract/visual.py` (Playwright) |
| ARGUS live-web crawl | No — out of scope for pilot |

---

## References

- ARGUS audit: [`reports/argus_technical_assessment.md`](argus_technical_assessment.md)
- Kinne, J., Lenz, D., & Wurst, J. (2020). Scientometrics. https://doi.org/10.1007/s11192-020-03726-9
