"""Operational transport controls for Phase B (orchestration only).

Does not change archival selection methodology or weaken TLS verification.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

TRANSPORT_FAILURE_RESUMABLE = "transport_failure_resumable"
RESCUE_PAUSED_TRANSPORT_UNSTABLE = "RESCUE_PAUSED_TRANSPORT_UNSTABLE"
PREFLIGHT_FAILED_TRANSPORT = "PREFLIGHT_FAILED_TRANSPORT"

# Detailed taxonomy (all transport_* remain resumable)
ERROR_TLS_EOF = "transport_tls_eof"
ERROR_CONNECTION_REFUSED = "transport_connection_refused"
ERROR_CONNECTION_RESET = "transport_connection_reset"
ERROR_CONNECT_TIMEOUT = "transport_connect_timeout"
ERROR_READ_TIMEOUT = "transport_read_timeout"
ERROR_HTTP_429 = "transport_http_429"
ERROR_HTTP_5XX = "transport_http_5xx"
ERROR_ARCHIVE_NOT_FOUND = "archive_not_found"
ERROR_ARCHIVE_INVALID = "archive_invalid_capture"
ERROR_PAGE_CONTENT = "page_content_error"
ERROR_OTHER = "other"

TRANSPORT_ERROR_TYPES = frozenset(
    {
        ERROR_TLS_EOF,
        ERROR_CONNECTION_REFUSED,
        ERROR_CONNECTION_RESET,
        ERROR_CONNECT_TIMEOUT,
        ERROR_READ_TIMEOUT,
        ERROR_HTTP_429,
        ERROR_HTTP_5XX,
        TRANSPORT_FAILURE_RESUMABLE,
    }
)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


def classify_transport_error(
    error: str | None = None,
    http_status: int | None = None,
) -> str:
    """Map an exception/status to a fine-grained error category."""
    if http_status == 429:
        return ERROR_HTTP_429
    if http_status is not None and http_status >= 500:
        return ERROR_HTTP_5XX
    if http_status == 404:
        return ERROR_ARCHIVE_NOT_FOUND
    err = (error or "").lower()
    if not err and http_status is None:
        return ERROR_OTHER
    if "429" in err or "too many requests" in err or "retry-after" in err:
        return ERROR_HTTP_429
    if "unexpected_eof" in err or "eof occurred" in err or "ssl" in err or "tls" in err:
        return ERROR_TLS_EOF
    if "connection refused" in err or "errno 61" in err:
        return ERROR_CONNECTION_REFUSED
    if "connection reset" in err or "errno 54" in err:
        return ERROR_CONNECTION_RESET
    if "connect timeout" in err or "connecterror" in err:
        return ERROR_CONNECT_TIMEOUT
    if "read timeout" in err or "timeout" in err or "timed out" in err:
        return ERROR_READ_TIMEOUT
    if "502" in err or "503" in err or "504" in err:
        return ERROR_HTTP_5XX
    if "not found" in err or "404" in err:
        return ERROR_ARCHIVE_NOT_FOUND
    if http_status is not None and 400 <= http_status < 500:
        return ERROR_PAGE_CONTENT
    return ERROR_OTHER


def classify_fetch_error(error: str | None, http_status: int | None = None) -> str | None:
    """Backward-compatible: return TRANSPORT_FAILURE_RESUMABLE or None."""
    cat = classify_transport_error(error, http_status)
    if cat in TRANSPORT_ERROR_TYPES or cat == TRANSPORT_FAILURE_RESUMABLE:
        return TRANSPORT_FAILURE_RESUMABLE
    return None


def is_circuit_failure(category: str) -> bool:
    return category in {
        ERROR_TLS_EOF,
        ERROR_CONNECTION_REFUSED,
        ERROR_CONNECTION_RESET,
        ERROR_CONNECT_TIMEOUT,
        ERROR_READ_TIMEOUT,
        ERROR_HTTP_429,
        ERROR_HTTP_5XX,
        TRANSPORT_FAILURE_RESUMABLE,
    }


@dataclass
class CircuitBreakerConfig:
    enabled: bool = True
    rolling_window_requests: int = 6
    failure_threshold: int = 3
    initial_cooldown_seconds: float = 300.0
    cooldown_multiplier: float = 2.0
    max_cooldown_seconds: float = 1800.0
    health_probe_successes_required: int = 2
    max_circuit_cycles_before_exit: int = 3


@dataclass
class CircuitBreaker:
    """Rolling-window circuit breaker with cooldown + health-probe recovery."""

    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitState = CircuitState.CLOSED
    recent_outcomes: list[bool] = field(default_factory=list)  # True=failure
    cooldown_seconds: float = 300.0
    open_since: float | None = None
    circuit_cycles: int = 0
    openings: int = 0
    last_reason: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cooldown_seconds = float(self.config.initial_cooldown_seconds)

    def record_success(self) -> None:
        self.recent_outcomes.append(False)
        self._trim()
        if self.state == CircuitState.HALF_OPEN:
            # half-open probe successes are tracked externally
            return

    def record_failure(self, *, url: str, error: str, category: str) -> None:
        if not is_circuit_failure(category):
            return
        self.recent_outcomes.append(True)
        self._trim()
        self.events.append({"url": url, "error": error, "category": category, "ts": time.time()})
        failures = sum(1 for x in self.recent_outcomes if x)
        if (
            self.config.enabled
            and self.state == CircuitState.CLOSED
            and failures >= self.config.failure_threshold
        ):
            self._open(reason=f"{failures} transport failures in last {len(self.recent_outcomes)} replay requests")

    def _trim(self) -> None:
        w = max(1, int(self.config.rolling_window_requests))
        if len(self.recent_outcomes) > w:
            self.recent_outcomes = self.recent_outcomes[-w:]

    def _open(self, *, reason: str) -> None:
        self.state = CircuitState.OPEN
        self.open_since = time.time()
        self.openings += 1
        self.last_reason = reason

    def should_block_requests(self) -> bool:
        return self.config.enabled and self.state == CircuitState.OPEN

    def time_until_half_open(self) -> float:
        if self.state != CircuitState.OPEN or self.open_since is None:
            return 0.0
        elapsed = time.time() - self.open_since
        return max(0.0, self.cooldown_seconds - elapsed)

    def enter_half_open_if_ready(self) -> bool:
        if self.state != CircuitState.OPEN:
            return self.state == CircuitState.HALF_OPEN
        if self.time_until_half_open() > 0:
            return False
        self.state = CircuitState.HALF_OPEN
        return True

    def close_after_probes(self) -> None:
        self.state = CircuitState.CLOSED
        self.recent_outcomes = []
        self.open_since = None
        self.cooldown_seconds = float(self.config.initial_cooldown_seconds)
        self.last_reason = ""

    def reopen_after_failed_probes(self) -> None:
        self.circuit_cycles += 1
        self.cooldown_seconds = min(
            self.config.max_cooldown_seconds,
            self.cooldown_seconds * self.config.cooldown_multiplier,
        )
        self._open(reason="health probes failed; extending cooldown")

    def exhausted_cycles(self) -> bool:
        return self.circuit_cycles >= self.config.max_circuit_cycles_before_exit


@dataclass
class TransportPolicy:
    concurrency: int = 1
    max_attempts_per_request: int = 3
    inter_request_delay_seconds: float = 3.0
    jitter_seconds: float = 2.0
    timeout_seconds: float = 45.0
    backoff_base_seconds: float = 2.0
    respect_retry_after: bool = True
    post_failure_pause_seconds: float = 5.0
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "TransportPolicy":
        data = dict(data or {})
        cb_raw = dict(data.pop("circuit_breaker", {}) or {})
        # map legacy keys
        if "circuit_breaker_threshold" in data and "failure_threshold" not in cb_raw:
            cb_raw["failure_threshold"] = int(data.pop("circuit_breaker_threshold"))
        if "throttle_seconds" in data and "inter_request_delay_seconds" not in data:
            data["inter_request_delay_seconds"] = float(data.pop("throttle_seconds"))
        if "retries" in data and "max_attempts_per_request" not in data:
            data["max_attempts_per_request"] = int(data.pop("retries"))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        cb_known = {f.name for f in CircuitBreakerConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        cb = CircuitBreakerConfig(**{k: v for k, v in cb_raw.items() if k in cb_known})
        kwargs = {k: v for k, v in data.items() if k in known and k != "circuit_breaker"}
        return cls(circuit_breaker=cb, **kwargs)


DEFAULT_TRANSPORT_POLICY = TransportPolicy.from_mapping(
    {
        "concurrency": 1,
        "max_attempts_per_request": 3,
        "inter_request_delay_seconds": 3.0,
        "jitter_seconds": 2.0,
        "timeout_seconds": 45.0,
        "backoff_base_seconds": 2.0,
        "respect_retry_after": True,
        "circuit_breaker": {
            "enabled": True,
            "rolling_window_requests": 6,
            "failure_threshold": 3,
            "initial_cooldown_seconds": 300,
            "cooldown_multiplier": 2,
            "max_cooldown_seconds": 1800,
            "health_probe_successes_required": 2,
            "max_circuit_cycles_before_exit": 3,
        },
    }
)


class TransportPausedError(RuntimeError):
    """Raised when rescue should stop cleanly as transport-unstable / resumable."""

    def __init__(self, message: str, *, resume_command: str = "") -> None:
        super().__init__(message)
        self.resume_command = resume_command
        self.code = RESCUE_PAUSED_TRANSPORT_UNSTABLE


def sleep_with_jitter(base: float, jitter: float) -> float:
    delay = max(0.0, float(base)) + random.uniform(0.0, max(0.0, float(jitter)))
    if delay:
        time.sleep(delay)
    return delay


def run_health_probes(
    *,
    probes: list[Callable[[], bool]],
    required_successes: int,
) -> dict[str, Any]:
    successes = 0
    results: list[bool] = []
    for probe in probes:
        ok = bool(probe())
        results.append(ok)
        if ok:
            successes += 1
        else:
            break
        if successes >= required_successes:
            break
    return {
        "successes": successes,
        "required": required_successes,
        "ok": successes >= required_successes,
        "results": results,
    }
