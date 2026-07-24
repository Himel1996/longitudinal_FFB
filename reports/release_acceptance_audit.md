# Release Acceptance Audit — pilot_v1_4_1

**Release audited:** `data/releases/pilot_v1_4_1/`  
**Compared against:** `data/archive/pilot_v1_4_pre_v1_4_1/`  
**Run ID:** `95bac495-6940-47be-b3ff-339fd97afa3e`  
**Git commit:** `5a5fec78333d7baead292037b2be2a94f6733366`  
**Audit script:** `scripts/audit_pilot_v1_4_1_acceptance.py`  
**Machine-readable:** `data/interim/release_acceptance_audit.json`

---

## Verdict

# READY TO SCALE

All parts 1–8 **PASS**. Manifest commit matches code HEAD.

---

## Part results

| Part | Check | Result |
|------|-------|--------|
| 1 | Legal exclusion from branding | PASS |
| 2 | Governance scope | PASS |
| 3 | Observation eligibility | PASS |
| 4 | Dedup / cross-time preserve | PASS |
| 5 | Language corpora (DE-only primary pages) | PASS |
| 6 | Reserved-slot priority (segment-aware) | PASS |
| 7 | Token consistency / analysis tokens | PASS |
| 8 | Quality summary consistency | PASS |
| 9 | Comparison vs v1.4 | Meaningful content diffs (expected) |
| 10 | Release acceptance | **READY TO SCALE** |

---

## Blocker fixes verified

### Reserved slots
- No news/product/career/press pages consume reserved `company_about` slots via substring `unternehmen`
- No reserved slots without high-confidence exact path-segment (or delimited Typo3 stem) evidence
- Legal / foreign reserved consumption: **0**

### Tokens
- Policy: `token_count` == `analysis_token_count` (choice A)
- Usable substantive pages with `analysis_token_count == 0`: **0**
- Chinese Peter-Lacke page: `analysis_token_count=716`, method=`unicode_cjk_chars`, not German-corpus-eligible

---

## Comparison snapshot (v1.4 → v1.4.1)

| Metric | v1.4 | v1.4.1 |
|--------|-----:|-------:|
| Pages | 394 | 394 |
| Branding pages (all) | 249 | 242 |
| Branding DE / EN / other | 243 / 2 / 4 | 234 / 4 / 4 |
| Branding token sum | 67,967 | 66,770 |
| Primary / sensitivity obs | 14 / 16 | 14 / 16 |
| Duplicate rows | 86 | 93 |
