"""B. Braun smoke-test summary writer (rescue-only reporting)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_bbraun_smoke_report(
    path: Path,
    *,
    payload: dict[str, Any],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = payload.get("final_status", "SMOKE_TEST_FAILED_LOGIC")
    lines = [
        "# B. Braun Smoke Test — Phase B",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Firm:** {payload.get('firm_id', '10')} / {payload.get('company', 'B. Braun')}",
        f"**Final status:** `{status}`",
        "",
        "## Discovery",
        "",
        f"- Target timepoints: {payload.get('timepoints')}",
        f"- Discovered/selected captures: {payload.get('discovered_captures')}",
        "",
        "## Crawl / cache",
        "",
        f"- Pages planned: {payload.get('pages_planned')}",
        f"- Pages already cached before run: {payload.get('pages_cached_before')}",
        f"- New pages fetched: {payload.get('pages_newly_fetched')}",
        f"- Cache hits: {payload.get('cache_hits')}",
        f"- Pending pages: {payload.get('pending_pages')}",
        f"- Resumable failures: {payload.get('resumable_failures')}",
        "",
        "## Transport",
        "",
        f"- Failures by category: `{payload.get('transport_failures_by_category')}`",
        f"- Retries / attempts: {payload.get('retries')}",
        f"- Circuit openings: {payload.get('circuit_openings')}",
        f"- Cooldown durations (s): {payload.get('cooldown_durations')}",
        f"- CDX probe results: {payload.get('cdx_probe_results')}",
        f"- Replay probe results: {payload.get('replay_probe_results')}",
        "",
        "## Extraction / decisions",
        "",
        f"- Observations extracted: {payload.get('observations_extracted')}",
        f"- German pages / tokens: {payload.get('german_pages_tokens')}",
        f"- Rescue decisions: {payload.get('rescue_decisions')}",
        f"- Longitudinal-ready status: {payload.get('longitudinal_ready')}",
        "",
        "## Integrity",
        "",
        f"- Parent release integrity: {payload.get('parent_release_integrity')}",
        f"- Resume command: `{payload.get('resume_command')}`",
        "",
        "## Notes",
        "",
        payload.get("notes") or "(none)",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
