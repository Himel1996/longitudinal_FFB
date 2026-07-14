# Manual Validation Report

**Run ID:** `ed085a32-23b7-4c16-9931-d5cd0abea722`  
**Validation date:** 2026-07-14  
**Method:** Each Wayback replay URL was opened in a headless browser (Playwright Chromium) and compared against `pages.csv` extraction fields. Screenshots saved to `data/output/validation_screenshots/`.

---

## 1. Summary Table

| Company | Observation | Result | Problems found |
|---------|-------------|--------|----------------|
| BLUE MOON | pre_pre_event | **PASS** | None material |
| BLUE MOON | pre_event | **PASS** | None material |
| BLUE MOON | event | **CONDITIONAL** | Temporally inappropriate capture (Mar 2025 for Jul 2024 event) |
| BLUE MOON | post_event | **FAIL (extraction)** | Page valid; pipeline extraction empty |
| PETER-LACKE | pre_pre_event | **FAIL (extraction)** | Page valid; pipeline extraction empty |
| PETER-LACKE | pre_event | **FAIL (extraction)** | Extraction mostly nav boilerplate |
| PETER-LACKE | event | **FAIL (extraction)** | Page valid; pipeline extraction empty |
| ANLAGENTECHNIK LEICHTLE | pre_pre_event | **FAIL (extraction)** | Nav-dominated extraction; sparse branding |
| ANLAGENTECHNIK LEICHTLE | pre_event | **FAIL (extraction)** | Page valid; pipeline extraction empty |
| ANLAGENTECHNIK LEICHTLE | event | **FAIL (extraction)** | Page valid; pipeline extraction empty; low branding density |
| ANLAGENTECHNIK LEICHTLE | post_event | **PASS** | Low family-branding signal but extraction usable |
| MYRENNE | pre_pre_event | **FAIL (extraction)** | Frames homepage; extractor captured fallback only |
| MYRENNE | pre_event | **PASS** | None material |
| MYRENNE | post_event | **FAIL (extraction)** | Page valid; pipeline extraction empty |
| MYRENNE | post_post_event | **FAIL (extraction)** | Page valid; pipeline extraction empty |
| MSF-VATHAUER | pre_pre_event | **CONDITIONAL** | Early capture vs 2002 target; frames site; empty extraction |
| MSF-VATHAUER | event | **FAIL** | Duplicate timestamp; frames unchanged from 2001; empty extraction |
| MSF-VATHAUER | post_event | **FAIL (extraction)** | Root URL serves Über-uns; extraction empty |
| MSF-VATHAUER | post_post_event | **FAIL (extraction)** | Page valid; pipeline extraction empty |

**Result key:** PASS = all validation fields TRUE. CONDITIONAL = archive/company correct but temporal or scope concerns. FAIL = one or more critical validation fields FALSE.

---

## 2. Validation Field Counts

| Field | TRUE | FALSE |
|-------|------|-------|
| correct_company | 19 | 0 |
| valid_archived_page | 19 | 0 |
| temporally_appropriate | 15 | 4 |
| content_extraction_usable | 5 | 14 |
| duplicate_capture | 1 | 18 |

---

## 3. Observations Needing Further Review

1. **BLUE MOON — event (2025-03-14 capture)**  
   Archive is post-event and post-redesign. Usable for post-succession branding analysis but not as an event-window observation without relabelling.

2. **BLUE MOON — post_event (2026-03-04 capture)**  
   Page renders correctly with strong familiengeführt / “Vier Teams. Eine Familie.” content. Requires re-extraction before NLP use.

3. **PETER-LACKE — all three observations**  
   Archives load correctly; extraction failed or captured boilerplate only. Event-window page (May 2015) contains “mittelständische Unternehmensgruppe mit mehr als 100 Jahren Erfahrung” visible on page.

4. **MSF-VATHAUER — pre_pre_event & event**  
   Frames-based legacy site. Browser renders corporate content in inner frames; extractor returns empty. Event observation shares timestamp `20050909231716` with excluded pre_event row.

5. **MSF-VATHAUER — post_event & post_post_event**  
   Archived homepage URL resolves to “Über uns” content. Substantive MSF-Vathauer corporate text present but not extracted.

6. **ANLAGENTECHNIK LEICHTLE — all except post_event**  
   Low family-branding density by design; three of four observations have missing or nav-heavy extraction.

---

## 4. Extraction Problems

| Firm | Timepoint | Issue |
|------|-----------|-------|
| BLUE MOON | post_event | Complete extraction failure despite ~10k chars visible body text |
| PETER-LACKE | pre_pre_event | Complete extraction failure |
| PETER-LACKE | pre_event | Only 45 words; nav/footer boilerplate dominates |
| PETER-LACKE | event | Complete extraction failure |
| LEICHTLE | pre_pre_event | 63 words; duplicated navigation menus |
| LEICHTLE | pre_event | Complete extraction failure |
| LEICHTLE | event | Complete extraction failure |
| MYRENNE | pre_pre_event | Frames not followed; only no-frames fallback captured |
| MYRENNE | post_event | Complete extraction failure |
| MYRENNE | post_post_event | Complete extraction failure |
| MSF-VATHAUER | pre_pre_event | Frames not followed; 0 words extracted |
| MSF-VATHAUER | event | Frames not followed; 0 words extracted |
| MSF-VATHAUER | post_event | Complete extraction failure |
| MSF-VATHAUER | post_post_event | Complete extraction failure |

**Patterns identified:**
- Systematic extraction failures for several firms/timepoints where the archived page clearly loads (likely pipeline fetch/write bug, not absent archives).
- Legacy `<frameset>` pages (Myrenne 2008, MSF 2001/2005) not handled—inner-frame content ignored.
- Navigation-heavy small-business sites (Leichtle) produce duplicated menu text with little corporate narrative.
- Hero/marketing slogans on redesigned sites (Blue Moon 2025+) partially captured but with fragmented line breaks in `main_text`.

---

## 5. Disagreements with Pipeline Recommendations

| Company | Timepoint | Pipeline | Manual verdict | Reason |
|---------|-----------|----------|----------------|--------|
| BLUE MOON | event | include | **Disagree on temporal fit** | Capture is 256 days after 2024 event proxy; content reflects post-succession redesign |
| BLUE MOON | post_event | include | **Disagree on usability** | `usable_for_analysis=False` in pages.csv confirmed; page itself is valid and content-rich |
| PETER-LACKE | pre_pre_event | include | **Disagree on usability** | Archive valid; extraction absent—should not enter NLP until re-extracted |
| PETER-LACKE | pre_event | include | **Disagree on usability** | Pipeline marked usable=True but extraction is boilerplate-only |
| PETER-LACKE | event | sensitivity_analysis | **Agree on scope, disagree on usability** | Correct sensitivity flag; extraction unusable |
| LEICHTLE | pre_pre_event | include | **Disagree on usability** | Nav-dominated extraction |
| LEICHTLE | pre_event | include | **Disagree on usability** | Extraction missing |
| LEICHTLE | event | sensitivity_analysis | **Agree** | Low branding density; extraction also missing |
| MYRENNE | pre_pre_event | include | **Disagree on usability** | Frames content visible in browser, not in extraction |
| MSF-VATHAUER | pre_pre_event | include | **Disagree on temporal fit & usability** | Early capture; frames extraction empty |
| MSF-VATHAUER | event | sensitivity_analysis | **Agree on sensitivity; duplicate confirmed** | Same timestamp as pre_event; frames site |
| MSF-VATHAUER | post_event | include | **Disagree on usability & scope** | Über-uns not homepage; extraction empty |

---

## 6. Recommendations for Improving the Extraction Pipeline

1. **Fix systematic homepage extraction failures**  
   Investigate why 10 observations return empty `document_title`, `main_text`, and `usable_for_analysis=False` while HTTP 200 archived pages load with thousands of characters of body text (Blue Moon post_event, Peter-Lacke pre_pre/event, Leichtle pre/event, Myrenne post/post_post, MSF post/post_post).

2. **Add frameset handling**  
   For legacy sites (Myrenne 2008, MSF 2001/2005), follow `<frame src="...">` targets and merge inner-frame text. Current extractor captures only the outer no-frames fallback.

3. **Improve boilerplate removal for nav-heavy sites**  
   Leichtle homepages repeat full navigation trees 2–3 times. Deduplicate menu blocks before scoring extraction quality.

4. **Validate homepage vs redirect target**  
   MSF 2008/2010 root URLs serve “Über uns” content. Flag or follow redirects and record `final_url` vs `requested_url` mismatch in validation output.

5. **Temporal validation gate for event timepoints**  
   Blue Moon event capture (Mar 2025) passed pipeline tolerance but fails human temporal review. Add content-era heuristics (site redesign detection, du/Sie shift) alongside date distance.

6. **Duplicate capture reporting**  
   MSF timestamp `20050909231716` correctly assigned to event timepoint with pre_event excluded; surface this explicitly in observation metadata.

7. **Post-extraction QA checks**  
   Fail extraction when `word_count=0` but rendered body length > 500 chars, or when `document_title` is empty for HTTP 200 homepage fetches.

---

## Evidence

All validation screenshots: `data/output/validation_screenshots/` (19 PNG files, one per observation).

Supporting machine-readable inspection logs:
- `data/output/validation_fetch_results.json`
- `data/output/validation_browser_results.json`
