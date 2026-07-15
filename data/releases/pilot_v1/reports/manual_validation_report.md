# Manual Validation Report — Pilot v1.0

**Run ID:** `a48bc35c-844b-4358-afb4-290410db7f5d`  
**Validation date:** 2026-07-15
**Method:** Playwright Chromium screenshots + comparison to regenerated `pages.csv` homepage extraction.

**Evidence:** `data/output/validation_screenshots/` (19 PNG)  
**URL manifest:** `data/output/evidence/validation_screenshot_urls.json`

---

## Summary

| Metric | Count |
|--------|-------|
| Observations validated | 19 |
| correct_company | 19 |
| valid_archived_page | 19 |
| temporally_appropriate | 16 |
| content_extraction_usable | **18** |
| duplicate_capture | 1 |

## Per-observation results

| Firm | Timepoint | Extraction usable | Temporal OK | Screenshot |
|------|-----------|-------------------|-------------|------------|
| BLUE MOON COMMUNICATION CONSUL | pre_pre_event | True | True | `validation_screenshots/01_1_blue_moon_communication__pre_pre_event.png` |
| BLUE MOON COMMUNICATION CONSUL | pre_event | True | True | `validation_screenshots/02_1_blue_moon_communication__pre_event.png` |
| BLUE MOON COMMUNICATION CONSUL | event | True | False | `validation_screenshots/03_1_blue_moon_communication__event.png` |
| BLUE MOON COMMUNICATION CONSUL | post_event | True | True | `validation_screenshots/04_1_blue_moon_communication__post_event.png` |
| PETER-LACKE HOLDING GMBH | pre_pre_event | True | True | `validation_screenshots/05_2_peter_lacke_holding_gmbh_pre_pre_event.png` |
| PETER-LACKE HOLDING GMBH | pre_event | True | True | `validation_screenshots/06_2_peter_lacke_holding_gmbh_pre_event.png` |
| PETER-LACKE HOLDING GMBH | event | True | True | `validation_screenshots/07_2_peter_lacke_holding_gmbh_event.png` |
| ANLAGENTECHNIK LEICHTLE GMBH | pre_pre_event | True | True | `validation_screenshots/08_3_anlagentechnik_leichtle__pre_pre_event.png` |
| ANLAGENTECHNIK LEICHTLE GMBH | pre_event | True | True | `validation_screenshots/09_3_anlagentechnik_leichtle__pre_event.png` |
| ANLAGENTECHNIK LEICHTLE GMBH | event | True | True | `validation_screenshots/10_3_anlagentechnik_leichtle__event.png` |
| ANLAGENTECHNIK LEICHTLE GMBH | post_event | True | True | `validation_screenshots/11_3_anlagentechnik_leichtle__post_event.png` |
| MYRENNE GMBH | pre_pre_event | False | True | `validation_screenshots/12_4_myrenne_gmbh_pre_pre_event.png` |
| MYRENNE GMBH | pre_event | True | True | `validation_screenshots/13_4_myrenne_gmbh_pre_event.png` |
| MYRENNE GMBH | post_event | True | True | `validation_screenshots/14_4_myrenne_gmbh_post_event.png` |
| MYRENNE GMBH | post_post_event | True | True | `validation_screenshots/15_4_myrenne_gmbh_post_post_event.png` |
| MSF-VATHAUER ANTRIEBSTECHNIK G | pre_pre_event | True | False | `validation_screenshots/16_5_msf_vathauer_antriebstec_pre_pre_event.png` |
| MSF-VATHAUER ANTRIEBSTECHNIK G | event | True | False | `validation_screenshots/17_5_msf_vathauer_antriebstec_event.png` |
| MSF-VATHAUER ANTRIEBSTECHNIK G | post_event | True | True | `validation_screenshots/18_5_msf_vathauer_antriebstec_post_event.png` |
| MSF-VATHAUER ANTRIEBSTECHNIK G | post_post_event | True | True | `validation_screenshots/19_5_msf_vathauer_antriebstec_post_post_event.png` |

## Screenshot URL index

| # | Firm | Timepoint | Wayback URL |
|---|------|-----------|-------------|
| 1 | 1 | pre_pre_event | https://web.archive.org/web/20201101073754id_/https://www.bluemoon.de/... |
| 2 | 1 | pre_event | https://web.archive.org/web/20220707114701id_/https://www.bluemoon.de/... |
| 3 | 1 | event | https://web.archive.org/web/20250314235344id_/https://www.bluemoon.de/... |
| 4 | 1 | post_event | https://web.archive.org/web/20260304002641id_/https://www.bluemoon.de/... |
| 5 | 2 | pre_pre_event | https://web.archive.org/web/20110709094353id_/http://www.peter-lacke.de:80/... |
| 6 | 2 | pre_event | https://web.archive.org/web/20130703032151id_/http://www.peter-lacke.de:80/... |
| 7 | 2 | event | https://web.archive.org/web/20150522040733id_/http://www.peter-lacke.de:80/... |
| 8 | 3 | pre_pre_event | https://web.archive.org/web/20190723051243id_/https://www.anlagentechnik-leichtl... |
| 9 | 3 | pre_event | https://web.archive.org/web/20210623054251id_/https://www.anlagentechnik-leichtl... |
| 10 | 3 | event | https://web.archive.org/web/20230529054753id_/https://www.anlagentechnik-leichtl... |
| 11 | 3 | post_event | https://web.archive.org/web/20250615044832id_/https://www.anlagentechnik-leichtl... |
| 12 | 4 | pre_pre_event | https://web.archive.org/web/20080820062004id_/http://www.myrenne.com/... |
| 13 | 4 | pre_event | https://web.archive.org/web/20100427181748id_/http://www.myrenne.com:80/... |
| 14 | 4 | post_event | https://web.archive.org/web/20140517163035id_/http://myrenne.com/... |
| 15 | 4 | post_post_event | https://web.archive.org/web/20160801210455id_/http://www.myrenne.com/... |
| 16 | 5 | pre_pre_event | https://web.archive.org/web/20010723123022id_/http://www.msf-technik.de:80/... |
| 17 | 5 | event | https://web.archive.org/web/20050909231716id_/http://www.msf-technik.de:80/... |
| 18 | 5 | post_event | https://web.archive.org/web/20080327012906id_/http://msf-technik.de:80/... |
| 19 | 5 | post_post_event | https://web.archive.org/web/20100618062303id_/http://www.msf-technik.de:80/... |
