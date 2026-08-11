"""Persistent rescue discovery state — durable snapshot selections (rescue-only).

Successful selected captures survive later transport failures and must not be
downgraded by empty CDX responses caused by Connection refused / timeouts.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from ffb_webminer.rescue.transport import TRANSPORT_FAILURE_RESUMABLE, classify_transport_error

SELECTED_STATUS = "selected"
ATTEMPT_TRANSPORT = "transport_failure_resumable"
ATTEMPT_CDX_EMPTY = "cdx_empty"
ATTEMPT_REJECTED = "rejected"
ATTEMPT_SELECTED = "selected"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_transport_discovery_failure(error: str | None, attempt_status: str | None = None) -> bool:
    if attempt_status == ATTEMPT_TRANSPORT:
        return True
    if not error:
        return False
    cat = classify_transport_error(error)
    return cat.startswith("transport_")


@dataclass
class DiscoverySelectionRecord:
    firm_id: str
    relative_timepoint: str
    candidate_seed_url: str = ""
    source_row_id: str | None = None
    candidate_domain: str | None = None
    target_date: str | None = None
    selected_snapshot_status: str = ""
    selected_capture_timestamp: str | None = None
    selected_capture_url: str | None = None
    temporal_distance_days: float | None = None
    temporal_fit_quality: str | None = None
    selection_reason: str | None = None
    failure_reason: str | None = None
    wayback_replay_url: str | None = None
    http_status: str | None = None
    mime_type: str | None = None
    digest: str | None = None
    homepage_available: bool = False
    relevant_subpages_available: bool = False
    subpage_only_observation: bool = False
    archive_evidence: str | None = None
    historical_domain_flag: bool = False
    locale_path_flag: bool = False
    migration_flag: bool = False
    entity_change_flag: bool = False
    candidate_type: str | None = None
    candidate_priority: int | None = None
    rescue_seed_url: str | None = None
    rescue_source_row_id: str | None = None
    rescue_candidate_type: str | None = None
    rescue_domain: str | None = None
    selected_at: str | None = None
    last_discovery_attempt_at: str | None = None
    latest_discovery_attempt_status: str | None = None
    discovery_error_type: str | None = None
    snapshot_row_json: str | None = None
    config_hash: str | None = None
    candidate_file_hash: str | None = None

    @property
    def has_valid_selection(self) -> bool:
        return (
            self.selected_snapshot_status == SELECTED_STATUS
            and bool(str(self.selected_capture_timestamp or "").strip())
        )


class DiscoveryStateStore:
    """SQLite-backed rescue discovery selections (firm × timepoint authoritative)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=60)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=FULL;")
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rescue_discovery_selection (
                firm_id TEXT NOT NULL,
                relative_timepoint TEXT NOT NULL,
                candidate_seed_url TEXT NOT NULL DEFAULT '',
                source_row_id TEXT,
                candidate_domain TEXT,
                target_date TEXT,
                selected_snapshot_status TEXT NOT NULL DEFAULT '',
                selected_capture_timestamp TEXT,
                selected_capture_url TEXT,
                temporal_distance_days REAL,
                temporal_fit_quality TEXT,
                selection_reason TEXT,
                failure_reason TEXT,
                wayback_replay_url TEXT,
                http_status TEXT,
                mime_type TEXT,
                digest TEXT,
                homepage_available INTEGER NOT NULL DEFAULT 0,
                relevant_subpages_available INTEGER NOT NULL DEFAULT 0,
                subpage_only_observation INTEGER NOT NULL DEFAULT 0,
                archive_evidence TEXT,
                historical_domain_flag INTEGER NOT NULL DEFAULT 0,
                locale_path_flag INTEGER NOT NULL DEFAULT 0,
                migration_flag INTEGER NOT NULL DEFAULT 0,
                entity_change_flag INTEGER NOT NULL DEFAULT 0,
                candidate_type TEXT,
                candidate_priority INTEGER,
                rescue_seed_url TEXT,
                rescue_source_row_id TEXT,
                rescue_candidate_type TEXT,
                rescue_domain TEXT,
                selected_at TEXT,
                last_discovery_attempt_at TEXT,
                latest_discovery_attempt_status TEXT,
                discovery_error_type TEXT,
                snapshot_row_json TEXT,
                config_hash TEXT,
                candidate_file_hash TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (firm_id, relative_timepoint)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rescue_discovery_attempt (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firm_id TEXT NOT NULL,
                relative_timepoint TEXT NOT NULL,
                candidate_seed_url TEXT,
                attempt_at TEXT NOT NULL,
                attempt_status TEXT NOT NULL,
                error_type TEXT,
                error_message TEXT
            )
            """
        )
        self._conn.commit()

    def get(self, firm_id: str, relative_timepoint: str) -> DiscoverySelectionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM rescue_discovery_selection WHERE firm_id=? AND relative_timepoint=?",
            (str(firm_id), str(relative_timepoint)),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def iter_records(self, *, firm_id: str | None = None) -> Iterator[DiscoverySelectionRecord]:
        if firm_id:
            rows = self._conn.execute(
                "SELECT * FROM rescue_discovery_selection WHERE firm_id=? ORDER BY relative_timepoint",
                (str(firm_id),),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM rescue_discovery_selection ORDER BY firm_id, relative_timepoint"
            ).fetchall()
        for row in rows:
            rec = self._row_to_record(row)
            if rec:
                yield rec

    def record_attempt(
        self,
        *,
        firm_id: str,
        relative_timepoint: str,
        candidate_seed_url: str,
        attempt_status: str,
        error: str | None = None,
    ) -> None:
        now = _utc_now()
        err_type = classify_transport_error(error) if error else None
        self._conn.execute(
            """
            INSERT INTO rescue_discovery_attempt
            (firm_id, relative_timepoint, candidate_seed_url, attempt_at, attempt_status, error_type, error_message)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                str(firm_id),
                str(relative_timepoint),
                candidate_seed_url,
                now,
                attempt_status,
                err_type,
                error,
            ),
        )
        existing = self.get(firm_id, relative_timepoint)
        if existing and existing.has_valid_selection:
            # Immutable-success: only update attempt metadata, not selection.
            self._conn.execute(
                """
                UPDATE rescue_discovery_selection SET
                    last_discovery_attempt_at=?,
                    latest_discovery_attempt_status=?,
                    discovery_error_type=?,
                    updated_at=?
                WHERE firm_id=? AND relative_timepoint=?
                """,
                (now, attempt_status, err_type, now, str(firm_id), str(relative_timepoint)),
            )
        else:
            self._upsert_pending_attempt(
                firm_id=firm_id,
                relative_timepoint=relative_timepoint,
                candidate_seed_url=candidate_seed_url,
                attempt_status=attempt_status,
                error_type=err_type,
                now=now,
            )
        self._conn.commit()

    def _upsert_pending_attempt(
        self,
        *,
        firm_id: str,
        relative_timepoint: str,
        candidate_seed_url: str,
        attempt_status: str,
        error_type: str | None,
        now: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO rescue_discovery_selection (
                firm_id, relative_timepoint, candidate_seed_url,
                selected_snapshot_status, last_discovery_attempt_at,
                latest_discovery_attempt_status, discovery_error_type, updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(firm_id, relative_timepoint) DO UPDATE SET
                candidate_seed_url=CASE
                    WHEN excluded.candidate_seed_url != '' THEN excluded.candidate_seed_url
                    ELSE rescue_discovery_selection.candidate_seed_url END,
                last_discovery_attempt_at=excluded.last_discovery_attempt_at,
                latest_discovery_attempt_status=excluded.latest_discovery_attempt_status,
                discovery_error_type=excluded.discovery_error_type,
                updated_at=excluded.updated_at
            """,
            (
                str(firm_id),
                str(relative_timepoint),
                candidate_seed_url,
                attempt_status if attempt_status != ATTEMPT_SELECTED else SELECTED_STATUS,
                now,
                attempt_status,
                error_type,
                now,
            ),
        )

    def persist_selection(
        self,
        snapshot_row: dict[str, Any],
        *,
        alias_meta: dict[str, Any] | None = None,
        config_hash: str | None = None,
        candidate_file_hash: str | None = None,
    ) -> bool:
        """Persist a selected capture. Returns True if stored/updated."""
        firm_id = str(snapshot_row.get("firm_id"))
        tp = str(snapshot_row.get("relative_timepoint"))
        status = str(snapshot_row.get("snapshot_status") or "")
        ts = str(snapshot_row.get("archive_timestamp") or "").strip()
        if status != SELECTED_STATUS or not ts:
            return False

        existing = self.get(firm_id, tp)
        new_dist = _float_or_none(snapshot_row.get("temporal_distance_days"))
        if existing and existing.has_valid_selection:
            old_ts = str(existing.selected_capture_timestamp or "").strip()
            old_dist = existing.temporal_distance_days
            if old_ts and old_ts == ts:
                # Same capture: allow enrichment refresh, but never worsen distance.
                if old_dist is not None and new_dist is not None and new_dist > old_dist:
                    return False
            else:
                # Different capture: only replace with a strictly closer valid selection.
                if old_dist is not None and new_dist is not None and new_dist >= old_dist:
                    return False
                if old_dist is not None and new_dist is None:
                    return False

        meta = alias_meta or {}
        now = _utc_now()
        row_json = json.dumps(snapshot_row, default=str)
        rec = DiscoverySelectionRecord(
            firm_id=firm_id,
            relative_timepoint=tp,
            candidate_seed_url=str(
                meta.get("candidate_seed_url")
                or snapshot_row.get("rescue_seed_url")
                or snapshot_row.get("canonical_original_url")
                or ""
            ),
            source_row_id=_str_or_none(meta.get("source_row_id") or snapshot_row.get("rescue_source_row_id")),
            candidate_domain=_str_or_none(meta.get("selected_domain") or snapshot_row.get("rescue_domain")),
            target_date=_str_or_none(snapshot_row.get("target_date")),
            selected_snapshot_status=SELECTED_STATUS,
            selected_capture_timestamp=ts,
            selected_capture_url=_str_or_none(snapshot_row.get("canonical_original_url")),
            temporal_distance_days=new_dist,
            temporal_fit_quality=_str_or_none(snapshot_row.get("temporal_fit_quality")),
            selection_reason=_str_or_none(snapshot_row.get("selection_reason")),
            failure_reason=_str_or_none(snapshot_row.get("failure_reason")),
            wayback_replay_url=_str_or_none(snapshot_row.get("wayback_replay_url")),
            http_status=_str_or_none(snapshot_row.get("http_status")),
            mime_type=_str_or_none(snapshot_row.get("mime_type")),
            digest=_str_or_none(snapshot_row.get("digest")),
            homepage_available=bool(snapshot_row.get("homepage_available")),
            relevant_subpages_available=bool(snapshot_row.get("relevant_subpages_available")),
            subpage_only_observation=bool(snapshot_row.get("subpage_only_observation")),
            archive_evidence=_str_or_none(meta.get("archive_evidence")),
            historical_domain_flag=bool(meta.get("historical_domain_flag")),
            locale_path_flag=bool(meta.get("locale_path_flag")),
            migration_flag=bool(meta.get("migration_flag")),
            entity_change_flag=bool(meta.get("entity_change_flag")),
            candidate_type=_str_or_none(meta.get("candidate_type") or snapshot_row.get("rescue_candidate_type")),
            candidate_priority=_int_or_none(meta.get("candidate_priority")),
            rescue_seed_url=_str_or_none(snapshot_row.get("rescue_seed_url")),
            rescue_source_row_id=_str_or_none(snapshot_row.get("rescue_source_row_id")),
            rescue_candidate_type=_str_or_none(snapshot_row.get("rescue_candidate_type")),
            rescue_domain=_str_or_none(snapshot_row.get("rescue_domain")),
            selected_at=existing.selected_at if existing and existing.has_valid_selection else now,
            last_discovery_attempt_at=now,
            latest_discovery_attempt_status=ATTEMPT_SELECTED,
            discovery_error_type=None,
            snapshot_row_json=row_json,
            config_hash=config_hash,
            candidate_file_hash=candidate_file_hash,
        )
        self._upsert_record(rec)
        self._conn.commit()
        return True

    def _upsert_record(self, rec: DiscoverySelectionRecord) -> None:
        now = _utc_now()
        self._conn.execute(
            """
            INSERT INTO rescue_discovery_selection (
                firm_id, relative_timepoint, candidate_seed_url, source_row_id, candidate_domain,
                target_date, selected_snapshot_status, selected_capture_timestamp,
                selected_capture_url, temporal_distance_days, temporal_fit_quality,
                selection_reason, failure_reason, wayback_replay_url, http_status, mime_type,
                digest, homepage_available, relevant_subpages_available, subpage_only_observation,
                archive_evidence, historical_domain_flag, locale_path_flag, migration_flag,
                entity_change_flag, candidate_type, candidate_priority, rescue_seed_url,
                rescue_source_row_id, rescue_candidate_type, rescue_domain, selected_at,
                last_discovery_attempt_at, latest_discovery_attempt_status, discovery_error_type,
                snapshot_row_json, config_hash, candidate_file_hash, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(firm_id, relative_timepoint) DO UPDATE SET
                candidate_seed_url=excluded.candidate_seed_url,
                source_row_id=excluded.source_row_id,
                candidate_domain=excluded.candidate_domain,
                target_date=excluded.target_date,
                selected_snapshot_status=excluded.selected_snapshot_status,
                selected_capture_timestamp=excluded.selected_capture_timestamp,
                selected_capture_url=excluded.selected_capture_url,
                temporal_distance_days=excluded.temporal_distance_days,
                temporal_fit_quality=excluded.temporal_fit_quality,
                selection_reason=excluded.selection_reason,
                failure_reason=excluded.failure_reason,
                wayback_replay_url=excluded.wayback_replay_url,
                http_status=excluded.http_status,
                mime_type=excluded.mime_type,
                digest=excluded.digest,
                homepage_available=excluded.homepage_available,
                relevant_subpages_available=excluded.relevant_subpages_available,
                subpage_only_observation=excluded.subpage_only_observation,
                archive_evidence=excluded.archive_evidence,
                historical_domain_flag=excluded.historical_domain_flag,
                locale_path_flag=excluded.locale_path_flag,
                migration_flag=excluded.migration_flag,
                entity_change_flag=excluded.entity_change_flag,
                candidate_type=excluded.candidate_type,
                candidate_priority=excluded.candidate_priority,
                rescue_seed_url=excluded.rescue_seed_url,
                rescue_source_row_id=excluded.rescue_source_row_id,
                rescue_candidate_type=excluded.rescue_candidate_type,
                rescue_domain=excluded.rescue_domain,
                selected_at=excluded.selected_at,
                last_discovery_attempt_at=excluded.last_discovery_attempt_at,
                latest_discovery_attempt_status=excluded.latest_discovery_attempt_status,
                discovery_error_type=excluded.discovery_error_type,
                snapshot_row_json=excluded.snapshot_row_json,
                config_hash=excluded.config_hash,
                candidate_file_hash=excluded.candidate_file_hash,
                updated_at=excluded.updated_at
            """,
            (
                rec.firm_id,
                rec.relative_timepoint,
                rec.candidate_seed_url,
                rec.source_row_id,
                rec.candidate_domain,
                rec.target_date,
                rec.selected_snapshot_status,
                rec.selected_capture_timestamp,
                rec.selected_capture_url,
                rec.temporal_distance_days,
                rec.temporal_fit_quality,
                rec.selection_reason,
                rec.failure_reason,
                rec.wayback_replay_url,
                rec.http_status,
                rec.mime_type,
                rec.digest,
                int(rec.homepage_available),
                int(rec.relevant_subpages_available),
                int(rec.subpage_only_observation),
                rec.archive_evidence,
                int(rec.historical_domain_flag),
                int(rec.locale_path_flag),
                int(rec.migration_flag),
                int(rec.entity_change_flag),
                rec.candidate_type,
                rec.candidate_priority,
                rec.rescue_seed_url,
                rec.rescue_source_row_id,
                rec.rescue_candidate_type,
                rec.rescue_domain,
                rec.selected_at,
                rec.last_discovery_attempt_at,
                rec.latest_discovery_attempt_status,
                rec.discovery_error_type,
                rec.snapshot_row_json,
                rec.config_hash,
                rec.candidate_file_hash,
                now,
            ),
        )

    def counts(self, *, firm_id: str | None = None) -> dict[str, int]:
        params: tuple[Any, ...] = ()
        where = ""
        if firm_id:
            where = "WHERE firm_id=?"
            params = (str(firm_id),)
        rows = self._conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN selected_snapshot_status='selected'
                    AND selected_capture_timestamp IS NOT NULL
                    AND TRIM(selected_capture_timestamp)!='' THEN 1 ELSE 0 END) AS selected,
                SUM(CASE WHEN latest_discovery_attempt_status='transport_failure_resumable' THEN 1 ELSE 0 END) AS retryable,
                COUNT(*) AS total
            FROM rescue_discovery_selection {where}
            """,
            params,
        ).fetchone()
        selected = int(rows["selected"] or 0)
        total = int(rows["total"] or 0)
        retryable = int(rows["retryable"] or 0)
        return {
            "candidate_timepoints": total,
            "selected_rescue_snapshots": selected,
            "unresolved_candidates": max(0, total - selected),
            "retryable_discovery_failures": retryable,
        }

    def snapshot_rows(self, *, firm_ids: list[str] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in self.iter_records():
            if firm_ids and rec.firm_id not in {str(f) for f in firm_ids}:
                continue
            if not rec.has_valid_selection or not rec.snapshot_row_json:
                continue
            try:
                row = json.loads(rec.snapshot_row_json)
            except json.JSONDecodeError:
                continue
            row["rescue_seed_url"] = rec.rescue_seed_url or rec.candidate_seed_url
            row["rescue_source_row_id"] = rec.rescue_source_row_id or rec.source_row_id
            row["rescue_candidate_type"] = rec.rescue_candidate_type or rec.candidate_type
            row["rescue_domain"] = rec.rescue_domain or rec.candidate_domain
            row["snapshot_status"] = SELECTED_STATUS
            row["archive_timestamp"] = rec.selected_capture_timestamp
            out.append(row)
        return out

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DiscoverySelectionRecord | None:
        if row is None:
            return None
        return DiscoverySelectionRecord(
            firm_id=str(row["firm_id"]),
            relative_timepoint=str(row["relative_timepoint"]),
            candidate_seed_url=str(row["candidate_seed_url"] or ""),
            source_row_id=row["source_row_id"],
            candidate_domain=row["candidate_domain"],
            target_date=row["target_date"],
            selected_snapshot_status=str(row["selected_snapshot_status"] or ""),
            selected_capture_timestamp=row["selected_capture_timestamp"],
            selected_capture_url=row["selected_capture_url"],
            temporal_distance_days=row["temporal_distance_days"],
            temporal_fit_quality=row["temporal_fit_quality"],
            selection_reason=row["selection_reason"],
            failure_reason=row["failure_reason"],
            wayback_replay_url=row["wayback_replay_url"],
            http_status=row["http_status"],
            mime_type=row["mime_type"],
            digest=row["digest"],
            homepage_available=bool(row["homepage_available"]),
            relevant_subpages_available=bool(row["relevant_subpages_available"]),
            subpage_only_observation=bool(row["subpage_only_observation"]),
            archive_evidence=row["archive_evidence"],
            historical_domain_flag=bool(row["historical_domain_flag"]),
            locale_path_flag=bool(row["locale_path_flag"]),
            migration_flag=bool(row["migration_flag"]),
            entity_change_flag=bool(row["entity_change_flag"]),
            candidate_type=row["candidate_type"],
            candidate_priority=row["candidate_priority"],
            rescue_seed_url=row["rescue_seed_url"],
            rescue_source_row_id=row["rescue_source_row_id"],
            rescue_candidate_type=row["rescue_candidate_type"],
            rescue_domain=row["rescue_domain"],
            selected_at=row["selected_at"],
            last_discovery_attempt_at=row["last_discovery_attempt_at"],
            latest_discovery_attempt_status=row["latest_discovery_attempt_status"],
            discovery_error_type=row["discovery_error_type"],
            snapshot_row_json=row["snapshot_row_json"],
            config_hash=row["config_hash"],
            candidate_file_hash=row["candidate_file_hash"],
        )


def summarize_discovery_state(store: DiscoveryStateStore, *, firm_id: str | None = None) -> str:
    c = store.counts(firm_id=firm_id)
    label = f"firm {firm_id}" if firm_id else "all firms"
    return (
        f"Rescue discovery state ({label}):\n"
        f"  candidate timepoints tracked: {c['candidate_timepoints']}\n"
        f"  selected rescue snapshots persisted: {c['selected_rescue_snapshots']}\n"
        f"  unresolved candidates: {c['unresolved_candidates']}\n"
        f"  retryable discovery failures: {c['retryable_discovery_failures']}"
    )


def _float_or_none(val: Any) -> float | None:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _str_or_none(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s or None


def _int_or_none(val: Any) -> int | None:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


def count_selected_snapshots(df: pd.DataFrame, firm_ids: set[str] | None = None) -> int:
    if df is None or df.empty:
        return 0
    scoped = df
    if firm_ids:
        scoped = df[df["firm_id"].astype(str).isin({str(f) for f in firm_ids})]
    if scoped.empty:
        return 0
    sel = scoped[scoped.get("snapshot_status", pd.Series(dtype=str)).astype(str) == SELECTED_STATUS]
    return int(
        sel[
            sel["archive_timestamp"].astype(str).str.strip().ne("")
            & sel["archive_timestamp"].astype(str).str.lower().ne("nan")
        ].shape[0]
    )


def merge_authoritative_snapshots(
    new_df: pd.DataFrame,
    store: DiscoveryStateStore,
    *,
    firm_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Overlay persisted selected rows onto a discovery dataframe."""
    persisted = store.snapshot_rows(firm_ids=firm_ids)
    if not persisted:
        return new_df
    if new_df is None or new_df.empty:
        return pd.DataFrame(persisted)

    out = new_df.copy()
    for row in persisted:
        fid = str(row["firm_id"])
        tp = str(row["relative_timepoint"])
        mask = (out["firm_id"].astype(str) == fid) & (out["relative_timepoint"].astype(str) == tp)
        if mask.any():
            for col, val in row.items():
                if col in out.columns:
                    out.loc[mask, col] = val
                else:
                    out[col] = None
                    out.loc[mask, col] = val
        else:
            out = pd.concat([out, pd.DataFrame([row])], ignore_index=True)
    return out


def validate_rescue_snapshots_regression(
    previous: pd.DataFrame | None,
    proposed: pd.DataFrame,
    *,
    firm_ids: set[str],
) -> tuple[bool, str]:
    """Reject writes that drop persisted selected coverage without cause."""
    prev_n = count_selected_snapshots(previous, firm_ids) if previous is not None else 0
    new_n = count_selected_snapshots(proposed, firm_ids)
    if prev_n > 0 and new_n < prev_n:
        return (
            False,
            f"proposed rescue_snapshots would drop selected captures from {prev_n} to {new_n}",
        )
    if prev_n > 0 and new_n == 0:
        return False, "proposed rescue_snapshots is empty but previous had selected captures"
    return True, ""


def atomic_write_rescue_snapshots(
    path: Path,
    df: pd.DataFrame,
    *,
    previous: pd.DataFrame | None = None,
    firm_ids: set[str] | None = None,
) -> None:
    """Atomically write rescue_snapshots.csv with regression guard."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if firm_ids:
        ok, reason = validate_rescue_snapshots_regression(previous, df, firm_ids=firm_ids)
        if not ok:
            raise ValueError(f"refusing rescue_snapshots write: {reason}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def import_snapshots_csv_to_store(
    store: DiscoveryStateStore,
    csv_path: Path,
    *,
    config_hash: str | None = None,
    candidate_file_hash: str | None = None,
) -> int:
    """One-time import of selected rows from rescue_snapshots.csv into SQLite."""
    path = Path(csv_path)
    if not path.exists():
        return 0
    df = pd.read_csv(path, dtype=str)
    if df.empty:
        return 0
    imported = 0
    for _, row in df.iterrows():
        if str(row.get("snapshot_status") or "") != SELECTED_STATUS:
            continue
        ts = str(row.get("archive_timestamp") or "").strip()
        if not ts or ts.lower() == "nan":
            continue
        payload = row.to_dict()
        if store.persist_selection(
            payload,
            alias_meta={
                "candidate_seed_url": row.get("rescue_seed_url") or row.get("canonical_original_url"),
                "source_row_id": row.get("rescue_source_row_id"),
                "selected_domain": row.get("rescue_domain"),
                "candidate_type": row.get("rescue_candidate_type"),
            },
            config_hash=config_hash,
            candidate_file_hash=candidate_file_hash,
        ):
            imported += 1
    return imported


def load_authoritative_rescue_snapshots(
    interim_dir: Path,
    store: DiscoveryStateStore,
    *,
    firm_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Prefer SQLite persisted selections; fall back to CSV."""
    rows = store.snapshot_rows(firm_ids=firm_ids)
    if rows:
        return pd.DataFrame(rows)
    csv_path = Path(interim_dir) / "rescue_snapshots.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path, dtype=str)
        if not df.empty:
            return df
    return pd.DataFrame()
