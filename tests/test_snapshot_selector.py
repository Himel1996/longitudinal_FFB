"""Tests for snapshot selection."""

from datetime import date

from ffb_webminer.archive.snapshot_selector import select_snapshot, target_date_for_year
from ffb_webminer.config import SnapshotSelectionConfig


def _config() -> SnapshotSelectionConfig:
    return SnapshotSelectionConfig(tolerance_days=548, prefer=["closest", "earlier_on_tie"])


def test_target_date_mid_year():
    d = target_date_for_year(2015, _config())
    assert d == date(2015, 7, 1)


def test_future_unavailable():
    sel = select_snapshot([], date(2030, 7, 1), _config(), run_date=date(2026, 7, 13))
    assert sel.snapshot_status == "future_unavailable"


def test_closest_capture():
    captures = [
        {"timestamp": "20150615120000", "original": "http://www.example.com/", "statuscode": "200", "mimetype": "text/html", "digest": "abc"},
        {"timestamp": "20140101000000", "original": "http://www.example.com/", "statuscode": "200", "mimetype": "text/html", "digest": "def"},
    ]
    sel = select_snapshot(captures, date(2015, 7, 1), _config(), run_date=date(2026, 7, 13))
    assert sel.snapshot_status == "selected"
    assert sel.archive_timestamp == "20150615120000"
    assert sel.temporal_distance_days == 16


def test_beyond_tolerance():
    captures = [
        {"timestamp": "20100101000000", "original": "http://www.example.com/", "statuscode": "200", "mimetype": "text/html", "digest": "abc"},
    ]
    sel = select_snapshot(captures, date(2015, 7, 1), _config(), run_date=date(2026, 7, 13))
    assert sel.snapshot_status == "beyond_tolerance"
