# Full-Sample Rescue Code-Change Audit

**Generated:** 2026-07-31 14:51 UTC

## Expected categories

| Category | Paths |
|----------|-------|
| Rescue orchestration | `scripts/run_full_sample_rescue.py`, `src/ffb_webminer/rescue/` |
| Rescue configuration | `config/full_sample_rescue.yaml` |
| Reporting | `reports/full_sample_rescue/`, report generators |
| Tests | `tests/test_rescue_phase_b.py` |
| Documentation | `docs/PHASE_B_VM_RUNBOOK.md` |
| Validated core pipeline | **0 changes expected** |

Re-run `git diff --name-only -- src/ffb_webminer/pipeline src/ffb_webminer/crawl src/ffb_webminer/archive src/ffb_webminer/extract src/ffb_webminer/quality` before freeze.
