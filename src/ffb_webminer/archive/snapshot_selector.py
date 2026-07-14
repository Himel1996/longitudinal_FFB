"""Snapshot selection relative to target dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ffb_webminer.archive.wayback_url import build_replay_url, is_homepage_path, normalize_canonical_from_cdx
from ffb_webminer.config import SnapshotSelectionConfig


@dataclass
class SnapshotSelection:
    snapshot_status: str
    requested_url: str | None
    canonical_original_url: str | None
    cdx_original_url: str | None
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
    homepage_available: bool = False
    relevant_subpages_available: bool = False
    subpage_only_observation: bool = False


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
    homepage_only: bool = True,
) -> SnapshotSelection:
    run_date = run_date or date.today()
    attempts = str(len(captures))

    empty = SnapshotSelection(
        snapshot_status="not_found",
        requested_url=None,
        canonical_original_url=None,
        cdx_original_url=None,
        archive_timestamp=None,
        selected_capture_date=None,
        temporal_distance_days=None,
        wayback_replay_url=None,
        http_status=None,
        mime_type=None,
        digest=None,
        redirect_chain=None,
        selection_reason=None,
        fallback_attempts=attempts,
        failure_reason=None,
    )

    if target > run_date:
        empty.snapshot_status = "future_unavailable"
        empty.selection_reason = "target_date_in_future"
        empty.failure_reason = None
        return empty

    if not captures:
        empty.selection_reason = "no_cdx_results"
        empty.failure_reason = "no_matching_captures"
        return empty

    # Prefer homepage captures when requested
    pool = captures
    if homepage_only:
        home = [c for c in captures if is_homepage_path(c.get("original", ""))]
        if home:
            pool = home

    candidates: list[tuple[int, date, dict[str, str]]] = []
    for row in pool:
        ts = row.get("timestamp", "")
        if len(ts) < 8:
            continue
        cap_date = capture_date_from_timestamp(ts)
        distance = abs((cap_date - target).days)
        if distance <= config.tolerance_days:
            candidates.append((distance, cap_date, row))

    if not candidates:
        empty.snapshot_status = "beyond_tolerance"
        empty.selection_reason = "no_capture_within_tolerance"
        empty.failure_reason = f"nearest_capture_exceeds_{config.tolerance_days}_days"
        return empty

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
    canonical, cdx_orig = normalize_canonical_from_cdx(original)
    replay = build_replay_url(original, ts)

    reason = f"closest_within_{config.tolerance_days}d"
    if distance == 0:
        reason = "exact_date_match"
    elif cap_date < target:
        reason += "_earlier"
    else:
        reason += "_later"
    if homepage_only and is_homepage_path(original):
        reason += "_homepage"

    return SnapshotSelection(
        snapshot_status="selected",
        requested_url=original,
        canonical_original_url=canonical,
        cdx_original_url=cdx_orig,
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
        homepage_available=is_homepage_path(original),
    )


def validate_event_observation(
    relative_timepoint: str,
    sel: SnapshotSelection,
    event_date: date | None,
    event_date_precision: str,
    pre_window_days: int = 90,
) -> SnapshotSelection:
    """Reject misaligned pre-event captures for the event timepoint."""
    if relative_timepoint != "event" or sel.snapshot_status != "selected":
        return sel
    if event_date is None or sel.selected_capture_date is None:
        return sel
    if event_date_precision not in ("day", "month"):
        return sel
    if sel.selected_capture_date < event_date:
        days_before = (event_date - sel.selected_capture_date).days
        if days_before > pre_window_days:
            sel.snapshot_status = "event_unavailable"
            sel.failure_reason = (
                f"closest_homepage_capture_{sel.selected_capture_date.isoformat()}_is_"
                f"{days_before}d_before_event_{event_date.isoformat()}"
            )
            sel.selection_reason = "rejected_pre_event_capture_for_event_timepoint"
    return sel
