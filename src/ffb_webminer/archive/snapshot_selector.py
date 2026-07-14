"""Snapshot selection relative to target dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from dateutil import parser as date_parser

from ffb_webminer.archive.wayback_url import build_replay_url
from ffb_webminer.config import SnapshotSelectionConfig


@dataclass
class SnapshotSelection:
    snapshot_status: str
    requested_url: str | None
    canonical_original_url: str | None
    archive_timestamp: str | None
    selected_capture_date: date | None
    temporal_distance_days: int | None
    wayback_replay_url: str | None
    http_status: str | None
    mime_type: str | None
    digest: str | None
    redirect_chain: str | None
    selection_reason: str | None
    fallback_attempts: str | None
    failure_reason: str | None


def target_date_for_year(target_year: int, config: SnapshotSelectionConfig) -> date:
    month, day = config.target_month_day.split("-")
    return date(target_year, int(month), int(day))


def capture_date_from_timestamp(ts: str) -> date:
    return datetime.strptime(ts[:8], "%Y%m%d").date()


def select_snapshot(
    captures: list[dict[str, str]],
    target: date,
    config: SnapshotSelectionConfig,
    run_date: date | None = None,
) -> SnapshotSelection:
    run_date = run_date or date.today()
    attempts = str(len(captures))

    if target > run_date:
        return SnapshotSelection(
            snapshot_status="future_unavailable",
            requested_url=None,
            canonical_original_url=None,
            archive_timestamp=None,
            selected_capture_date=None,
            temporal_distance_days=None,
            wayback_replay_url=None,
            http_status=None,
            mime_type=None,
            digest=None,
            redirect_chain=None,
            selection_reason="target_date_in_future",
            fallback_attempts=attempts,
            failure_reason=None,
        )

    if not captures:
        return SnapshotSelection(
            snapshot_status="not_found",
            requested_url=None,
            canonical_original_url=None,
            archive_timestamp=None,
            selected_capture_date=None,
            temporal_distance_days=None,
            wayback_replay_url=None,
            http_status=None,
            mime_type=None,
            digest=None,
            redirect_chain=None,
            selection_reason="no_cdx_results",
            fallback_attempts=attempts,
            failure_reason="no_matching_captures",
        )

    candidates: list[tuple[int, date, dict[str, str]]] = []
    for row in captures:
        ts = row.get("timestamp", "")
        if len(ts) < 8:
            continue
        cap_date = capture_date_from_timestamp(ts)
        distance = abs((cap_date - target).days)
        if distance <= config.tolerance_days:
            candidates.append((distance, cap_date, row))

    if not candidates:
        return SnapshotSelection(
            snapshot_status="beyond_tolerance",
            requested_url=None,
            canonical_original_url=None,
            archive_timestamp=None,
            selected_capture_date=None,
            temporal_distance_days=None,
            wayback_replay_url=None,
            http_status=None,
            mime_type=None,
            digest=None,
            redirect_chain=None,
            selection_reason="no_capture_within_tolerance",
            fallback_attempts=attempts,
            failure_reason=f"nearest_capture_exceeds_{config.tolerance_days}_days",
        )

    # Sort: closest distance, then earlier_on_tie if configured
    prefer_earlier = "earlier_on_tie" in config.prefer

    def sort_key(item: tuple[int, date, dict[str, str]]) -> tuple:
        distance, cap_date, row = item
        if prefer_earlier:
            return (distance, cap_date.toordinal() * -1)
        return (distance, cap_date.toordinal())

    candidates.sort(key=sort_key)
    distance, cap_date, row = candidates[0]
    ts = row["timestamp"]
    original = row.get("original", "")
    replay = build_replay_url(original, ts)

    reason = f"closest_within_{config.tolerance_days}d"
    if distance == 0:
        reason = "exact_date_match"
    elif cap_date < target:
        reason += "_earlier"
    else:
        reason += "_later"

    return SnapshotSelection(
        snapshot_status="selected",
        requested_url=original,
        canonical_original_url=original,
        archive_timestamp=ts,
        selected_capture_date=cap_date,
        temporal_distance_days=distance,
        wayback_replay_url=replay,
        http_status=row.get("statuscode"),
        mime_type=row.get("mimetype"),
        digest=row.get("digest"),
        redirect_chain=row.get("redirect") or None,
        selection_reason=reason,
        fallback_attempts=attempts,
        failure_reason=None,
    )
