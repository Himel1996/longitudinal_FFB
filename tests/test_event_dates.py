"""Tests for event date resolution."""

from datetime import date

from ffb_webminer.archive.event_dates import resolve_event_date, target_date_for_timepoint


def test_myrenne_april_2012_from_label():
    firm = {
        "rank": 4,
        "event_year": 2012,
        "event_label": "Übergabe im April 2012 bestätigt",
        "event_source_url": "",
    }
    ev = resolve_event_date(firm, overrides={4: {
        "event_date": "2012-04-15",
        "event_date_precision": "month",
        "event_date_source": "event_label",
    }})
    assert ev.event_date == date(2012, 4, 15)
    assert ev.event_date_precision == "month"

    target, prec = target_date_for_timepoint("event", 2012, ev, "07-01")
    assert target == date(2012, 4, 15)
    assert prec == "month"


def test_resolve_event_date_full_verified_vs_inferred():
    from ffb_webminer.archive.event_dates import resolve_event_date_full

    firm = {
        "rank": 4,
        "event_year": 2012,
        "event_label": "Übergabe im April 2012 bestätigt",
    }
    full = resolve_event_date_full(firm, overrides={4: {
        "event_date": "2012-04-15",
        "event_date_precision": "month",
        "event_date_source": "config/event_dates.yaml",
    }})
    assert full.event_date_verified == date(2012, 4, 15)
    assert full.event_date_inferred == date(2012, 4, 15)
    assert full.event_date_final == date(2012, 4, 15)
    assert full.event_date_verification_status == "verified"
    assert full.event_date_source == "config/event_dates.yaml"


def test_year_level_fallback():
    firm = {"rank": 1, "event_year": 2024, "event_label": "some event", "event_source_url": ""}
    ev = resolve_event_date(firm)
    assert ev.event_date_precision == "year"
    target, prec = target_date_for_timepoint("pre_event", 2022, ev, "07-01")
    assert target == date(2022, 7, 1)
    assert prec == "year"
