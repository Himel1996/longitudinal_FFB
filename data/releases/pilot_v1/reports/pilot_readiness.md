# Pilot v1.0 Readiness Report

**Release:** Pilot v1.0  
**Run ID:** `a48bc35c-844b-4358-afb4-290410db7f5d`  
**Run date:** 2026-07-15  
**Git commit:** `e1d11cb16d0b99309dae50f1893e2051e735fdae`  
**Release bundle:** `data/releases/pilot_v1/`

---

## Executive Summary

The five-firm pilot dataset has been **regenerated from scratch** using the final multi-stage extraction pipeline. Manual validation confirms **18 of 19** observations have usable extraction for NLP analysis, exceeding the ≥15/19 success criterion.

**Ready to share with Christian:** **YES** — with documented limitations below.

---

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Firms | 5 |
| Snapshot observations | 25 |
| Selected snapshots | 20 |
| Total page rows | 394 |
| Pages usable for analysis | 358 |
| Primary analysis observations | 16 |
| Sensitivity observations | 19 |
| Manual validation sample | 19 |

---

## Manual Validation Results

| Field | TRUE | FALSE |
|-------|------|-------|
| correct_company | 19 | 0 |
| valid_archived_page | 19 | 0 |
| temporally_appropriate | 16 | 3 |
| content_extraction_usable | **18** | 1 |
| duplicate_capture | 1 | 18 |

**Evidence:** 19 screenshots in `data/output/validation_screenshots/`  
**URL manifest:** `data/output/evidence/validation_screenshot_urls.json`  
**Report:** `reports/manual_validation_report.md`

### Single extraction failure

| Observation | Words | Issue |
|-------------|-------|-------|
| 4\|pre_pre_event (Myrenne 2008) | 35 | HTML frameset; partial frame expansion; welcome text only |

### Temporal flags (archival, not extraction)

| Observation | Issue |
|-------------|-------|
| 1\|event | Capture Mar 2025 (~8 months post-2024 event) |
| 5\|pre_pre_event | Capture Jul 2001 (~11 months before 2002 target) |
| 5\|event | Duplicate timestamp with excluded pre_event |

---

## Extraction Success by Firm

| Firm | Homepage observations | Usable extraction |
|------|----------------------|-------------------|
| BLUE MOON (1) | 4 | 4/4 |
| PETER-LACKE (2) | 3 | 3/3 |
| LEICHTLE (3) | 4 | 4/4 |
| MYRENNE (4) | 4 | 3/4 |
| MSF-VATHAUER (5) | 4 | 4/4 |

---

## Remaining Limitations

1. **Wayback intermittency** — Connection refused errors during crawl; mitigated by 5-attempt retry in fetcher.
2. **Playwright dependency** — Modern JS sites require Stage D extraction (~60% of observations).
3. **Frameset sites** — Myrenne 2008 and MSF legacy pages need frame expansion; MSF intro pages require JS redirect follow.
4. **Visual extraction** — `homepage_visuals.csv` partially populated; many Wayback renders failed at release time.
5. **Sparse homepages** — Leichtle (49–122 words) and Peter-Lacke event (31 words) are service-focused with minimal family-branding language by site design.

---

## Pipeline Changes in v1.0

| Component | Change |
|-----------|--------|
| `fetcher.py` | Working retry loop (5 attempts); config-driven `retries` |
| `html_preprocess.py` | Wayback strip, JS redirect, frameset merge; `/web/` path fix |
| `text.py` | Multi-stage extraction A→E with quality scoring |
| `schemas.py` | Added `validation_screenshot_path` to manual validation columns |

---

## Reproducibility

See `reports/reproducibility.md` for exact commands, package versions, and expected outputs.

---

## Recommendation

| Question | Answer |
|----------|--------|
| Pilot v1.0 complete? | **YES** |
| Meets ≥15/19 extraction target? | **YES** (18/19) |
| Ready for Christian? | **YES** |
| Process remaining 25 firms? | **YES** — after Christian reviews v1.0; expect similar Wayback retry requirements |

---

## Release Contents

`data/releases/pilot_v1/` contains:

- All CSV outputs + `run_manifest.json`
- Reports (quality, validation, readiness, reproducibility)
- 19 validation screenshots + evidence manifest
- Configuration (`config/pilot.yaml`, `config/event_dates.yaml`)
- README
