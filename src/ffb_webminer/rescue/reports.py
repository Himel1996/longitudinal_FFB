"""Report generators/templates for Phase B (no fabricated run statistics)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_candidate_validation_report(
    path: Path,
    report: dict[str, Any],
    *,
    candidate_hash: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Rescue Candidate Input Validation",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Candidate SHA-256:** `{candidate_hash}`",
        f"**Safe to execute:** `{report.get('safe_to_execute')}`",
        "",
        "## Summary",
        "",
        f"- Rows loaded: {report.get('rows_loaded')}",
        f"- Firms: {report.get('firms_represented')}",
        f"- Timepoints: {report.get('timepoints_represented')}",
        f"- Unknown firm IDs: {report.get('unknown_firm_ids')}",
        f"- Firms not in non-ready set: {report.get('firms_not_in_nonready_set')}",
        f"- Ambiguous periods: {report.get('ambiguous_period_mappings')}",
        f"- Invalid URLs: {report.get('invalid_urls')}",
        f"- Missing fields: {report.get('missing_required_fields')}",
        f"- Duplicate keys: {len(report.get('duplicate_candidate_rows') or [])}",
        "",
        "## Hard-fail reasons",
        "",
    ]
    reasons = report.get("hard_fail_reasons") or []
    if reasons:
        lines.extend(f"- {r}" for r in reasons)
    else:
        lines.append("- (none)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_impact_report_template() -> str:
    return f"""# Full-Sample Rescue Impact — Phase B

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
**Status:** TEMPLATE — populate only after a completed rescue run.

## Sections to fill from run artifacts

1. Firms targeted
2. Candidate seeds evaluated
3. Timepoints rescued
4. Observations replaced
5. Sensitivity alternatives added
6. German counts before and after
7. Longitudinal readiness before and after
8. Firms newly ready
9. Firms still not ready
10. Rejected candidates
11. Migrations
12. Entity-change warnings
13. Special-case outcomes (MSF, Freudenberg, STIHL, Viessmann, Oetker)
14. Remaining limitations

Do not invent statistics. Source tables:

- `rescue_comparison_decisions.csv`
- `firm_longitudinal_coverage.csv`
- parent vs rescue corpus counts
"""


def render_acceptance_report_template() -> str:
    return f"""# Full-Sample Rescue Release Acceptance

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
**Status:** TEMPLATE — complete after release assembly and audits.

## Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Candidate-file validation | |
| 2 | Targeted execution only | |
| 3 | Timepoint-specific seed support | |
| 4 | Temporal-policy preservation | |
| 5 | Extraction-rule preservation | |
| 6 | Non-targeted immutability | |
| 7 | Parent release unchanged | |
| 8 | German sensitivity exports | |
| 9 | Firm coverage export | |
| 10 | Special cases documented | |
| 11 | Transport failures classified as resumable | |
| 12 | Manual validation sample prepared | |

## Verdict

`NOT READY TO FREEZE` until a real rescue run completes on the VM.
"""


def render_code_change_audit_template() -> str:
    return f"""# Full-Sample Rescue Code-Change Audit

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

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
"""


def render_manual_validation_template() -> str:
    return f"""# Full-Sample Rescue Manual Validation

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
**Status:** TEMPLATE — fill after sampling on the VM.

Use `rescue_manual_validation_sample.csv` strata:

- newly German-ready firms
- historical-domain rescue
- locale-path rescue
- archived-subpage rescue
- MSF / Freudenberg / STIHL / Viessmann / Oetker
- failed rescue
- unchanged observation
"""


def write_report_templates(reports_dir: Path) -> list[Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "full_sample_rescue_impact.md": render_impact_report_template(),
        "full_sample_rescue_release_acceptance.md": render_acceptance_report_template(),
        "full_sample_rescue_code_change_audit.md": render_code_change_audit_template(),
        "full_sample_rescue_manual_validation.md": render_manual_validation_template(),
    }
    written: list[Path] = []
    for name, text in mapping.items():
        path = reports_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
