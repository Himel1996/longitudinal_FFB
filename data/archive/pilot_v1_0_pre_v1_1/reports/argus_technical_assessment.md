# ARGUS Technical Assessment

**Date:** 2026-07-13  
**Repository audited:** [JanKinne/ARGUS](https://github.com/JanKinne/ARGUS) (cloned to `external/ARGUS`)  
**Last upstream commit:** 2022-01-12  
**License:** GNU General Public License v3.0  

**Purpose:** Determine whether ARGUS is suitable for a longitudinal archived-web research design (Internet Archive / Wayback Machine), and identify what can be reused versus replaced in a new pilot pipeline.

---

## Executive Summary

ARGUS is a **live-web, same-domain breadth-first crawler** built on Scrapy. It was designed for scraping current firm websites at scale (ZEW research context; see [Kinne et al., 2020](https://link.springer.com/article/10.1007/s11192-020-03726-9)). It is **not sufficient without substantial modification** for a longitudinal archived-web research design.

The shipped codebase contains **no working Wayback/Internet Archive spider** despite GUI and orchestration code referencing a `webarchive` spider. The only active spider in `ARGUS/spiders/` is `dualspider`. ARGUS cannot extract CSS-computed colors or fonts, cannot select CDX snapshots relative to an event date, and does not preserve original versus replay URL provenance.

**Recommendation:** Treat ARGUS as a **reference implementation** for live-web crawling patterns (domain filtering, URL stack heuristics, tabular output schema). Build a new pipeline in `src/` that handles CDX snapshot resolution, Wayback URL rewriting, and (if needed) headless rendering for computed styles. Keep ARGUS unmodified in `external/ARGUS` for auditability and license separation.

---

## 1. Repository Structure

```
external/ARGUS/
├── ARGUS/                    # Scrapy project package
│   ├── spiders/
│   │   └── dualspider.py     # ONLY active spider (text + links)
│   ├── items.py              # Collector/Exporter item schemas
│   ├── pipelines.py          # CSV chunk export (Windows paths)
│   ├── middlewares.py        # Stub spider middleware
│   └── settings.py           # Scrapy settings (reads bin/settings.txt)
├── build/lib/ARGUS/spiders/  # Stale copies: textspider, linkspider, dualspider
├── bin/                      # Orchestration: scrapyd jobs, postprocessing, GUI helpers
├── ARGUS.py                  # Tkinter GUI (Windows-centric)
├── ARGUS_noGUI.py            # CLI entry (Windows: os.startfile, backslash paths)
├── setup.py                  # Minimal setuptools (no pinned deps)
├── scrapy.cfg / scrapyd.conf
├── misc/                     # Example URL list, ISO language codes
└── chunks/                   # Intermediate CSV output during crawls
```

**Notable absences:**

- No `webarchive` spider implementation (referenced but missing).
- No `requirements.txt`, `pyproject.toml`, or pinned dependency versions.
- No tests.
- `textspider` and `linkspider` exist only under `build/lib/` (build artifact), not in the active spider module.

---

## 2. Dependencies and Runtime Environment

### Declared dependencies (README)

| Package | Role |
|---------|------|
| Scrapy | Core crawler framework |
| scrapyd / scrapyd-client | Distributed job scheduling |
| scrapy-fake-useragent | Random User-Agent rotation |
| tldextract | Domain/subdomain parsing |
| pandas | Input URL lists, aggregation |
| pywin32 | **Windows only** |
| pdfminer.six | Inline PDF text extraction |
| urllib | PDF fetching (stdlib) |

### Practicality on current macOS/Linux (2026)

| Aspect | Assessment |
|--------|------------|
| **Python version** | README says 3.6+. Code uses deprecated pandas API (`error_bad_lines`) removed in pandas 2.x. Likely needs pandas &lt; 2 or code updates. |
| **Scrapy APIs** | Uses deprecated patterns: `.extract()` on selectors, `scrapy.contrib.feedexport` (removed in Scrapy 2.x), `error_bad_lines` in `read_csv`. |
| **Path handling** | Hard-coded Windows backslashes (`\\chunks\\`, `.\bin\settings.txt`, `TSKILL scrapyd`). **Will not run on macOS/Linux without path rewrites.** |
| **GUI / orchestration** | `ARGUS.py` (Tkinter), `os.startfile`, `pywin32`, `.bat` launchers — Windows-only. |
| **scrapyd + curl** | Job scheduling assumes local scrapyd on port 6800 and shell `curl`. Workable cross-platform if paths are fixed, but adds operational complexity unnecessary for a pilot. |
| **Headless browser** | None. Pure HTTP + XPath. No Playwright/Selenium/Puppeteer. |

**Verdict:** ARGUS is **not practically runnable out of the box** on macOS/Linux without porting work. Even on Windows, dependency drift since 2022 (Scrapy 2.x, pandas 2.x) will cause breakage. For a new research pipeline, prefer a fresh `pyproject.toml` with pinned, current dependencies rather than inheriting ARGUS's environment as-is.

---

## 3. Crawler Implementation

### Active spider: `dualspider`

The dual spider combines text extraction and outbound link collection in a single pass. Core behavior:

1. **Input:** Tab-separated CSV chunk with `ID` and URL columns. URLs expected as `www.example.com` (no scheme).
2. **Start URL construction:** Prepends `http://` and lowercases. Does not try `https://`.
3. **Crawl strategy:** Breadth-first via an in-memory URL stack, with optional heuristics (shortest URL first, ISO language path tags).
4. **Scope:** Same registered domain + subdomain, enforced via Scrapy `OffsiteMiddleware` and custom `allowed_domains` list. Cross-domain links are recorded in `links` but not followed.
5. **Limit:** `site_limit` caps pages per site (0 = unlimited).
6. **Text extraction:** XPath on static HTML tags (`p`, `div`, `h1`–`h6`, `li`, etc.). Tag markers like `[->p<-]` are inserted for downstream parsing.
7. **Metadata:** `title`, `description`, `keywords`, `language` (from `<html lang>`).
8. **PDFs:** Optional inline fetch via `urllib` + pdfminer (bypasses Scrapy downloader).
9. **Redirects:** Detects cross-domain redirect on first page; records `alias` and expands `allowed_domains` to follow redirect target.

### URL / domain logic

```python
# Initialization (dualspider.py)
self.allowed_domains = [url.split("www.")[-1].lower() for url in list(data[url_col])]
self.start_urls = ["http://" + url.lower() for url in self.allowed_domains]
```

- **Assumes live domains**, not full URLs with schemes or paths.
- **Same-domain enforcement** via `tldextract` registered domain + subdomain matching.
- **Wayback host would break domain logic:** A replay URL like `https://web.archive.org/web/20150301000000*/http://www.example.com/` would parse `web.archive.org` as the domain, not `example.com`. All `allowed_domains` / offsite checks would fail without a dedicated rewriter.

### Redirect handling

- Initial redirect: `checkRedirectDomain()` compares `tldextract(response.url).registered_domain` to `download_slot` domain. Sets `redirect=True` and `alias`.
- Subpage redirects to different firm: `start_domain` guard raises/skips.
- HTTP 301/302: Still extracts links from redirect response body but does not store text from redirect landing page in those branches.
- `RETRY_ENABLED = False` — transient failures are not retried.

### Error handling

- Structured errorback for start requests: HTTP status, DNS, timeout, other.
- Subpage errors: bare `except` falls back to `processURLstack` (silent skip).
- No structured logging of per-URL failure reasons in output beyond site-level `error` on main page failure.

### Post-processing

- Chunk CSVs written to `chunks/ARGUS_chunk_{n}.csv` during crawl.
- `bin/postprocessing.py` merges chunks into `{input_basename}_scraped_texts.csv`.
- `bin/aggregator.py` rolls webpage-level text up to site level.
- All paths Windows-specific; uses Tkinter `messagebox` for user feedback.

---

## 4. Output Schema

One row per webpage (tab-separated CSV):

| Field | Description |
|-------|-------------|
| `ID` | User-supplied site identifier |
| `dl_rank` | Download order (0 = seed page) |
| `dl_slot` | Domain from input list |
| `alias` | Redirect target domain if cross-domain redirect on seed |
| `error` | `None`, HTTP code, `DNS`, `Timeout`, `other` |
| `redirect` | Boolean — seed redirected to different registered domain |
| `start_page` | First URL actually scraped |
| `title`, `keywords`, `description`, `language` | HTML metadata |
| `text` | Concatenated tag-level text with markers |
| `links` | List of external domains found on site |
| `timestamp` | Local download time (`strftime("%c")`), not archive date |
| `url` | Final URL of the scraped page |

**Missing for archived-web research:**

- Original (canonical) URL vs Wayback replay URL
- Snapshot timestamp (CDX `timestamp`)
- Archive source identifier (e.g., `web.archive.org`)
- Event-date-relative snapshot selection metadata
- Computed CSS colors/fonts
- Raw HTML retention option
- Structured subdomain field (only inferable from `url` / `dl_slot`)

---

## 5. Wayback / Internet Archive Capability

### Code search results

- **Zero references** to `wayback`, `archive.org`, `web.archive`, or CDX APIs in spider/source code.
- `bin/start_crawl.py` and `ARGUS.py` reference `spider=webarchive` with a `date` parameter — **but no `webarchive.py` spider exists** in `ARGUS/spiders/`.
- This appears to be **planned or removed functionality**, not a shipped feature.

### Would dualspider work against Wayback replay URLs?

**No, not reliably.** Critical blockers:

| Issue | Detail |
|-------|--------|
| **Domain parsing** | `tldextract` on Wayback URLs yields `web.archive.org`, not the original site. |
| **allowed_domains** | Offsite middleware would block or mis-scope all internal links. |
| **Link rewriting** | Wayback rewrites `href` values to `web.archive.org/web/{ts}*/{original}`. ARGUS does not unwrap these to original URLs or re-wrap for consistent snapshot crawling. |
| **URL join** | `response.urljoin()` would produce further Wayback URLs, potentially mixing snapshots. |
| **JavaScript / archived assets** | Many archived pages depend on Wayback's `wm-` injected JS and rewritten asset URLs. Static XPath may return toolbar/injection text. |
| **Rate limiting** | Internet Archive has access policies; ARGUS has no IA-specific throttling or identity headers. |
| **HTTPS** | ARGUS defaults to `http://` for seeds; IA requires `https://web.archive.org/...`. |

### Can it select snapshots relative to an event date?

**No.** No CDX API integration, no `closest` snapshot logic, no `date` parameter consumed by any existing spider.

### Can it preserve original URLs and archived replay URLs?

**No.** Only stores the final requested URL (`url`, `start_page`). No separate original-URL field or replay-URL field.

---

## 6. Feature Checklist (Research Requirements)

| Requirement | ARGUS (as shipped) | Notes |
|-------------|-------------------|-------|
| Crawl live/current pages | **Yes** | Core use case |
| Crawl archived/Wayback pages | **No** | No spider; domain logic incompatible |
| Select snapshot relative to event date | **No** | No CDX integration |
| Preserve original + replay URLs | **No** | Single `url` field |
| Page-level text extraction | **Partial** | XPath on static HTML; misses JS-rendered content |
| Page metadata (title, description, keywords, lang) | **Yes** | From HTML head |
| Domain and subdomain | **Partial** | `dl_slot` / URL parsing; no explicit subdomain column |
| CSS-computed colors | **No** | No headless browser or computed-style extraction |
| CSS-computed fonts | **No** | Only legacy `<font>` tag text via XPath |
| Longitudinal reproducibility | **No** | `timestamp` is download time, not archive time |
| Cross-platform pipeline | **No** | Windows-centric paths and tooling |

---

## 7. Licensing Implications

ARGUS is licensed under **GPLv3**.

| Scenario | Implication |
|----------|-------------|
| **Use unmodified in `external/ARGUS`** | Allowed. No copyleft obligation on separate `src/` code that does not incorporate GPL code. |
| **Import ARGUS as a Python package** | If linked/combined into a single distributed program, the combined work may need to be GPLv3. |
| **Copy-paste spider logic into `src/`** | Derivative work → GPLv3 applies to distributed copies; must provide source and license notice. |
| **Study / reuse algorithms without copying code** | Generally no GPL obligation (ideas are not copyrightable). Document provenance. |
| **Modify ARGUS in `external/ARGUS`** | Allowed; modifications must be marked and GPLv3 applies to distributed modified versions. |

**Recommendation:** Keep ARGUS **unmodified** in `external/` as a reference. Implement the pilot pipeline in `src/` under a license chosen for the research project. If specific functions are ported (e.g., `subdomainGetter`, URL stack heuristics), either reimplement from the published paper description or accept GPLv3 for those modules.

---

## 8. Reuse vs Adapt vs Replace

### Reuse directly (with caution)

| Component | Value | Caveat |
|-----------|-------|--------|
| **Output schema concept** | `ID`, `dl_rank`, page-level rows, metadata fields | Extend, don't copy verbatim; add archive fields |
| **`tldextract` domain parsing pattern** | Subdomain + registered domain logic | Must operate on *original* URLs, not Wayback wrapper URLs |
| **URL stack + breadth-first heuristic** | Short-URL and language-priority ordering | Reimplement in new spider; logic is simple |
| **Tag-based text extraction idea** | Structured text with element markers | Consider `trafilatura` or `readability-lxml` for better quality |
| **Research documentation** | Paper methodology, field definitions | Cite Kinne et al. (2020) |

### Adapt (significant work)

| Component | Needed changes |
|-----------|----------------|
| **Scrapy spider** | New Wayback-aware spider: CDX lookup, replay URL builder, link unwrapping, snapshot pinning |
| **Domain filter** | Filter on original URL host, not `web.archive.org` |
| **Pipelines** | Cross-platform paths, parquet/JSONL option, provenance columns |
| **Settings** | Remove Windows config path; modern Scrapy 2.x settings |
| **Orchestration** | Replace scrapyd/GUI with CLI/Makefile or simple Python runner |

### Do not use

| Component | Reason |
|-----------|--------|
| **`ARGUS.py` GUI** | Windows/Tkinter; irrelevant for reproducible pipeline |
| **scrapyd orchestration** | Overkill for pilot; hard to reproduce in CI/HPC |
| **`bin/postprocessing.py`** | Windows paths, Tkinter dialogs |
| **`webarchive` spider references** | Non-functional stub |
| **`build/lib/` artifacts** | Stale; not source of truth |
| **PDF via urllib bypass** | Blocks event loop; fragile for archived PDFs |
| **pandas `error_bad_lines`** | Removed API |

### Replace entirely

| Capability | Replacement direction |
|------------|---------------------|
| **Snapshot selection** | CDX API (`cdx/search/cdx`) or `waybackpy` |
| **Archived page fetch** | Construct `https://web.archive.org/web/{timestamp}id_/{original_url}` |
| **Link normalization** | Strip/reapply Wayback prefix; pin to same snapshot timestamp |
| **Computed colors/fonts** | Playwright or Puppeteer via `page.evaluate(getComputedStyle)` |
| **Text extraction** | `trafilatura`, `beautifulsoup4`, or Playwright-rendered DOM |
| **Dependency management** | `pyproject.toml` with pinned versions |
| **Configuration** | YAML/TOML in `config/`, not GUI-driven `settings.txt` |

---

## 9. Direct Answers to Assessment Questions

### Is ARGUS sufficient without modification?

**No.** It lacks archived-web support, snapshot selection, provenance fields, computed-style extraction, and cross-platform operability. The referenced `webarchive` spider does not exist.

### Is ARGUS useful only for current/live pages?

**Yes.** It is explicitly designed for live firm websites: `http://` seeds, download-time timestamps, same-domain crawling, redirect-to-live-alias handling. That is its intended and only working mode.

### Can it reliably handle archived pages and Wayback URL rewriting?

**No.** No Wayback integration. Feeding replay URLs into `dualspider` would break domain scoping and produce inconsistent, unreliable results.

### Can it select snapshots relative to an event date?

**No.** No CDX or date-parameter logic exists in any shipped spider.

### Can it preserve both original URLs and archived replay URLs?

**No.** Only a single `url` field (final fetch URL) is stored.

### Can it extract page-level text, metadata, domain and subdomain?

**Partially.**

- **Text:** Yes, page-level, via XPath tag extraction (quality limitations for modern/JS sites).
- **Metadata:** Yes (`title`, `keywords`, `description`, `language`).
- **Domain/subdomain:** Implicit in `dl_slot` and URL strings; `subdomainGetter()` exists internally but is not exported as a dedicated output column.

### Can it extract CSS-computed colors and fonts?

**No.** No headless rendering or `getComputedStyle`. The only font-related extraction is text inside deprecated `<font>` HTML tags.

### Which parts should be reused versus replaced?

See Section 8. In short: reuse the **research schema concepts** and **crawl heuristic ideas**; replace **orchestration, Wayback integration, style extraction, and platform-specific tooling**.

---

## 10. Recommended Architecture for the Pilot Pipeline

```
project-root/
  external/ARGUS/          # Unmodified reference (GPLv3)
  src/
    archive/               # CDX client, snapshot resolver
    crawl/                 # Scrapy/Playwright spiders (new)
    extract/               # Text, metadata, computed styles
    pipeline/              # Orchestration, I/O
  config/                  # Sites, event dates, crawl limits
  data/
    input/                 # Seed URL lists with IDs + event dates
    interim/               # Raw captures, CDX responses
    output/                # Analysis-ready tables
  reports/                 # This document + run logs
  tests/
  scripts/                 # CLI entry points
```

**Suggested pilot flow:**

1. Read seed list (`ID`, `original_url`, `event_date`).
2. Query CDX for closest snapshot ≤ event date (or configurable policy).
3. Build pinned replay URL for seed page.
4. Crawl same-domain links within snapshot (unwrap Wayback URLs, re-wrap at same timestamp).
5. Extract text + metadata via modern extractors.
6. Optionally render with Playwright for computed colors/fonts on seed/key pages.
7. Write parquet/CSV with `original_url`, `replay_url`, `snapshot_timestamp`, `crawl_timestamp`, and content fields.

---

## 11. References

- ARGUS repository: https://github.com/JanKinne/ARGUS
- Kinne, J., Lenz, D., & Wurst, J. (2020). *ARGUS: A web scraping tool*. Scientometrics. https://link.springer.com/article/10.1007/s11192-020-03726-9
- Internet Archive CDX API: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server
- Wayback Machine URL format: `https://web.archive.org/web/{timestamp}/{url}`

---

*Assessment completed without modifying `external/ARGUS`.*
