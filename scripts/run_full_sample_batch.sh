#!/usr/bin/env bash
# Run one full-sample firm batch: discover → crawl → validate/export → QC gate.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CONFIG="${CONFIG:-config/full_sample.yaml}"
BATCH_LABEL="${1:?batch label required, e.g. 01_firms_1_5}"
shift
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <batch_label> <firm_id> [firm_id...]" >&2
  exit 1
fi
FIRM_ARGS=()
for fid in "$@"; do
  FIRM_ARGS+=(--firm-id "$fid")
done
LOG_DIR=data/interim/full_sample_batches
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/batch_${BATCH_LABEL}.log"
echo "=== BATCH $BATCH_LABEL firms=$* $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
.venv/bin/python -m ffb_webminer discover-snapshots --config "$CONFIG" "${FIRM_ARGS[@]}" 2>&1 | tee -a "$LOG"
.venv/bin/python -m ffb_webminer crawl --config "$CONFIG" "${FIRM_ARGS[@]}" 2>&1 | tee -a "$LOG"
.venv/bin/python <<PY 2>&1 | tee -a "$LOG"
from pathlib import Path
from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline.runner import PipelineRunner
r = PipelineRunner(PipelineConfig.from_yaml("$CONFIG"), project_root=Path(".").resolve())
stats = r.validate_and_export()
r.report()
print("VALIDATE_OK", stats)
PY
QC_ARGS=()
for fid in "$@"; do
  QC_ARGS+=(--firm-id "$fid")
done
.venv/bin/python scripts/full_sample_batch_qc.py --batch-label "$BATCH_LABEL" "${QC_ARGS[@]}" 2>&1 | tee -a "$LOG"
echo "=== BATCH $BATCH_LABEL DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
