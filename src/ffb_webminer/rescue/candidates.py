"""Rescue candidate ingestion and validation (Phase B).

Does not alter validated extraction rules. Reads Christian's rescue CSV and
normalizes firm × timepoint seed aliases.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

PERIOD_TO_TIMEPOINTS = {
    "pre": ("pre_pre_event", "pre_event"),
    "post": ("post_event", "post_post_event"),
    "all": ("pre_pre_event", "pre_event", "event", "post_event", "post_post_event"),
    "event": ("event",),
    "pre_pre_event": ("pre_pre_event",),
    "pre_event": ("pre_event",),
    "post_event": ("post_event",),
    "post_post_event": ("post_post_event",),
}

URL_RE = re.compile(r"^https?://[^\s]+$", re.I)


@dataclass
class NormalizedCandidate:
    source_row_id: int
    firm_id: str
    company: str
    event_year: str | None
    event_cluster: str | None
    target_period: str
    target_timepoint: str
    candidate_seed_url: str
    candidate_domain: str
    locale: str | None
    candidate_type: str
    priority: int
    rescue_strength: str
    assessment: str
    archive_evidence: str
    special_handling: str
    historical_domain_flag: bool
    locale_path_flag: bool
    entity_change_warning: bool
    migration_warning: bool
    original_columns: dict[str, Any] = field(default_factory=dict)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _as_str(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def classify_candidate_type(url: str, assessment: str, rescue_status: str) -> str:
    u = url.lower()
    a = (assessment + " " + rescue_status).lower()
    path = urlparse(url).path or "/"
    if "entity" in a:
        pass
    if any(x in path for x in ("/de/", "/de.", "/de-", "index.de", "/de.html", "/de/home")):
        if path.rstrip("/") in {"/de", "/de.html"} or path.endswith("/de/") or "/de/home" in path:
            return "locale_path"
    if "locale" in a or "german locale" in a:
        return "locale_path"
    if "migration" in a or "migrated" in a or "historical domain" in a or "domain migration" in a:
        return "historical_domain" if "historical" in a or "migration" in a else "migrated_domain"
    if "subdomain" in a or "corporate subdomain" in a:
        return "corporate_root_alias"
    if any(x in path for x in ("historie", "geschichte", "history", "heritage")):
        return "history_page"
    if any(x in path for x in ("familie", "family", "owners", "eigent")):
        return "family_or_owner_page"
    if any(x in path for x in ("management", "geschaeftsfuehrung", "geschäftsführung", "fuehrung")):
        return "management_page"
    if any(x in path for x in ("werte", "verantwortung", "sustainab", "responsibility", "values")):
        return "responsibility_or_values_page"
    if any(x in path for x in ("ueber-uns", "über-uns", "about", "unternehmen", "company")):
        if path.count("/") >= 2 and path.rstrip("/") not in {"", "/"}:
            return "about_page" if "about" in path or "ueber" in path or "über" in path else "company_section"
        return "company_section"
    if path not in ("/", "") and path.count("/") >= 2:
        return "archived_subpage_seed"
    if "holding" in u or "group" in path or "gruppe" in path:
        return "corporate_root_alias"
    if path in ("/", "") or path.endswith("/index.jsp") or path.endswith("/home.aspx"):
        return "historical_domain" if "historical" in a else "corporate_root_alias"
    return "other"


def detect_locale(url: str) -> str | None:
    path = (urlparse(url).path or "").lower()
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".de") and "/de" not in path:
        return "de-domain"
    if "/de/" in path or path.endswith("/de") or path.endswith("/de.html") or "index.de" in path:
        return "de"
    if "/en/" in path or path.endswith("/en"):
        return "en"
    return None


def expand_seed_variants(seed_url: str) -> list[str]:
    """Legitimate variants only: scheme, www, trailing slash."""
    parsed = urlparse(seed_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return [seed_url]
    host = parsed.netloc
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    hosts = {host}
    if host.startswith("www."):
        hosts.add(host[4:])
    else:
        hosts.add("www." + host)
    out: list[str] = []
    for scheme in ("https", "http"):
        for h in hosts:
            for p in {path, path.rstrip("/") + "/" if path != "/" else "/"}:
                out.append(f"{scheme}://{h}{p}{query}")
    # preserve original first
    uniq = [seed_url]
    for u in out:
        if u not in uniq:
            uniq.append(u)
    return uniq


def load_raw_candidates(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def normalize_candidates(
    raw: pd.DataFrame,
    *,
    nonready_firm_ids: set[str],
    known_firm_ids: set[str],
) -> tuple[list[NormalizedCandidate], dict[str, Any]]:
    report: dict[str, Any] = {
        "rows_loaded": len(raw),
        "firms_represented": [],
        "timepoints_represented": [],
        "duplicate_candidate_rows": [],
        "invalid_urls": [],
        "unknown_firm_ids": [],
        "firms_not_in_nonready_set": [],
        "ambiguous_period_mappings": [],
        "missing_required_fields": [],
        "safe_to_execute": True,
        "hard_fail_reasons": [],
    }

    required = ["firm_id", "seed_url", "period"]
    for col in required:
        if col not in raw.columns:
            report["missing_required_fields"].append(col)
            report["safe_to_execute"] = False
            report["hard_fail_reasons"].append(f"missing_column:{col}")

    if not report["safe_to_execute"]:
        return [], report

    normalized: list[NormalizedCandidate] = []
    seen_keys: dict[tuple[str, str, str], int] = {}

    for idx, row in raw.iterrows():
        source_row_id = int(idx) + 2  # 1-based CSV line approx (header=1)
        firm_id = _as_str(row.get("firm_id"))
        company = _as_str(row.get("company"))
        period = _as_str(row.get("period")).lower()
        seed = _as_str(row.get("seed_url")).strip('"')
        priority = int(float(_as_str(row.get("priority") or "1") or "1"))
        rescue_status = _as_str(row.get("rescue_status"))
        assessment = _as_str(row.get("assessment"))
        archive_evidence = _as_str(row.get("archive_evidence"))
        event_year = _as_str(row.get("event_year")) or None
        event_cluster = _as_str(row.get("event_cluster")) or None

        missing = []
        if not firm_id:
            missing.append("firm_id")
        if not seed:
            missing.append("seed_url")
        if not period:
            missing.append("period")
        if missing:
            report["missing_required_fields"].append({"row": source_row_id, "fields": missing})
            report["safe_to_execute"] = False
            report["hard_fail_reasons"].append(f"row_{source_row_id}_missing_fields")
            continue

        if firm_id not in known_firm_ids:
            report["unknown_firm_ids"].append(firm_id)
            report["safe_to_execute"] = False
            report["hard_fail_reasons"].append(f"unknown_firm:{firm_id}")
            continue

        if firm_id not in nonready_firm_ids:
            report["firms_not_in_nonready_set"].append(firm_id)

        if not URL_RE.match(seed):
            report["invalid_urls"].append({"row": source_row_id, "url": seed})
            report["safe_to_execute"] = False
            report["hard_fail_reasons"].append(f"invalid_url_row_{source_row_id}")
            continue

        if period not in PERIOD_TO_TIMEPOINTS:
            report["ambiguous_period_mappings"].append({"row": source_row_id, "period": period})
            report["safe_to_execute"] = False
            report["hard_fail_reasons"].append(f"ambiguous_period_row_{source_row_id}:{period}")
            continue

        domain = parse_domain_safe(seed)
        locale = detect_locale(seed)
        ctype = classify_candidate_type(seed, assessment, rescue_status)
        entity_warn = "entity" in (assessment + " " + rescue_status).lower()
        migration_warn = any(
            x in (assessment + " " + rescue_status).lower()
            for x in ("migration", "migrated", "redesign", "domain")
        )
        hist_flag = ctype in {"historical_domain", "migrated_domain"} or "historical" in assessment.lower()
        locale_flag = ctype == "locale_path" or locale in {"de", "de-domain"}

        special = []
        if firm_id == "5":
            special.append("msf_text_volume_threshold")
        if firm_id == "21":
            special.append("freudenberg_sensitivity")
        if firm_id == "22":
            special.append("stihl_sensitivity")
        if firm_id == "24":
            special.append("viessmann_entity_change")
        if firm_id == "30":
            special.append("oetker_entity_change")

        for tp in PERIOD_TO_TIMEPOINTS[period]:
            key = (firm_id, tp, seed)
            if key in seen_keys:
                report["duplicate_candidate_rows"].append(
                    {"row": source_row_id, "dup_of_row": seen_keys[key], "key": list(key)}
                )
            else:
                seen_keys[key] = source_row_id
            normalized.append(
                NormalizedCandidate(
                    source_row_id=source_row_id,
                    firm_id=firm_id,
                    company=company,
                    event_year=event_year,
                    event_cluster=event_cluster,
                    target_period=period,
                    target_timepoint=tp,
                    candidate_seed_url=seed,
                    candidate_domain=domain,
                    locale=locale,
                    candidate_type=ctype,
                    priority=priority,
                    rescue_strength=rescue_status,
                    assessment=assessment,
                    archive_evidence=archive_evidence,
                    special_handling=";".join(special),
                    historical_domain_flag=hist_flag,
                    locale_path_flag=locale_flag,
                    entity_change_warning=entity_warn,
                    migration_warning=migration_warn,
                    original_columns={k: _as_str(row.get(k)) for k in raw.columns},
                )
            )

    report["firms_represented"] = sorted({c.firm_id for c in normalized}, key=lambda x: int(x))
    report["timepoints_represented"] = sorted({c.target_timepoint for c in normalized})
    # Duplicate rows are warnings, not hard fails unless identical conflicting priorities
    if report["unknown_firm_ids"] or report["ambiguous_period_mappings"] or report["invalid_urls"]:
        report["safe_to_execute"] = False
    # Firms in candidate set but already ready: warn only
    if report["firms_not_in_nonready_set"]:
        report["hard_fail_reasons"].append(
            "candidates_include_ready_firms:" + ",".join(sorted(set(report["firms_not_in_nonready_set"])))
        )
        # Christian file targets non-ready only; treat as hard fail if any
        report["safe_to_execute"] = False

    return normalized, report


def parse_domain_safe(url: str) -> str:
    from ffb_webminer.extract.domain import parse_domain

    try:
        return parse_domain(url).registrable_domain
    except Exception:
        host = urlparse(url).hostname or ""
        return host[4:] if host.startswith("www.") else host


def candidates_to_dataframe(candidates: list[NormalizedCandidate]) -> pd.DataFrame:
    return pd.DataFrame([asdict(c) for c in candidates])


def build_alias_map(candidates: list[NormalizedCandidate]) -> dict[tuple[str, str], list[NormalizedCandidate]]:
    """firm_id × timepoint -> candidates sorted by priority."""
    out: dict[tuple[str, str], list[NormalizedCandidate]] = {}
    for c in candidates:
        key = (c.firm_id, c.target_timepoint)
        out.setdefault(key, []).append(c)
    for key in out:
        out[key].sort(key=lambda x: (x.priority, x.source_row_id))
    return out


def write_validation_report(report: dict[str, Any], path: Path, *, candidate_hash: str) -> None:
    safe = report["safe_to_execute"]
    lines = [
        "# Rescue Candidate Input Validation",
        "",
        f"**Candidate file hash (SHA-256):** `{candidate_hash}`",
        f"**Safe to execute:** {'YES' if safe else 'NO — HARD FAIL'}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Rows loaded | {report['rows_loaded']} |",
        f"| Firms represented | {len(report['firms_represented'])} |",
        f"| Timepoints represented | {len(report['timepoints_represented'])} |",
        f"| Duplicate candidate expansions | {len(report['duplicate_candidate_rows'])} |",
        f"| Invalid URLs | {len(report['invalid_urls'])} |",
        f"| Unknown firm IDs | {len(report['unknown_firm_ids'])} |",
        f"| Ambiguous period mappings | {len(report['ambiguous_period_mappings'])} |",
        f"| Missing required fields | {len(report['missing_required_fields'])} |",
        f"| Firms not in non-ready set | {len(set(report['firms_not_in_nonready_set']))} |",
        "",
        f"**Firms:** {', '.join(report['firms_represented'])}",
        "",
        f"**Timepoints:** {', '.join(report['timepoints_represented'])}",
        "",
        "## Hard-fail reasons",
        "",
    ]
    if report["hard_fail_reasons"]:
        lines.extend(f"- `{r}`" for r in report["hard_fail_reasons"])
    else:
        lines.append("- None")
    lines.extend(["", "## Invalid URLs", ""])
    if report["invalid_urls"]:
        for item in report["invalid_urls"]:
            lines.append(f"- row {item['row']}: `{item['url']}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Ambiguous periods", ""])
    if report["ambiguous_period_mappings"]:
        for item in report["ambiguous_period_mappings"]:
            lines.append(f"- row {item['row']}: `{item['period']}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Duplicate expansions (same firm×timepoint×URL)", ""])
    if report["duplicate_candidate_rows"]:
        for item in report["duplicate_candidate_rows"][:50]:
            lines.append(f"- row {item['row']} dup of {item['dup_of_row']}: `{item['key']}`")
    else:
        lines.append("- None")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
