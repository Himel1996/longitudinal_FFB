# Full-sample baseline freeze

**Frozen at:** 2026-07-25  
**Predecessor release:** `data/releases/pilot_v1_4_1/`  
**Scaling config:** `config/full_sample.yaml`

## Code

| Field | Value |
|-------|-------|
| Git commit | `8230a11ab637311d6c7c52a8421a3585aedd1921` |
| Commit subject | pilot v1.4.1 |
| Pilot release commit (manifest) | `5a5fec78333d7baead292037b2be2a94f6733366` |

Current HEAD is the definitive scaling baseline after pilot_v1_4_1 acceptance packaging.

## Config hashes (SHA-256)

```
2e3c987c0cb13b2c248d75275d4cacf16370741d791085b43f65079a9622c58b  config/full_sample.yaml
02f871521ef23aa449f075d40305155044d2f1777b70b188352463d43af638a6  config/pilot.yaml
a38e36411aefc9c07666b9baa85e71fb797ac891d41c6d3e64bd109383c6be7c  config/event_dates.yaml
```

**Full-sample run_id:** `508f1903-71e7-4aab-aba6-000fed4d8b7d`  
**Run date:** 2026-07-25

## Invariants locked (do not change during full-sample run)

- snapshot-selection rules
- legal-page exclusions
- governance-layer rules
- within-timepoint deduplication
- cross-timepoint preservation
- language handling
- reserved-slot prioritization
- tokenization policy
- observation eligibility rules

## Execution plan

- Batches of 5 firms (`--firm-id`)
- Preserve `data/interim/cdx` and `data/interim/html`
- Stop if any release-acceptance invariant fails after a batch
- Dictionary scoring deferred until full-sample extraction is accepted
