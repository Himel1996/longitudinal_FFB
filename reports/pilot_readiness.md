# Pilot Dataset Readiness Assessment

**Run ID:** `ed085a32-23b7-4c16-9931-d5cd0abea722`  
**Assessment date:** 2026-07-14  
**Firms:** 5 (BLUE MOON, PETER-LACKE, ANLAGENTECHNIK LEICHTLE, MYRENNE, MSF-VATHAUER)  
**Observations:** 19 manually validated homepage snapshots

---

## Success Criterion

> **Target:** ≥15 of 19 observations with usable, correct extraction for publication-quality pilot dataset.

| Metric | Result | Status |
|--------|--------|--------|
| `content_extraction_usable=True` | **19 / 19** | **PASS** |
| Observations with ≥30 words | **19 / 19** | **PASS** |
| `correct_company=True` | 19 / 19 | PASS (unchanged) |
| `valid_archived_page=True` | 19 / 19 | PASS (unchanged) |

**Verdict: Success criterion MET.**

---

## Current Extraction Success

### By firm

| Firm | Observations | Usable extraction | Word range | Primary method |
|------|-------------|-------------------|------------|----------------|
| BLUE MOON (1) | 4 | 4/4 | 1,340–1,908 | playwright |
| PETER-LACKE (2) | 3 | 3/3 | 90–267 | playwright |
| LEICHTLE (3) | 4 | 4/4 | 63–199 | playwright |
| MYRENNE (4) | 4 | 4/4 | 35–110 | playwright / visible_dom |
| MSF-VATHAUER (5) | 4 | 4/4 | 182–315 | trafilatura / visible_dom |

### Improvement trajectory

| Stage | Usable extractions |
|-------|-------------------|
| Original pipeline (pre-fix) | 5 / 19 (26%) |
| After multi-stage pipeline | **19 / 19 (100%)** |
| Minimum target | 15 / 19 (79%) |

---

## Remaining Failures

**Extraction failures: 0 / 19**

No observation remains blocked by empty extraction, frameset-only capture, or fetch-without-retry. All previously failed observations were recovered.

---

## Remaining Limitations (Non-Extraction)

These are **archival, temporal, or content-design** limitations — not pipeline bugs. They do not block pilot completion but must be documented in publication.

### 1. Temporal misfit (4 observations)

| Observation | Issue |
|-------------|-------|
| 1\|event | Capture Mar 2025, ~8 months post-2024 event; post-redesign content |
| 5\|pre_pre_event | Capture Jul 2001, ~11 months before 2002 target |
| 5\|event | Capture Sep 2005; duplicate timestamp with excluded pre_event |
| (implicit) | MSF early-era design predates succession window |

**Impact:** Affects temporal modelling interpretation, not extraction quality. Already flagged in `manual_validation_sample.csv` (`temporally_appropriate=False`).

### 2. Scope mismatch (2 observations)

| Observation | Issue |
|-------------|-------|
| 5\|post_event | Archived root URL serves *Über uns*, not literal homepage |
| 5\|post_post_event | Same — Über-uns content at root |

**Impact:** Content is valid MSF-Vathauer corporate text; observation scope is homepage proxy. Acceptable for branding analysis with metadata note.

### 3. Low family-branding density (by site design)

| Firm | Note |
|------|------|
| LEICHTLE | B2B installer; service content dominates; 0 family terms across all timepoints |
| MYRENNE 4\|pre_pre | 35 words; frameset era with minimal welcome text |
| PETER-LACKE 2\|event | 90 words; brief homepage era |

**Impact:** Dictionary scoring (out of scope) may show low signal; extraction itself is correct.

### 4. Infrastructure dependency

- **Playwright required** for 11/19 observations (modern JS sites). Adds ~5–10s per page.
- **Wayback intermittent failures** (`Connection refused`) require retry; ~5% of frame child fetches fail on first attempt.
- **MSF frames sites** produce elevated boilerplate ratio (0.20–0.30) from merged menu frames.

---

## Can the Pilot Be Considered Complete?

### YES — for the stated objective

The pilot validates:

1. **Architecture** — accepted (prior methodological validation)
2. **Temporal modelling & snapshot selection** — accepted; 4 temporal flags documented
3. **Manual validation** — 19/19 archives confirmed correct
4. **Extraction pipeline** — 19/19 observations now produce usable homepage text

The five-firm pilot dataset is **publication-ready** for homepage text extraction and downstream NLP, subject to:

- Documenting temporal flags and scope mismatches in methodology section
- Not claiming 100% family-branding coverage (site-dependent)
- Acknowledging Playwright dependency for modern archived sites

### What is NOT complete (explicitly out of scope)

- Dictionary scoring
- Extension to remaining 25 firms
- Sub-page crawl analysis (homepage-only scope)

---

## Should the Remaining 25 Firms Be Processed?

### **YES** — with documented caveats

| Factor | Evidence | Implication |
|--------|----------|-------------|
| Extraction recall | 14/14 failed observations recovered; 19/19 final | Pipeline generalizes across frames, JS, nav-heavy, and modern sites |
| Archive validity | 19/19 archives confirmed correct at baseline | Bottleneck was extraction, not snapshot selection |
| Generic fixes | No firm-specific hacks; multi-stage + preprocess | Applicable to unseen firm websites |
| Retry resilience | Fetch retry recovers intermittent Wayback errors | Expect ~5–10% retry rate at scale |
| Playwright cost | 58% of observations need Stage D | Budget ~2 min/firm for 4 timepoints with Playwright |
| Residual risk | Frame child fetch failures; temporal misfit possible on sparse CDX | Monitor QA gates; human validation sample recommended |

### Recommended pre-scale checklist

1. Run full pipeline on 25 firms with current multi-stage extraction
2. Apply QA gate: flag `word_count=0` with HTTP 200
3. Sample 10% for manual validation (as done here)
4. Do **not** proceed to dictionary scoring until scale validation completes

### When to answer NO

Would recommend NO if extraction success remained <79% (15/19). Current 100% on validation sample supports YES.

---

## Evidence Summary

| Artifact | Location |
|----------|----------|
| Root cause analysis | `reports/extraction_failure_analysis.md` |
| Improvement metrics | `reports/extraction_improvement.md` |
| Manual validation (baseline) | `reports/manual_validation_report.md` |
| Updated validation CSV | `data/output/manual_validation_sample.csv` |
| Re-extraction results | `data/output/extraction_reextract_results.json` |
| Root cause probes | `data/output/extraction_root_cause.json` |
| Screenshots | `data/output/validation_screenshots/` (19 PNG) |
| Pipeline code | `src/ffb_webminer/extract/text.py`, `html_preprocess.py` |
| Unit tests | `tests/test_text_extraction.py` (3 passing) |

---

## Conclusion

| Question | Answer |
|----------|--------|
| Extraction success rate | **19/19 (100%)** |
| Meets ≥15/19 target? | **YES** |
| Pilot complete? | **YES** |
| Process remaining 25 firms? | **YES** (with Playwright budget, retry logic, and sample validation) |

The archived pages were always valid. The extraction pipeline was the bottleneck. Multi-stage extraction with archived HTML preprocessing resolves the failures observed in manual validation. The five-firm pilot is ready for publication-quality use.
