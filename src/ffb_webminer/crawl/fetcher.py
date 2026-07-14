"""HTTP fetcher with caching for archived pages."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ffb_webminer.archive.wayback_url import build_replay_url, unwrap_wayback_url

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    original_archived_url: str
    wayback_replay_url: str | None
    http_status: int | None
    mime_type: str | None
    content: bytes | None
    content_hash: str | None
    redirect_chain: str | None
    fetch_error: str | None
    raw_html_path: str | None


class PageFetcher:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: int = 45,
        max_bytes: int = 10_485_760,
        throttle_seconds: float = 1.5,
        raw_html_dir: str | Path | None = None,
        store_raw_html: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.throttle_seconds = throttle_seconds
        self.raw_html_dir = Path(raw_html_dir) if raw_html_dir else None
        if self.raw_html_dir:
            self.raw_html_dir.mkdir(parents=True, exist_ok=True)
        self.store_raw_html = store_raw_html
        self._last_request = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.throttle_seconds:
            time.sleep(self.throttle_seconds - elapsed)
        self._last_request = time.monotonic()

    def _cache_path(self, url: str, archive_timestamp: str | None) -> Path | None:
        if not self.raw_html_dir:
            return None
        key = hashlib.sha256(f"{archive_timestamp or ''}|{url}".encode()).hexdigest()
        return self.raw_html_dir / f"{key}.html"

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        reraise=True,
    )
    def fetch(
        self,
        original_url: str,
        archive_timestamp: str | None = None,
        use_cache: bool = True,
    ) -> FetchResult:
        original = unwrap_wayback_url(original_url)
        replay = (
            build_replay_url(original, archive_timestamp)
            if archive_timestamp
            else original
        )
        cache_path = self._cache_path(replay, archive_timestamp)

        if use_cache and cache_path and cache_path.exists():
            content = cache_path.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()
            return FetchResult(
                requested_url=replay,
                final_url=replay,
                original_archived_url=original,
                wayback_replay_url=replay if archive_timestamp else None,
                http_status=200,
                mime_type="text/html",
                content=content,
                content_hash=content_hash,
                redirect_chain=None,
                fetch_error=None,
                raw_html_path=str(cache_path),
            )

        self._throttle()
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                resp = client.get(replay)
                content = resp.content[: self.max_bytes]
                mime = resp.headers.get("content-type", "").split(";")[0].strip()
                content_hash = hashlib.sha256(content).hexdigest() if content else None
                raw_path = None
                if self.store_raw_html and cache_path and content:
                    cache_path.write_bytes(content)
                    raw_path = str(cache_path)
                return FetchResult(
                    requested_url=replay,
                    final_url=str(resp.url),
                    original_archived_url=original,
                    wayback_replay_url=replay if archive_timestamp else None,
                    http_status=resp.status_code,
                    mime_type=mime,
                    content=content,
                    content_hash=content_hash,
                    redirect_chain=None,
                    fetch_error=None,
                    raw_html_path=raw_path,
                )
        except Exception as exc:
            logger.warning("Fetch failed %s: %s", replay, exc)
            return FetchResult(
                requested_url=replay,
                final_url=replay,
                original_archived_url=original,
                wayback_replay_url=replay if archive_timestamp else None,
                http_status=None,
                mime_type=None,
                content=None,
                content_hash=None,
                redirect_chain=None,
                fetch_error=str(exc),
                raw_html_path=None,
            )
