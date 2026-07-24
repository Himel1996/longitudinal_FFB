# FFB Pilot Dataset v1.3.1

**Release date:** 2026-07-24  
**Run ID:** `6f4f1dd0-8f2a-42ca-ae1d-7f3067b47fc9`  
**Git commit:** `565da6bfd8969793d64c80a4d2d68850a25e4191`

## Contents

Final clean rebuild of Pilot v1.3 with legal-path demotion applied during crawl:

- `/unternehmen/` legal pages (Impressum, AGB, Datenschutz, etc.) cannot consume reserved About/company slots
- within firm × timepoint deduplication
- hybrid language handling with German-only primary corpus
- reserved-slot staged crawl prioritization

See `reports/v1_3_1_change_report.md` and `reports/reproducibility.md`.

Family Firm Branding in Transition — Archived Web Pipeline (Pilot v1.3.1)
