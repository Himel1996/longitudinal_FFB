"""Tests for temporal validity scoring."""

from datetime import date

import pandas as pd

from ffb_webminer.archive.snapshot_selector import SnapshotSelection, validate_event_observation
from ffb_webminer.quality.temporal_validity import (
    enrich_snapshots_dataframe,
    temporal_fit_quality,
    temporal_fit_usable_default,
)


def test_temporal_fit_bands():
    assert temporal_fit_quality(30) == "high"
    assert temporal_fit_quality(120) == "moderate"
    assert temporal_fit_quality(250) == "low"
    assert temporal_fit_quality(400) == "very_low"
    assert temporal_fit_usable_default("very_low") is False
    assert temporal_fit_usable_default("high") is True


def test_reject_pre_event_capture_for_event_timepoint():
    sel = SnapshotSelection(
        snapshot_status="selected",
        requested_url="http://www.example.com/",
        canonical_original_url="http://www.example.com/",
        cdx_original_url="http://www.example.com:80/",
        archive_timestamp="20110810103830",
        selected_capture_date=date(2011, 8, 10),
        temporal_distance_days=248,
        wayback_replay_url="https://web.archive.org/web/20110810103830id_/http://www.example.com/",
        http_status="200",
        mime_type="text/html",
        digest="abc",
        redirect_chain=None,
        selection_reason="test",
        fallback_attempts="1",
        failure_reason=None,
        homepage_available=True,
    )
    out = validate_event_observation("event", sel, date(2012, 4, 15), "month", pre_window_days=90)
    assert out.snapshot_status == "event_unavailable"


def test_adjacent_overlap_flag():
    snapshots = pd.DataFrame([
        {
            "firm_id": "1", "relative_timepoint": "pre_event", "snapshot_status": "selected",
            "selected_capture_date": "2011-08-10", "temporal_distance_days": 10,
            "adjacent_period_overlap_flag": False,
        },
        {
            "firm_id": "1", "relative_timepoint": "event", "snapshot_status": "selected",
            "selected_capture_date": "2011-09-01", "temporal_distance_days": 5,
            "adjacent_period_overlap_flag": False,
        },
    ])
    firms = pd.DataFrame([{
        "firm_id": "1",
        "event_date_final": "2012-04-15",
        "event_date_precision": "month",
    }])
    out = enrich_snapshots_dataframe(snapshots, firms, adjacent_min_days=180)
    event_row = out[out["relative_timepoint"] == "event"].iloc[0]
    assert event_row["adjacent_period_overlap_flag"] == True  # noqa: E712
