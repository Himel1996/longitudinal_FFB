# Phase B VM Runbook — Targeted German Rescue

## 1. Purpose

Execute the Phase B targeted rescue for the 19 non-ready firms using
`data/input/full_sample_url_rescue_candidates.csv`, without modifying frozen
`data/releases/full_sample_v1/` or validated extraction rules.

## 2. Preconditions

- Repository checked out with Phase B code present
- Parent release `data/releases/full_sample_v1/` intact
- Candidate CSV present and unchanged
- Stable European network path to `web.archive.org`
- No concurrent writes to the parent release

## 3. Recommended VM

- Ubuntu LTS
- European region
- 2–4 vCPU
- 8 GB RAM
- ≥ 40 GB disk
- Stable public IPv4

## 4. Required repository state

```bash
git status
# Expect Phase B files present; do not modify config/full_sample.yaml
test -f data/releases/full_sample_v1/data/full_sample_branding_corpus_observations_primary.csv
test -f data/input/full_sample_url_rescue_candidates.csv
test -f config/full_sample_rescue.yaml
test -f scripts/run_full_sample_rescue.py
```

## 5. Required input files

- `data/input/full_sample_url_rescue_candidates.csv`
- `data/input/family_firm_event_longlist_30_trimmed.csv`
- `config/event_dates.yaml`
- `data/releases/full_sample_v1/data/*` (read-only parent)

## 6–8. Dependency / Python / Playwright setup

```bash
cd /path/to/FFB
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
# Playwright only if visual extraction is re-enabled later (default rescue visual.enabled=false)
# python -m playwright install chromium
```

## 9. Environment variables

No required secrets. Optional:

```bash
export PYTHONUNBUFFERED=1
```

## 10. Input checksum verification

```bash
shasum -a 256 data/input/full_sample_url_rescue_candidates.csv
shasum -a 256 data/releases/full_sample_v1/data/full_sample_branding_corpus_observations_primary.csv
```

Record both values in the run log.

## 11. Wayback preflight

Preflight now exercises real CDX + archived replay operations (not just the
Wayback homepage):

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage preflight
```

Expect `status: PREFLIGHT_OK` with CDX successes and ≥80% replay success.
On failure the process exits with code 3 (`PREFLIGHT_FAILED_TRANSPORT`) and
must not start discovery/crawl.

## 12. Candidate validation (no network)

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage validate \
  --no-network
```

## 13. Full targeted rescue

```bash
PYTHONUNBUFFERED=1 python -u scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full \
  2>&1 | tee data/interim/full_sample_rescue/rescue_run.log
```

## 14. Resume commands

Page-level resume (preferred after transport pause):

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full \
  --firms 10 \
  --resume
```

Stage-level resume (backward compatible):

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --resume-from crawl

python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --resume-from compare
```

`--resume` reuses valid HTML cache + SQLite `page_fetch_state.sqlite` and valid
discovery artifacts. Exit code **4** = `RESCUE_PAUSED_TRANSPORT_UNSTABLE`
(resumable; not a methodological failure).

## 15. Running one firm first

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full \
  --firms 10
```

## 16. Monitoring progress

```bash
tail -f data/interim/full_sample_rescue/rescue_run.log
wc -l data/interim/full_sample_rescue/rescue_discovery_log.csv
ls data/interim/full_sample_rescue/html | wc -l
```

## 17. Handling HTTP 429

- Stop the run cleanly (Ctrl-C is safe; stages are resumable)
- Wait for Retry-After / cool-down
- Resume with `--resume-from crawl` or later
- Do **not** interpret 429 as archive unavailability

## 18. Handling TLS/EOF failures

- Classified as `transport_failure_resumable`
- Resume later; do not mark snapshots archive_unavailable solely for TLS EOF
- If circuit breaker trips, wait and resume

## 19. Output locations

| Path | Contents |
|------|----------|
| `data/raw/full_sample_rescue/` | reserved raw |
| `data/interim/full_sample_rescue/` | discovery log, decisions, HTML cache, state |
| `data/processed/full_sample_rescue/output/` | working corpora |
| `data/releases/full_sample_v1_1_rescue/` | assembled rescue release |
| `reports/full_sample_rescue/` | impact / acceptance / audit templates + outputs |

## 20. Validation commands

```bash
python -m pytest tests/test_rescue_phase_b.py tests/test_rescue_transport.py -q
python scripts/run_full_sample_rescue.py --config config/full_sample_rescue.yaml --stage validate --no-network
```

## Dependency note: lingua-language-detector

Require `lingua-language-detector>=2.1.1,<3` (see `pyproject.toml`).
Version **2.1.1** is sufficient for the APIs used
(`LanguageDetectorBuilder.from_languages(...).build()` and
`compute_language_confidence_values`). Do not require ≥2.2.

## 21. Release acceptance command

```bash
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage acceptance
```

## 22–23. Packaging / copy back

```bash
tar -czf full_sample_v1_1_rescue_bundle.tgz \
  data/releases/full_sample_v1_1_rescue \
  data/interim/full_sample_rescue/rescue_comparison_decisions.csv \
  data/interim/full_sample_rescue/rescue_discovery_log.csv \
  reports/full_sample_rescue \
  reports/rescue_candidate_input_validation.md
# scp bundle to workstation
```

## 24. Verify full_sample_v1 unchanged

```bash
shasum -a 256 data/releases/full_sample_v1/data/full_sample_branding_corpus_observations_primary.csv
# must match the pre-run checksum
git status -- data/releases/full_sample_v1
```

## 25. Shutting down the VM

```bash
deactivate
# sync/copy outputs first, then stop/delete the VM per cloud provider
```

## Staged sequence (summary)

```bash
# Validate inputs without network
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage validate \
  --no-network

# Remote preflight
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage preflight

# One-firm smoke test
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full \
  --firms 10

# Full targeted rescue
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full

# Resume example
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --resume-from crawl

python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage acceptance
```

---

## Rerunning B. Braun after transport hardening

Use this sequence on the Mac/VM after pulling the transport-hardening commit.
**Do not** start the 19-firm full rescue automatically after B. Braun.

Keep between attempts (do not delete):

- `data/interim/full_sample_rescue/rescue_snapshots.csv`
- `data/interim/full_sample_rescue/rescue_discovery_log.csv`
- `data/interim/full_sample_rescue/html/` (including any prior `.html` cache files)
- `data/interim/full_sample_rescue/state/page_fetch_state.sqlite` (created on first hardened crawl)

```bash
# 1) pull/checkout updated commit, then:
cd /path/to/FFB
git status

# 2) activate venv
source .venv/bin/activate

# 3) reinstall editable package (picks up lingua>=2.1.1,<3)
pip install -e .

# 4) offline validation
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage validate \
  --no-network

# 5) stronger preflight (live CDX + replay probes)
python scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage preflight

# 6) B. Braun smoke with page-level resume
PYTHONUNBUFFERED=1 python -u scripts/run_full_sample_rescue.py \
  --config config/full_sample_rescue.yaml \
  --stage full \
  --firms 10 \
  --resume \
  2>&1 | tee data/interim/full_sample_rescue/bbraun_smoke.log

# 7) inspect smoke report
cat reports/full_sample_rescue/bbraun_smoke_test.md

# 8) STOP — do not launch the 19-firm full rescue until B. Braun is SMOKE_TEST_PASSED
```

Allowed B. Braun final statuses in the smoke report:

- `SMOKE_TEST_PASSED`
- `SMOKE_TEST_PAUSED_TRANSPORT_RESUMABLE` (retry later with the same `--resume` command)
- `SMOKE_TEST_FAILED_LOGIC`

If paused for transport, wait for archive stability, then re-run step 6 only
(or steps 5–6). Cached HTML and SQLite state are preserved.
