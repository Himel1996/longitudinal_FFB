# Full-Sample Readiness

**Run ID:** `508f1903-71e7-4aab-aba6-000fed4d8b7d`  
**Git commit:** `cbdd849197cb139b7e3c228c0ec962d8ed16d254`  
**Predecessor:** `pilot_v1_4_1`  
**Bundle:** `data/releases/full_sample_v1/`

## Verdict

# FULL SAMPLE EXTRACTION READY FOR DICTIONARY DEVELOPMENT

## Checklist

| Gate | Status |
|------|--------|
| All 30 firms prepared / discovered / crawled | PASS |
| Batch QC gates (after Canyon repair) | PASS |
| Final release-acceptance invariants | PASS |
| Consistency checks | PASS |
| Stratified manual validation produced | PASS |
| Required `full_sample_*.csv` exports | PASS |
| Dictionary scoring started | **NOT started** (deferred) |

## Headline metrics

- **30** firms · **150** observations · **100** selected snapshots  
- **1,376** branding pages (862 DE) · **692,429** branding tokens  
- **51** primary / **84** sensitivity NLP observations  
- **27** governance pages · **333** duplicate rows / **97,840** tokens removed  

## Remaining limitations

1. Wayback intermittency (`Connection refused`, 404s) reduces some pages; failures are recorded, not skipped silently.  
2. 45 observations beyond temporal tolerance; 4 future-unavailable; 1 event-unavailable.  
3. Large international firms contribute substantial English pages; German primary corpus stays DE-gated.  
4. Stratified manual validation used pipeline evidence (no full Playwright re-screenshot pass for all 30).  
5. Mid-run Canyon `terms-conditions` reserved-slot false positive required a legal-segment alias fix + firm-28 re-crawl.  
6. `crawl_priority_summary.csv` was rebuilt from page tiers after a batch-merge bug (now fixed in code).

## Next step

Dictionary development may begin on the German primary / sensitivity corpora. Do not change extraction eligibility rules mid-dictionary without a new release.
