"""Tests for duplicate archive capture handling."""

import pandas as pd

from ffb_webminer.quality.duplicate_captures import apply_duplicate_capture_rules


def test_duplicate_capture_marks_loser_exclude():
    snapshots = pd.DataFrame([
        {
            "firm_id": "5",
            "relative_timepoint": "pre_event",
            "snapshot_status": "selected",
            "archive_timestamp": "20050909120000",
            "target_date": "2005-07-01",
            "selected_capture_date": "2005-09-09",
            "observation_recommendation": "sensitivity_analysis",
        },
        {
            "firm_id": "5",
            "relative_timepoint": "event",
            "snapshot_status": "selected",
            "archive_timestamp": "20050909120000",
            "target_date": "2006-01-01",
            "selected_capture_date": "2005-09-09",
            "observation_recommendation": "sensitivity_analysis",
        },
    ])
    out = apply_duplicate_capture_rules(snapshots)
    pre = out[out["relative_timepoint"] == "pre_event"].iloc[0]
    event = out[out["relative_timepoint"] == "event"].iloc[0]
    assert pre["observation_recommendation"] == "sensitivity_analysis"
    assert pre["analysis_eligible"] == True  # noqa: E712
    assert event["observation_recommendation"] == "exclude_duplicate_capture"
    assert event["analysis_eligible"] == False  # noqa: E712
    assert event["duplicate_capture_flag"] == True  # noqa: E712
