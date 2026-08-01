"""Rescue-local archive timestamp helpers (not part of validated core modules)."""

from __future__ import annotations

import re


def normalize_archive_timestamp(timestamp: object) -> str:
    """Coerce CDX timestamps to 14-digit strings after CSV float round-trips."""
    if timestamp is None:
        raise ValueError("archive timestamp is required")
    s = str(timestamp).strip()
    if not s or s.lower() in {"nan", "none", "nat", "<na>"}:
        raise ValueError(f"invalid archive timestamp: {timestamp!r}")
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".", 1)[0]
    elif re.search(r"[.eE]", s):
        try:
            s = f"{int(float(s))}"
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid archive timestamp: {timestamp!r}") from exc
    digits = re.sub(r"\D", "", s)
    if len(digits) < 8:
        raise ValueError(f"invalid archive timestamp: {timestamp!r}")
    return digits[:14] if len(digits) >= 14 else digits


def sanitize_wayback_replay_url(url: object) -> str | None:
    if url is None:
        return None
    s = str(url).strip()
    if not s or s.lower() in {"nan", "none", "nat", "<na>"}:
        return None
    return re.sub(
        r"(web\.archive\.org/web/)(\d+)\.0+([a-z_]*/)",
        r"\1\2\3",
        s,
        flags=re.IGNORECASE,
    )
