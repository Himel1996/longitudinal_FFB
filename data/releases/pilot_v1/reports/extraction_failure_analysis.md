# Extraction Failure Root Cause Analysis

**Run ID:** `ed085a32-23b7-4c16-9931-d5cd0abea722`  
**Analysis date:** 2026-07-14  
**Scope:** 14 of 19 manually validated observations with `content_extraction_usable=False` at baseline  
**Evidence sources:** Archived HTML inspection (`data/interim/html/`), live Wayback fetches, trafilatura/readability probes, browser validation (`data/output/validation_browser_results.json`), machine log `data/output/extraction_root_cause.json`

---

## Executive Summary

All 19 archived pages were **valid** (correct company, HTTP 200, substantive visible content in browser). Extraction failed on 14 observations due to **pipeline bottlenecks**, not bad archives:

| Root cause category | Count | Share of failures |
|---------------------|-------|-------------------|
| Crawler fetch failure (HTML never cached) | 9 | 64% |
| HTML frameset / JS redirect chain | 3 | 21% |
| Wrong DOM / navigation domination | 4 | 29% |
| Trafilatura + readability failure on valid HTML | 2 | 14% |

*(Some observations have multiple contributing categories.)*

The dominant failure mode was **intermittent Wayback connection errors during the original crawl** (`[Errno 61] Connection refused`), which left homepage rows with empty `main_text` despite archives loading successfully on retry.

---

## Methodology

For each failed observation:

1. Opened the archived HTML from cache or live Wayback (`id_` replay URL).
2. Inspected DOM structure: framesets, iframes, meta/JS redirects, body text length.
3. Ran isolated trafilatura and readability probes on raw and preprocessed HTML.
4. Compared against browser-rendered screenshots in `data/output/validation_screenshots/`.
5. Classified the **exact technical reason** — no inference without HTML evidence.

---

## Per-Observation Classification

### Firm 1 — BLUE MOON COMMUNICATION CONSULTANTS GMBH

#### 1|post_event (2026-03-04 capture) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20260304002641id_/https://www.bluemoon.de/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | trafilatura failure (on retry: succeeds with 752+ words) |

**Evidence:** Original `pages.csv` row had `fetch_error=[Errno 61] Connection refused`, empty `document_title`, `word_count=0`. Live fetch returned HTTP 200, 131 KB HTML, title *"Die Werbeagentur des Mittelstands \| BLUE MOON"*, body text ~10,053 chars. No frameset. Modern JS-rendered homepage (familiengeführt, Vier Teams branding visible in browser). Trafilatura alone extracted 752 words from cached HTML; Playwright stage extracts ~1,340 words with full rendered DOM.

**Exact reason:** Homepage fetch failed during original crawl; no HTML cached → empty extraction row written. Archive and content were always valid.

---

### Firm 2 — PETER-LACKE HOLDING GMBH

#### 2|pre_pre_event (2011-07-09) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20110709094353id_/http://www.peter-lacke.de:80/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | wrong_DOM_selected, navigation_domination |

**Evidence:** Original row empty (`fetch_error=Connection refused`). Cached HTML (20 KB) has title *"PETER-LACKE Farbe & mehr"*, body ~2,074 chars. No frames. Trafilatura: 41 words (nav/footer only). Main content lives in `.colInhalt` div — not selected by trafilatura. Playwright + visible_dom with `#inhalt`/`.colInhalt` selectors extracts 241 words.

**Exact reason:** Fetch failure during crawl; on available HTML, trafilatura selected navigation boilerplate instead of `#inhalt` content block.

#### 2|pre_event (2013-07-03) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20130703032151id_/http://www.peter-lacke.de:80/` |
| Primary category | **wrong_DOM_selected** |
| Secondary | navigation_domination |

**Evidence:** HTML cached (27 KB). Pipeline extracted 45 words via trafilatura, marked `usable_for_analysis=True` but content was Servicemenü/Navigation headings only. Browser shows Lack-Kompetenz hero in `.colInhalt`. Readability: 61 words (still nav-heavy). Visible DOM targeting `.colInhalt` → 267 words with substantive lacquer-industry content.

**Exact reason:** Extractor captured repeated navigation tree; hero content block not prioritized.

#### 2|event (2015-05-22) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20150522040733id_/http://www.peter-lacke.de:80/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | wrong_DOM_selected, navigation_domination |

**Evidence:** Original row empty (Connection refused). Live HTML 13 KB, title *"PETER-LACKE: Startseite"*. Trafilatura: 38 words; readability: 31 words. Browser shows *"mittelständische Unternehmensgruppe mit mehr als 100 Jahren Erfahrung"*. Playwright extracts 90 words including corporate narrative.

**Exact reason:** Fetch failure + nav-dominated partial extraction on retry without content-selector fallback.

---

### Firm 3 — ANLAGENTECHNIK LEICHTLE GMBH

#### 3|pre_pre_event (2019-07-23) — **FAIL (marginal)**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20190723051243id_/https://www.anlagentechnik-leichtle.de/` |
| Primary category | **navigation_domination** |

**Evidence:** HTML cached (33 KB). Trafilatura: 63 words. Body text only 709 chars — small homepage. Navigation menu repeated 2× in DOM. No frames. Content is service-oriented (installations, references) with minimal family-branding language. Extraction is technically non-empty but nav-heavy.

**Exact reason:** Small homepage with duplicated navigation overwhelming main content signal; not a fetch failure.

#### 3|pre_event (2021-06-23) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20210623054251id_/https://www.anlagentechnik-leichtle.de/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | navigation_domination |

**Evidence:** Original row empty (Connection refused). Live HTML 29 KB, body ~801 chars. Trafilatura: 73 words on fetch. JS-enhanced layout; Playwright required for consistent extraction.

**Exact reason:** Fetch failure during crawl; JS-rendered content needs Playwright stage.

#### 3|event (2023-05-29) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20230529054753id_/https://www.anlagentechnik-leichtle.de/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | wrong_DOM_selected, navigation_domination |

**Evidence:** Original row empty (Connection refused). Live HTML 29 KB. Trafilatura and readability both ~23 words. Playwright: 83 words. Very low family-branding density by site design.

**Exact reason:** Fetch failure + minimal content homepage with nav duplication.

---

### Firm 4 — MYRENNE GMBH

#### 4|pre_pre_event (2008-08-20) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20080820062004id_/http://www.myrenne.com/` |
| Primary category | **HTML_frameset** |
| Secondary | frameset_noframes_only |

**Evidence:** Cached HTML (3 KB) contains `<frameset>` with frames `inhalt.htm` and `home.htm`. Body text 87 chars — only `<noframes>` fallback: *"myrenne gmbh - spezialmaschinen + apparatebau"*. Trafilatura/readability: 12 words. Browser renders welcome content inside `inhalt.htm` frame. Frame fetch to `inhalt.htm` intermittently fails (Connection refused on archived frame URL).

**Exact reason:** Outer HTML is frameset shell; real content in child frames not merged. Partial frame expansion yields 35 words when frame fetch succeeds.

#### 4|post_event (2014-05-17) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20140517163035id_/http://myrenne.com/` |
| Primary category | **crawler_fetch_failure** |

**Evidence:** Original row empty (Connection refused). Live HTML 11 KB, no frameset, title *"myrenne gmbh"*, body ~805 chars. Trafilatura: 97 words. Visible_dom: 84 words with Gesamtlösungen Maschinenbau text.

**Exact reason:** Fetch failure during crawl; standard HTML extractable on retry.

#### 4|post_post_event (2016-08-01) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20160801210455id_/http://www.myrenne.com/` |
| Primary category | **crawler_fetch_failure** |

**Evidence:** Original row empty (Connection refused). Live HTML 13 KB, title *"Spezialmaschinen & Apparatebau, Myrenne GmbH in Roetgen"*, body ~1,682 chars. Trafilatura: 107 words. Visible_dom: 105 words.

**Exact reason:** Fetch failure during crawl.

---

### Firm 5 — MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG

#### 5|pre_pre_event (2001-07-23) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20010723123022id_/http://www.msf-technik.de:80/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | trafilatura_failure, readability_failure, JavaScript rendering |

**Evidence:** Original row empty (Connection refused). Live HTML 1.8 KB, title *"MSF-TECHNIK [Intro]"*, body text **0 chars**. Page is JS intro splash with `window.location` redirect to `entry.html` → frames layout (`menu.html`, `head.html`, content frame). Trafilatura/readability on intro page: 0 words. After JS redirect follow + frame expansion: 182 words via trafilatura. Frame child fetches (`menu.html`, `head.html`) intermittently fail with Connection refused.

**Exact reason:** JS redirect chain to frameset site; intro page has no extractable text; frame content requires redirect follow + recursive frame fetch.

#### 5|event (2005-09-09) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20050909231716id_/http://www.msf-technik.de:80/` |
| Primary category | **trafilatura_failure**, **readability_failure** |
| Secondary | JavaScript rendering, HTML_frameset |

**Evidence:** HTML cached (3.3 KB), same intro page structure as 2001. Title *"MSF-TECHNIK [Intro]"*, body 0 chars. Pipeline used readability → 0 words. Duplicate timestamp with excluded pre_event row. After preprocessing (JS redirect + frames): 195 words.

**Exact reason:** Intro redirect page cached but redirect/frames not followed during original extraction.

#### 5|post_event (2008-03-27) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20080327012906id_/http://msf-technik.de:80/` |
| Primary category | **crawler_fetch_failure** |
| Secondary | homepage redirect (root serves Über-uns) |

**Evidence:** Original row empty (Connection refused). Live HTML 20 KB, title *"Über uns"* (not literal homepage — root URL redirects to about page). Body ~2,562 chars. Trafilatura: 218 words. Visible_dom: 221 words with MSF-Vathauer corporate welcome text.

**Exact reason:** Fetch failure; archived root URL serves Über-uns content (scope note, not extraction blocker).

#### 5|post_post_event (2010-06-18) — **FAIL**

| Field | Value |
|-------|-------|
| URL | `https://web.archive.org/web/20100618062303id_/http://www.msf-technik.de:80/` |
| Primary category | **crawler_fetch_failure** |

**Evidence:** Original row empty (Connection refused). Live HTML 30 KB, title *"Über uns"*, body ~3,733 chars. Trafilatura: 309 words. Visible_dom: 315 words.

**Exact reason:** Fetch failure during crawl.

---

## Category Summary

| Category | Observations | Mechanism |
|----------|-------------|-----------|
| **crawler_fetch_failure** | 1\|post, 2\|pre_pre, 2\|event, 3\|pre_event, 3\|event, 4\|post, 4\|post_post, 5\|pre_pre, 5\|post, 5\|post_post | Wayback `[Errno 61] Connection refused` during crawl; empty page row persisted |
| **HTML_frameset** | 4\|pre_pre, 5\|pre_pre, 5\|event | Outer page is frame shell; content in child frames |
| **JavaScript rendering** | 1\|post, 3\|pre_event, 3\|event, 5\|pre_pre, 5\|event | Content requires JS execution or redirect follow |
| **wrong_DOM_selected** | 2\|pre_pre, 2\|pre_event, 2\|event, 3\|event | Trafilatura selected nav/footer instead of `#inhalt`/`.colInhalt` |
| **navigation_domination** | 2\|pre_pre, 2\|pre_event, 3\|pre_pre, 3\|pre_event, 3\|event | Repeated menu blocks overwhelm short homepages |
| **trafilatura_failure** | 5\|pre_pre, 5\|event | Zero words on intro/frameset shell pages |
| **readability_failure** | 5\|event | Zero words on intro page |
| **homepage redirect** | 5\|post_event, 5\|post_post | Root URL serves Über-uns (valid content, scope mismatch) |

**Not observed in this sample:** encoding problems, malformed HTML beyond framesets, extraction timeout, image-only homepages, incorrect URL normalization, archive asset permanently missing, CSS-hidden content (as primary blocker), archive toolbar contamination (stripped successfully in preprocessing).

---

## Implications for Pipeline Design

1. **Retry fetch with backoff** before writing empty rows (implemented in `PageFetcher`).
2. **Preprocess archived HTML** before extraction: strip Wayback DOM, follow JS/meta redirects, expand framesets (`html_preprocess.py`).
3. **Multi-stage extraction** with quality scoring: trafilatura → readability → visible DOM (content selectors) → Playwright → frame merge (`text.py`).
4. **QA gate:** reject `word_count=0` when HTTP 200 and body length > 500 chars.

---

## Evidence Files

- `data/output/extraction_root_cause.json` — machine-readable per-observation probes
- `data/output/validation_screenshots/` — 19 browser screenshots
- `data/output/validation_browser_results.json` — rendered body lengths
- `data/interim/html/` — cached archived HTML for inspection
