"""Event-date resolution: verified config vs inferred label parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

MONTH_MAP = {
    "januar": 1, "january": 1, "jan": 1,
    "februar": 2, "february": 2, "feb": 2,
    "märz": 3, "maerz": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "december": 12, "dec": 12,
}


@dataclass(frozen=True)
class EventDateResolution:
    event_date_inferred: date | None
    event_date_verified: date | None
    event_date_final: date | None
    event_date_precision: str
    event_date_source: str
    event_date_verification_status: str  # verified | inferred | unverified_proxy
    target_date_precision: str


@dataclass(frozen=True)
class EventDateInfo:
    """Backward-compatible view used by snapshot target-date logic."""
    event_date: date | None
    event_date_precision: str
    event_date_source: str
    target_date_precision: str


def load_event_date_overrides(path: str | Path | None) -> dict[int, dict[str, Any]]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {int(k): v for k, v in raw.items()}


def resolve_event_date_full(
    firm_row: dict[str, Any],
    overrides: dict[int, dict[str, Any]] | None = None,
) -> EventDateResolution:
    rank = int(firm_row.get("rank", firm_row.get("firm_id", 0)))
    event_year = int(firm_row["event_year"])
    label = str(firm_row.get("event_label", "") or "")

    inferred = _parse_from_label(label, event_year)
    verified: date | None = None
    verified_prec = "year"
    verified_source = ""

    if overrides and rank in overrides:
        o = overrides[rank]
        verified = date.fromisoformat(o["event_date"])
        verified_prec = o.get("event_date_precision", "day")
        verified_source = o.get("event_date_source", "config/event_dates.yaml")
        return EventDateResolution(
            event_date_inferred=inferred.event_date if inferred else None,
            event_date_verified=verified,
            event_date_final=verified,
            event_date_precision=verified_prec,
            event_date_source=verified_source,
            event_date_verification_status="verified",
            target_date_precision=verified_prec if verified_prec != "year" else "month",
        )

    if inferred:
        return EventDateResolution(
            event_date_inferred=inferred.event_date,
            event_date_verified=None,
            event_date_final=inferred.event_date,
            event_date_precision=inferred.event_date_precision,
            event_date_source=f"inferred_from_label: {label.strip()}",
            event_date_verification_status="inferred",
            target_date_precision=inferred.target_date_precision,
        )

    proxy = date(event_year, 7, 1)
    return EventDateResolution(
        event_date_inferred=None,
        event_date_verified=None,
        event_date_final=proxy,
        event_date_precision="year",
        event_date_source=f"unverified_proxy: event_year={event_year} mid-year",
        event_date_verification_status="unverified_proxy",
        target_date_precision="year",
    )


def resolve_event_date(
    firm_row: dict[str, Any],
    overrides: dict[int, dict[str, Any]] | None = None,
) -> EventDateInfo:
    full = resolve_event_date_full(firm_row, overrides)
    return EventDateInfo(
        event_date=full.event_date_final,
        event_date_precision=full.event_date_precision,
        event_date_source=full.event_date_source,
        target_date_precision=full.target_date_precision,
    )


def target_date_for_timepoint(
    relative_timepoint: str,
    target_year: int,
    event_info: EventDateInfo,
    default_month_day: str,
) -> tuple[date, str]:
    if relative_timepoint == "event" and event_info.event_date:
        if event_info.event_date_precision == "day":
            return event_info.event_date, "day"
        if event_info.event_date_precision == "month":
            return event_info.event_date, "month"
        return event_info.event_date, "year"
    month_s, day_s = default_month_day.split("-")
    return date(target_year, int(month_s), int(day_s)), "year"


def _parse_from_label(label: str, event_year: int) -> EventDateInfo | None:
    lower = label.lower()
    for pattern in [r"\b(im\s+)?(\w+)\s+(\d{4})\b", r"\b(\w+)\s+(\d{4})\b"]:
        m = re.search(pattern, lower)
        if m:
            groups = m.groups()
            month_token = groups[-2] if len(groups) >= 2 else None
            year_token = groups[-1]
            if month_token and month_token in MONTH_MAP and int(year_token) == event_year:
                month = MONTH_MAP[month_token]
                return EventDateInfo(
                    event_date=date(event_year, month, 15),
                    event_date_precision="month",
                    event_date_source=f"event_label: {label.strip()}",
                    target_date_precision="month",
                )
    dm = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", label)
    if dm:
        d, mo, y = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        if y == event_year:
            return EventDateInfo(
                event_date=date(y, mo, d),
                event_date_precision="day",
                event_date_source=f"event_label: {label.strip()}",
                target_date_precision="day",
            )
    return None
