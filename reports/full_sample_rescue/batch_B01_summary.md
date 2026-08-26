# Batch B01 Summary — PAUSED_TRANSPORT

**Generated:** 2026-08-26 04:58 UTC  
**Firms:** 2 (Peter-Lacke), 11 (Harting), 12 (Rossmann)  
**Status:** `PAUSED_TRANSPORT`

## Progress when paused

| Firm | Discovery selections | FETCHED | FETCH_FAILED_RESUMABLE |
|------|----------------------|---------|------------------------|
| 2 Peter-Lacke | 4 | 0 | 0 |
| 11 Harting | 4 | 72 | 6 |
| 12 Rossmann | 4 | 0 | 0 |
| 10 B. Braun (untouched) | 5 | 152 | 3 |

- Discovery completed earlier: `selected=12` for B01 firms
- Crawl paused mid-Harting with circuit breaker after sustained connection refused / TLS / timeout failures
- Exit: `RESCUE_PAUSED_TRANSPORT_UNSTABLE`
- Cache/state preserved (html, page_fetch_state, discovery state, snapshots)

## Resume

Require two consecutive `PREFLIGHT_OK`, then:

```bash
PYTHONUNBUFFERED=1 python -u scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full --firms 2 11 12 --resume \
  2>&1 | tee -a data/interim/full_sample_rescue/batch_B01.log
```

Do not clear caches. Do not start Batch B02 until B01 completes.
