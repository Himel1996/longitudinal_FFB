"""Operational transport classification for Phase B (orchestration only).

Does not change archival selection methodology or PageFetcher TLS settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TRANSPORT_FAILURE_RESUMABLE = "transport_failure_resumable"

_TLS_MARKERS = (
    "ssl",
    "tls",
    "unexpected_eof",
    "eof occurred",
    "ssl_error",
    "certificate",
    "handshake",
)
_RATE_MARKERS = ("429", "too many requests", "retry-after")
_CONN_MARKERS = (
    "connection refused",
    "connection reset",
    "timed out",
    "timeout",
    "network is unreachable",
    "temporary failure",
    "name or service not known",
)


def classify_fetch_error(error: str | None, http_status: int | None = None) -> str | None:
    """Return TRANSPORT_FAILURE_RESUMABLE when the failure is transport-side.

    Never maps transport issues to archive_unavailable / snapshot_unavailable.
    """
    if http_status == 429:
        return TRANSPORT_FAILURE_RESUMABLE
    err = (error or "").lower()
    if not err and http_status is not None and http_status >= 500:
        return TRANSPORT_FAILURE_RESUMABLE
    if any(m in err for m in _TLS_MARKERS + _RATE_MARKERS + _CONN_MARKERS):
        return TRANSPORT_FAILURE_RESUMABLE
    return None


@dataclass
class CircuitBreaker:
    """Stop after repeated resumable transport failures in a cluster."""

    failure_threshold: int = 8
    consecutive_failures: int = 0
    tripped: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self, *, url: str, error: str) -> None:
        self.consecutive_failures += 1
        self.events.append({"url": url, "error": error, "class": TRANSPORT_FAILURE_RESUMABLE})
        if self.consecutive_failures >= self.failure_threshold:
            self.tripped = True

    def assert_not_tripped(self) -> None:
        if self.tripped:
            raise RuntimeError(
                f"transport circuit breaker tripped after {self.consecutive_failures} "
                f"consecutive {TRANSPORT_FAILURE_RESUMABLE} events; resume later"
            )


DEFAULT_TRANSPORT_POLICY = {
    "concurrency": 1,
    "throttle_seconds": 2.5,
    "timeout_seconds": 45,
    "retries": 5,
    "backoff_base_seconds": 2.0,
    "jitter_seconds": 0.5,
    "respect_retry_after": True,
    "circuit_breaker_threshold": 8,
    "classify_transport_failures": True,
}
