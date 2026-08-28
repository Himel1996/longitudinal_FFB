"""Atomic page-level cache + SQLite resume state for Phase B (rescue-only)."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from ffb_webminer.archive.wayback_url import build_replay_url, unwrap_wayback_url
from ffb_webminer.rescue.timestamps import normalize_archive_timestamp

STATUS_PENDING = "PENDING"
STATUS_FETCHING = "FETCHING"
STATUS_FETCHED = "FETCHED"
STATUS_FETCH_FAILED_RESUMABLE = "FETCH_FAILED_RESUMABLE"
STATUS_EXTRACTED = "EXTRACTED"
STATUS_PERMANENTLY_REJECTED = "PERMANENTLY_REJECTED"

VALID_REUSE_STATUSES = frozenset({STATUS_FETCHED, STATUS_EXTRACTED})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def page_cache_key(
    original_url: str,
    archive_timestamp: str,
    *,
    modifier: str = "id_",
) -> str:
    """Deterministic cache identity: original URL × archive timestamp × modifier."""
    original = unwrap_wayback_url(original_url)
    ts = normalize_archive_timestamp(archive_timestamp)
    replay = build_replay_url(original, ts, modifier=modifier)
    material = f"{ts}|{modifier}|{original}|{replay}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class PageFetchRecord:
    page_cache_key: str
    firm_id: str | None = None
    relative_timepoint: str | None = None
    original_url: str = ""
    replay_url: str = ""
    archive_timestamp: str = ""
    fetch_status: str = STATUS_PENDING
    attempt_count: int = 0
    first_attempt_at: str | None = None
    last_attempt_at: str | None = None
    completed_at: str | None = None
    content_hash: str | None = None
    bytes_received: int = 0
    http_status: int | None = None
    mime_type: str | None = None
    transport_error_type: str | None = None
    cache_path: str | None = None
    cache_valid: bool = False
    extraction_pending: bool = True
    extraction_completed: bool = False


class PageFetchStateStore:
    """SQLite-backed page fetch state for crash-safe resume."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_conn()
        self._ensure_schema()

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            try:
                self._conn.execute("SELECT 1")
                return self._conn
            except sqlite3.ProgrammingError:
                self._conn = None
        self._conn = sqlite3.connect(str(self.db_path), timeout=60)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=FULL;")
        return self._conn

    def close(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        except sqlite3.Error:
            pass
        self._conn = None

    def _ensure_schema(self) -> None:
        self._ensure_conn().execute(
            """
            CREATE TABLE IF NOT EXISTS page_fetch_state (
                page_cache_key TEXT PRIMARY KEY,
                firm_id TEXT,
                relative_timepoint TEXT,
                original_url TEXT NOT NULL,
                replay_url TEXT NOT NULL,
                archive_timestamp TEXT NOT NULL,
                fetch_status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                first_attempt_at TEXT,
                last_attempt_at TEXT,
                completed_at TEXT,
                content_hash TEXT,
                bytes_received INTEGER NOT NULL DEFAULT 0,
                http_status INTEGER,
                mime_type TEXT,
                transport_error_type TEXT,
                cache_path TEXT,
                cache_valid INTEGER NOT NULL DEFAULT 0,
                extraction_pending INTEGER NOT NULL DEFAULT 1,
                extraction_completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._ensure_conn().commit()

    def get(self, key: str) -> PageFetchRecord | None:
        row = self._ensure_conn().execute(
            "SELECT * FROM page_fetch_state WHERE page_cache_key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return PageFetchRecord(
            page_cache_key=row["page_cache_key"],
            firm_id=row["firm_id"],
            relative_timepoint=row["relative_timepoint"],
            original_url=row["original_url"],
            replay_url=row["replay_url"],
            archive_timestamp=row["archive_timestamp"],
            fetch_status=row["fetch_status"],
            attempt_count=int(row["attempt_count"] or 0),
            first_attempt_at=row["first_attempt_at"],
            last_attempt_at=row["last_attempt_at"],
            completed_at=row["completed_at"],
            content_hash=row["content_hash"],
            bytes_received=int(row["bytes_received"] or 0),
            http_status=row["http_status"],
            mime_type=row["mime_type"],
            transport_error_type=row["transport_error_type"],
            cache_path=row["cache_path"],
            cache_valid=bool(row["cache_valid"]),
            extraction_pending=bool(row["extraction_pending"]),
            extraction_completed=bool(row["extraction_completed"]),
        )

    def upsert(self, record: PageFetchRecord) -> None:
        self._ensure_conn().execute(
            """
            INSERT INTO page_fetch_state (
                page_cache_key, firm_id, relative_timepoint, original_url, replay_url,
                archive_timestamp, fetch_status, attempt_count, first_attempt_at,
                last_attempt_at, completed_at, content_hash, bytes_received, http_status,
                mime_type, transport_error_type, cache_path, cache_valid,
                extraction_pending, extraction_completed, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(page_cache_key) DO UPDATE SET
                firm_id=excluded.firm_id,
                relative_timepoint=excluded.relative_timepoint,
                original_url=excluded.original_url,
                replay_url=excluded.replay_url,
                archive_timestamp=excluded.archive_timestamp,
                fetch_status=excluded.fetch_status,
                attempt_count=excluded.attempt_count,
                first_attempt_at=excluded.first_attempt_at,
                last_attempt_at=excluded.last_attempt_at,
                completed_at=excluded.completed_at,
                content_hash=excluded.content_hash,
                bytes_received=excluded.bytes_received,
                http_status=excluded.http_status,
                mime_type=excluded.mime_type,
                transport_error_type=excluded.transport_error_type,
                cache_path=excluded.cache_path,
                cache_valid=excluded.cache_valid,
                extraction_pending=excluded.extraction_pending,
                extraction_completed=excluded.extraction_completed,
                updated_at=excluded.updated_at
            """,
            (
                record.page_cache_key,
                record.firm_id,
                record.relative_timepoint,
                record.original_url,
                record.replay_url,
                record.archive_timestamp,
                record.fetch_status,
                record.attempt_count,
                record.first_attempt_at,
                record.last_attempt_at,
                record.completed_at,
                record.content_hash,
                record.bytes_received,
                record.http_status,
                record.mime_type,
                record.transport_error_type,
                record.cache_path,
                1 if record.cache_valid else 0,
                1 if record.extraction_pending else 0,
                1 if record.extraction_completed else 0,
                _utc_now(),
            ),
        )
        self._ensure_conn().commit()

    def counts(self, *, firm_id: str | None = None) -> dict[str, int]:
        sql = "SELECT fetch_status, COUNT(*) AS n FROM page_fetch_state"
        params: tuple[Any, ...] = ()
        if firm_id is not None:
            sql += " WHERE firm_id = ?"
            params = (str(firm_id),)
        sql += " GROUP BY fetch_status"
        rows = self._ensure_conn().execute(sql, params).fetchall()
        out = {
            "completed_pages": 0,
            "cached_valid_pages": 0,
            "resumable_failures": 0,
            "pending_pages": 0,
            "fetching_pages": 0,
            "extracted_pages": 0,
            "permanently_rejected": 0,
            "total": 0,
        }
        for row in rows:
            status = row["fetch_status"]
            n = int(row["n"])
            out["total"] += n
            if status in VALID_REUSE_STATUSES:
                out["completed_pages"] += n
                out["cached_valid_pages"] += n
            if status == STATUS_EXTRACTED:
                out["extracted_pages"] += n
            if status == STATUS_FETCH_FAILED_RESUMABLE:
                out["resumable_failures"] += n
            if status == STATUS_PENDING:
                out["pending_pages"] += n
            if status == STATUS_FETCHING:
                out["fetching_pages"] += n
            if status == STATUS_PERMANENTLY_REJECTED:
                out["permanently_rejected"] += n
        return out

    def iter_records(self, *, firm_id: str | None = None) -> Iterator[PageFetchRecord]:
        sql = "SELECT page_cache_key FROM page_fetch_state"
        params: tuple[Any, ...] = ()
        if firm_id is not None:
            sql += " WHERE firm_id = ?"
            params = (str(firm_id),)
        for row in self._ensure_conn().execute(sql, params):
            rec = self.get(row["page_cache_key"])
            if rec is not None:
                yield rec


class AtomicPageCache:
    """Filesystem HTML cache with atomic rename + metadata sidecar."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.cache_dir / ".tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def html_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.html"

    def meta_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.meta.json"

    def write_atomic(
        self,
        key: str,
        content: bytes,
        *,
        metadata: dict[str, Any],
    ) -> tuple[Path, str]:
        if not content:
            raise ValueError("refusing to cache empty response")
        content_hash = hashlib.sha256(content).hexdigest()
        final_html = self.html_path(key)
        final_meta = self.meta_path(key)
        tmp_html = self.tmp_dir / f"{key}.{os.getpid()}.{time.time_ns()}.html.tmp"
        tmp_meta = self.tmp_dir / f"{key}.{os.getpid()}.{time.time_ns()}.meta.tmp"
        try:
            with open(tmp_html, "wb") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            meta = {
                **metadata,
                "content_hash": content_hash,
                "bytes_received": len(content),
                "cache_valid": True,
            }
            with open(tmp_meta, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_html, final_html)
            os.replace(tmp_meta, final_meta)
        finally:
            for p in (tmp_html, tmp_meta):
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
        return final_html, content_hash

    def read_valid(self, key: str, *, expected_hash: str | None = None) -> tuple[bytes, dict[str, Any]] | None:
        html_path = self.html_path(key)
        meta_path = self.meta_path(key)
        if not html_path.exists():
            return None
        content = html_path.read_bytes()
        if not content:
            return None
        meta: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
        digest = hashlib.sha256(content).hexdigest()
        if expected_hash and digest != expected_hash:
            return None
        if meta.get("content_hash") and meta["content_hash"] != digest:
            return None
        if meta.get("bytes_received") not in (None, len(content)):
            return None
        if meta and not meta.get("cache_valid", True):
            return None
        meta.setdefault("content_hash", digest)
        meta.setdefault("bytes_received", len(content))
        return content, meta

    def discard_temps_for_key(self, key: str) -> int:
        n = 0
        for p in self.tmp_dir.glob(f"{key}.*"):
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
        return n


def summarize_resume_state(store: PageFetchStateStore, *, firm_id: str | None = None) -> str:
    c = store.counts(firm_id=firm_id)
    return (
        "Rescue resume state:\n"
        f"  completed pages: {c['completed_pages']}\n"
        f"  cached valid pages: {c['cached_valid_pages']}\n"
        f"  resumable failures: {c['resumable_failures']}\n"
        f"  pending pages: {c['pending_pages']}\n"
        f"  fetching (interrupted): {c['fetching_pages']}"
    )
