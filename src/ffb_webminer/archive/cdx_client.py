"""Internet Archive CDX API client with caching and retries."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

CDX_FIELDS = [
    "urlkey",
    "timestamp",
    "original",
    "mimetype",
    "statuscode",
    "digest",
    "length",
    "redirect",
]


class CDXClient:
    def __init__(
        self,
        api_url: str,
        cache_dir: str | Path,
        user_agent: str,
        throttle_seconds: float = 1.5,
        retry_max: int = 5,
        retry_backoff_base: float = 2.0,
    ) -> None:
        self.api_url = api_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.throttle_seconds = throttle_seconds
        self.retry_max = retry_max
        self.retry_backoff_base = retry_backoff_base
        self._last_request = 0.0

    def _cache_key(self, url: str, filters: dict[str, str]) -> str:
        payload = json.dumps({"url": url, "filters": filters}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.throttle_seconds:
            time.sleep(self.throttle_seconds - elapsed)
        self._last_request = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=60),
        reraise=True,
    )
    def _fetch(self, params: dict[str, str]) -> list[list[str]]:
        return self._fetch_params(list(params.items()))

    def _fetch_params(self, params: list[tuple[str, str]]) -> list[list[str]]:
        self._throttle()
        with httpx.Client(timeout=60.0, headers={"User-Agent": self.user_agent}) as client:
            resp = client.get(self.api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        if not data:
            return []
        # First row is header when output=json
        if data and data[0] == CDX_FIELDS:
            return data[1:]
        return data

    def search(
        self,
        url: str,
        status_codes: list[str] | None = None,
        mimetypes: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, str]]:
        filters: dict[str, str] = {}
        cache_key = self._cache_key(url, {"status": status_codes or [], "mime": mimetypes or []})
        cache_path = self._cache_path(cache_key)

        if use_cache and cache_path.exists():
            logger.debug("CDX cache hit: %s", url)
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            return [self._row_to_dict(r) for r in raw]

        params: list[tuple[str, str]] = [
            ("url", url),
            ("output", "json"),
            ("fl", ",".join(CDX_FIELDS)),
            ("collapse", "digest"),
        ]
        if status_codes:
            for code in status_codes:
                params.append(("filter", f"statuscode:{code}"))
        if mimetypes:
            for mime in mimetypes:
                params.append(("filter", f"mimetype:{mime}"))

        logger.info("CDX query: %s", url)
        rows = self._fetch_params(params)
        if use_cache:
            cache_path.write_text(json.dumps(rows), encoding="utf-8")
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: list[str]) -> dict[str, str]:
        return {field: row[i] if i < len(row) else "" for i, field in enumerate(CDX_FIELDS)}

    def search_url_variants(
        self,
        domain: str,
        website: str,
        variants: list[str],
        status_codes: list[str],
        mimetypes: list[str],
    ) -> tuple[list[dict[str, str]], list[str]]:
        """Search multiple URL patterns; return merged captures and attempt log."""
        attempts: list[str] = []
        seen: set[str] = set()
        merged: list[dict[str, str]] = []

        seeds = {website.rstrip("/") + "/", f"https://www.{domain}/", f"https://{domain}/"}
        for tmpl in variants:
            seeds.add(tmpl.format(domain=domain))

        for seed in sorted(seeds):
            attempts.append(seed)
            try:
                rows = self.search(seed, status_codes=status_codes, mimetypes=mimetypes)
            except Exception as exc:
                logger.warning("CDX failed for %s: %s", seed, exc)
                continue
            for row in rows:
                key = f"{row.get('timestamp','')}|{row.get('original','')}"
                if key not in seen:
                    seen.add(key)
                    merged.append(row)
        return merged, attempts
