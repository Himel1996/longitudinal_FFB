# Pilot v1.2 Readiness Report

**Release:** Pilot v1.2  
**Run ID:** `c956bd4e-2b8a-4c48-8780-c187587f46b3`  
**Run date:** 2026-07-23  
**Git commit:** `40284949bcf3e42355fcdf7fd93bacd00610c6f7`  
**Release bundle:** `data/releases/pilot_v1_2/`

---

## Executive summary

Pilot v1.2 fixes Christian Schröder’s three corpus-integrity issues without changing crawl/extraction architecture:

1. Strict legal URL/title precedence before branding categories  
2. Observation corpora export only `text_analysis_eligible = true` rows  
3. Governance layer restricted to Impressum / direct legal-governance evidence  

**Ready to share with Christian:** **YES**  
**Ready to scale to remaining 25 firms:** **YES, after Christian confirms the three integrity fixes**

---

## Key counts

| Metric | Value |
|--------|-------|
| Branding corpus pages | 290 |
| Legal/Impressum/AGB/Datenschutz URLs in branding | 0 |
| Governance pages | 19 |
| Primary NLP-eligible observations | 14 |
| Sensitivity NLP-eligible observations | 16 |
| Consistency checks | PASSED |
| Tests | 47 passed |

---

## Suggested review files

1. `branding_corpus_observations_primary.csv`
2. `branding_corpus_pages.csv`
3. `observation_text_summary.csv`
4. `governance_metadata_pages.csv`
5. `reports/v1_2_change_report.md`
