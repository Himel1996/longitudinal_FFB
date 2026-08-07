"""Rescue-only resumable Wayback fetcher (duck-typed like PageFetcher).

Does not modify core PageFetcher. Uses atomic cache + SQLite state + circuit breaker.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from ffb_webminer.archive.wayback_url import build_replay_url, unwrap_wayback_url
from ffb_webminer.crawl.fetcher import FetchResult
from ffb_webminer.rescue.page_cache import (
    STATUS_EXTRACTED,
    STATUS_FETCHED,
    STATUS_FETCHING,
    STATUS_FETCH_FAILED_RESUMABLE,
    STATUS_PENDING,
    AtomicPageCache,
    PageFetchRecord,
    PageFetchStateStore,
    page_cache_key,
    summarize_resume_state,
)
from ffb_webminer.rescue.timestamps import normalize_archive_timestamp
from ffb_webminer.rescue.transport import (
    CircuitBreaker,
    TransportPausedError,
    TransportPolicy,
    classify_transport_error,
    is_circuit_failure,
    run_health_probes,
)

logger = logging.getLogger(__name__)


class ResumableRescueFetcher:
    """PageFetcher-compatible fetcher with resume/cache/circuit-breaker."""

    def __init__(
        self,
        *,
        user_agent: str,
        cache_dir: Path,
        state_db: Path,
        policy: TransportPolicy | None = None,
        firm_id: str | None = None,
        relative_timepoint: str | None = None,
        resume_command: str = "",
        sleep_fn=time.sleep,
    ) -> None:
        self.user_agent = user_agent
        self.policy = policy or TransportPolicy()
        self.timeout_seconds = self.policy.timeout_seconds
        self.retries = max(1, int(self.policy.max_attempts_per_request))
        self.throttle_seconds = float(self.policy.inter_request_delay_seconds)
        self.raw_html_dir = Path(cache_dir)
        self.store_raw_html = True
        self.firm_id = firm_id
        self.relative_timepoint = relative_timepoint
        self.resume_command = resume_command
        self._sleep = sleep_fn
        self.cache = AtomicPageCache(Path(cache_dir))
        self.store = PageFetchStateStore(Path(state_db))
        self.circuit = CircuitBreaker(config=self.policy.circuit_breaker)
        self._client: httpx.Client | None = None
        self._last_request = 0.0
        self.stats: dict[str, int] = {
            "cache_hits": 0,
            "network_fetches": 0,
            "resumable_failures": 0,
            "successes": 0,
        }

    # --- PageFetcher-compatible attributes used elsewhere ---
    @property
    def max_bytes(self) -> int:
        return 10_485_760

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self.store.close()

    def print_resume_summary(self) -> None:
        print(summarize_resume_state(self.store, firm_id=self.firm_id))
        print(f"  cache directory: {self.cache.cache_dir}")
        print(f"  state database: {self.store.db_path}")

    def _client_get(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
                http2=False,
                limits=httpx.Limits(max_keepalive_connections=0, max_connections=1),
            )
        return self._client

    def _reset_client(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        need = self.throttle_seconds - elapsed
        if need > 0:
            self._sleep(need)
        if self.policy.jitter_seconds:
            import random

            self._sleep(random.uniform(0.0, float(self.policy.jitter_seconds)))
        self._last_request = time.monotonic()

    def _handle_open_circuit(self) -> None:
        while self.circuit.should_block_requests():
            wait = self.circuit.time_until_half_open()
            counts = self.store.counts(firm_id=self.firm_id)
            print(
                "WAYBACK CIRCUIT OPEN\n"
                f"Reason: {self.circuit.last_reason}\n"
                f"Cached pages preserved: {counts['cached_valid_pages']}\n"
                f"Pending/resumable: {counts['pending_pages'] + counts['resumable_failures']}\n"
                f"Cooldown: {int(wait)} seconds"
            )
            if wait > 0:
                self._sleep(wait)
            if not self.circuit.enter_half_open_if_ready():
                continue
            probe = self._run_default_probes()
            if probe["ok"]:
                print("WAYBACK CIRCUIT CLOSED after successful health probes")
                self.circuit.close_after_probes()
                return
            self.circuit.reopen_after_failed_probes()
            if self.circuit.exhausted_cycles():
                raise TransportPausedError(
                    "RESCUE_PAUSED_TRANSPORT_UNSTABLE: max circuit cycles exceeded",
                    resume_command=self.resume_command,
                )

    def _run_default_probes(self) -> dict[str, Any]:
        # Lightweight probes using same client stack; URLs are Wayback operations.
        def cdx_probe() -> bool:
            try:
                client = self._client_get()
                r = client.get(
                    "https://web.archive.org/cdx/search/cdx",
                    params={
                        "url": "https://www.bbraun.de/",
                        "output": "json",
                        "limit": "1",
                        "fl": "timestamp,original,statuscode",
                    },
                )
                return r.status_code == 200 and bool(r.content)
            except Exception:
                self._reset_client()
                return False

        def replay_probe() -> bool:
            try:
                client = self._client_get()
                # Stable known B. Braun capture used in prior smoke discovery windows
                url = "https://web.archive.org/web/20190704175027id_/https://www.bbraun.com/"
                r = client.get(url)
                return 200 <= r.status_code < 400 and len(r.content) > 100
            except Exception:
                self._reset_client()
                return False

        return run_health_probes(
            probes=[cdx_probe, replay_probe, replay_probe],
            required_successes=self.policy.circuit_breaker.health_probe_successes_required,
        )

    def fetch(
        self,
        original_url: str,
        archive_timestamp: str | None = None,
        use_cache: bool = True,
    ) -> FetchResult:
        if not archive_timestamp:
            # Live URL path (rare in rescue); fall through without cache keying by timestamp
            return self._fetch_network_uncached(original_url)

        ts = normalize_archive_timestamp(archive_timestamp)
        original = unwrap_wayback_url(original_url)
        replay = build_replay_url(original, ts)
        key = page_cache_key(original, ts)
        self.cache.discard_temps_for_key(key)

        existing = self.store.get(key)
        if use_cache and existing and existing.fetch_status in {STATUS_FETCHED, STATUS_EXTRACTED} and existing.cache_valid:
            cached = self.cache.read_valid(key, expected_hash=existing.content_hash)
            if cached is not None:
                content, _meta = cached
                self.stats["cache_hits"] += 1
                return FetchResult(
                    requested_url=replay,
                    final_url=replay,
                    original_archived_url=original,
                    wayback_replay_url=replay,
                    http_status=existing.http_status or 200,
                    mime_type=existing.mime_type or "text/html",
                    content=content,
                    content_hash=existing.content_hash,
                    redirect_chain=None,
                    fetch_error=None,
                    raw_html_path=str(self.cache.html_path(key)),
                )

        # Also reuse orphan HTML files from prior smoke test (legacy PageFetcher naming)
        # only when sidecar/state validates; otherwise require network.
        if use_cache:
            cached = self.cache.read_valid(key, expected_hash=existing.content_hash if existing else None)
            if cached is not None:
                content, meta = cached
                rec = existing or PageFetchRecord(
                    page_cache_key=key,
                    firm_id=self.firm_id,
                    relative_timepoint=self.relative_timepoint,
                    original_url=original,
                    replay_url=replay,
                    archive_timestamp=ts,
                )
                rec.fetch_status = STATUS_FETCHED
                rec.cache_valid = True
                rec.content_hash = meta.get("content_hash")
                rec.bytes_received = int(meta.get("bytes_received") or len(content))
                rec.cache_path = str(self.cache.html_path(key))
                rec.http_status = int(meta.get("http_status") or 200)
                rec.mime_type = str(meta.get("mime_type") or "text/html")
                self.store.upsert(rec)
                self.stats["cache_hits"] += 1
                return FetchResult(
                    requested_url=replay,
                    final_url=replay,
                    original_archived_url=original,
                    wayback_replay_url=replay,
                    http_status=rec.http_status,
                    mime_type=rec.mime_type,
                    content=content,
                    content_hash=rec.content_hash,
                    redirect_chain=None,
                    fetch_error=None,
                    raw_html_path=rec.cache_path,
                )

        # Attempt to import legacy core cache file (sha256 of timestamp|replay) if present
        if use_cache:
            import hashlib

            legacy_key = hashlib.sha256(f"{ts}|{replay}".encode()).hexdigest()
            legacy_path = self.cache.cache_dir / f"{legacy_key}.html"
            if legacy_path.exists():
                content = legacy_path.read_bytes()
                if content:
                    path, digest = self.cache.write_atomic(
                        key,
                        content,
                        metadata={
                            "original_url": original,
                            "replay_url": replay,
                            "archive_timestamp": ts,
                            "http_status": 200,
                            "mime_type": "text/html",
                            "imported_from_legacy_cache": legacy_key,
                        },
                    )
                    rec = PageFetchRecord(
                        page_cache_key=key,
                        firm_id=self.firm_id,
                        relative_timepoint=self.relative_timepoint,
                        original_url=original,
                        replay_url=replay,
                        archive_timestamp=ts,
                        fetch_status=STATUS_FETCHED,
                        content_hash=digest,
                        bytes_received=len(content),
                        http_status=200,
                        mime_type="text/html",
                        cache_path=str(path),
                        cache_valid=True,
                        completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    )
                    self.store.upsert(rec)
                    self.stats["cache_hits"] += 1
                    return FetchResult(
                        requested_url=replay,
                        final_url=replay,
                        original_archived_url=original,
                        wayback_replay_url=replay,
                        http_status=200,
                        mime_type="text/html",
                        content=content,
                        content_hash=digest,
                        redirect_chain=None,
                        fetch_error=None,
                        raw_html_path=str(path),
                    )

        self._handle_open_circuit()

        rec = existing or PageFetchRecord(
            page_cache_key=key,
            firm_id=self.firm_id,
            relative_timepoint=self.relative_timepoint,
            original_url=original,
            replay_url=replay,
            archive_timestamp=ts,
            fetch_status=STATUS_PENDING,
        )
        if rec.first_attempt_at is None:
            rec.first_attempt_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        last_exc: Exception | None = None
        last_category = None
        for attempt in range(self.retries):
            self._handle_open_circuit()
            rec.fetch_status = STATUS_FETCHING
            rec.attempt_count += 1
            rec.last_attempt_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.store.upsert(rec)
            if attempt:
                self._sleep(min(self.policy.backoff_base_seconds ** attempt, 30))
            try:
                result = self._fetch_once(replay, original, ts, key, rec)
                self.circuit.record_success()
                self.stats["network_fetches"] += 1
                self.stats["successes"] += 1
                return result
            except TransportPausedError:
                raise
            except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
                last_exc = exc
                last_category = classify_transport_error(str(exc))
                logger.warning(
                    "Rescue fetch attempt %s/%s failed %s [%s]: %s",
                    attempt + 1,
                    self.retries,
                    replay,
                    last_category,
                    exc,
                )
                self._reset_client()
                if is_circuit_failure(last_category):
                    self.circuit.record_failure(url=replay, error=str(exc), category=last_category)
                if self.policy.post_failure_pause_seconds:
                    self._sleep(self.policy.post_failure_pause_seconds)
                if self.circuit.should_block_requests():
                    rec.fetch_status = STATUS_FETCH_FAILED_RESUMABLE
                    rec.transport_error_type = last_category
                    self.store.upsert(rec)
                    self.stats["resumable_failures"] += 1
                    self._handle_open_circuit()

        rec.fetch_status = STATUS_FETCH_FAILED_RESUMABLE
        rec.transport_error_type = last_category or classify_transport_error(str(last_exc) if last_exc else None)
        self.store.upsert(rec)
        self.stats["resumable_failures"] += 1
        self.stats["network_fetches"] += 1
        return FetchResult(
            requested_url=replay,
            final_url=replay,
            original_archived_url=original,
            wayback_replay_url=replay,
            http_status=None,
            mime_type=None,
            content=None,
            content_hash=None,
            redirect_chain=None,
            fetch_error=str(last_exc) if last_exc else "fetch_failed",
            raw_html_path=None,
        )

    def _fetch_once(
        self,
        replay: str,
        original: str,
        archive_timestamp: str,
        key: str,
        rec: PageFetchRecord,
    ) -> FetchResult:
        self._throttle()
        client = self._client_get()
        resp = client.get(replay)
        # Retry-After on 429
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            if self.policy.respect_retry_after and ra:
                try:
                    self._sleep(min(float(ra), 600))
                except ValueError:
                    self._sleep(60)
            cat = classify_transport_error(None, 429)
            self.circuit.record_failure(url=replay, error="HTTP 429", category=cat)
            raise httpx.HTTPStatusError("HTTP 429", request=resp.request, response=resp)
        if resp.status_code >= 500:
            cat = classify_transport_error(None, resp.status_code)
            self.circuit.record_failure(url=replay, error=f"HTTP {resp.status_code}", category=cat)
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )
        content = resp.content[: self.max_bytes]
        mime = resp.headers.get("content-type", "").split(";")[0].strip() or "text/html"
        if not content:
            raise OSError("empty response body")
        path, digest = self.cache.write_atomic(
            key,
            content,
            metadata={
                "original_url": original,
                "replay_url": replay,
                "archive_timestamp": archive_timestamp,
                "http_status": resp.status_code,
                "mime_type": mime,
            },
        )
        rec.fetch_status = STATUS_FETCHED
        rec.cache_valid = True
        rec.content_hash = digest
        rec.bytes_received = len(content)
        rec.http_status = resp.status_code
        rec.mime_type = mime
        rec.cache_path = str(path)
        rec.transport_error_type = None
        rec.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.store.upsert(rec)
        return FetchResult(
            requested_url=replay,
            final_url=str(resp.url),
            original_archived_url=original,
            wayback_replay_url=replay,
            http_status=resp.status_code,
            mime_type=mime,
            content=content,
            content_hash=digest,
            redirect_chain=None,
            fetch_error=None,
            raw_html_path=str(path),
        )

    def _fetch_network_uncached(self, url: str) -> FetchResult:
        self._throttle()
        try:
            resp = self._client_get().get(url)
            content = resp.content[: self.max_bytes]
            return FetchResult(
                requested_url=url,
                final_url=str(resp.url),
                original_archived_url=unwrap_wayback_url(url),
                wayback_replay_url=None,
                http_status=resp.status_code,
                mime_type=resp.headers.get("content-type", "").split(";")[0].strip(),
                content=content,
                content_hash=None,
                redirect_chain=None,
                fetch_error=None,
                raw_html_path=None,
            )
        except Exception as exc:
            self._reset_client()
            return FetchResult(
                requested_url=url,
                final_url=url,
                original_archived_url=unwrap_wayback_url(url),
                wayback_replay_url=None,
                http_status=None,
                mime_type=None,
                content=None,
                content_hash=None,
                redirect_chain=None,
                fetch_error=str(exc),
                raw_html_path=None,
            )
