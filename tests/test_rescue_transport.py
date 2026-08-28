"""Phase B transport/cache/circuit-breaker tests — mocks only, no Wayback."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ffb_webminer.rescue.page_cache import (
    STATUS_FETCHED,
    STATUS_FETCH_FAILED_RESUMABLE,
    STATUS_PENDING,
    AtomicPageCache,
    PageFetchRecord,
    PageFetchStateStore,
    page_cache_key,
)
from ffb_webminer.rescue.resumable_fetcher import ResumableRescueFetcher
from ffb_webminer.rescue.smoke_report import write_bbraun_smoke_report
from ffb_webminer.rescue.transport import (
    ERROR_CONNECTION_REFUSED,
    ERROR_HTTP_429,
    ERROR_TLS_EOF,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    TransportPausedError,
    TransportPolicy,
    classify_fetch_error,
    classify_transport_error,
    is_circuit_failure,
    run_health_probes,
)
from ffb_webminer.extract.language_detection import detect_page_language


ROOT = Path(__file__).resolve().parents[1]


def test_page_cache_key_differs_by_timestamp():
    u = "https://www.bbraun.de/"
    k1 = page_cache_key(u, "20190704175027")
    k2 = page_cache_key(u, "20210706194317")
    assert k1 != k2
    assert page_cache_key(u, "20190704175027.0") == k1


def test_atomic_cache_write_and_reuse(tmp_path: Path):
    cache = AtomicPageCache(tmp_path / "html")
    key = page_cache_key("https://example.de/", "20200101120000")
    content = b"<html>ok</html>"
    path, digest = cache.write_atomic(
        key, content, metadata={"http_status": 200, "mime_type": "text/html"}
    )
    assert path.exists()
    assert path.read_bytes() == content
    hit = cache.read_valid(key, expected_hash=digest)
    assert hit is not None
    assert hit[0] == content


def test_corrupt_cache_rejected(tmp_path: Path):
    cache = AtomicPageCache(tmp_path / "html")
    key = page_cache_key("https://example.de/", "20200101120000")
    cache.write_atomic(key, b"<html>good</html>", metadata={"http_status": 200})
    # Tamper HTML without updating meta
    cache.html_path(key).write_bytes(b"<html>tampered</html>")
    assert cache.read_valid(key) is None


def test_empty_content_not_cached(tmp_path: Path):
    cache = AtomicPageCache(tmp_path / "html")
    key = "abc"
    with pytest.raises(ValueError):
        cache.write_atomic(key, b"", metadata={})


def test_sqlite_state_resume_counts(tmp_path: Path):
    store = PageFetchStateStore(tmp_path / "state.sqlite")
    try:
        k = page_cache_key("https://a.de/", "20200101")
        store.upsert(
            PageFetchRecord(
                page_cache_key=k,
                firm_id="10",
                original_url="https://a.de/",
                replay_url="https://web.archive.org/web/20200101id_/https://a.de/",
                archive_timestamp="20200101",
                fetch_status=STATUS_FETCHED,
                cache_valid=True,
            )
        )
        store.upsert(
            PageFetchRecord(
                page_cache_key=page_cache_key("https://b.de/", "20200101"),
                firm_id="10",
                original_url="https://b.de/",
                replay_url="x",
                archive_timestamp="20200101",
                fetch_status=STATUS_FETCH_FAILED_RESUMABLE,
                transport_error_type=ERROR_CONNECTION_REFUSED,
            )
        )
        c = store.counts(firm_id="10")
        assert c["cached_valid_pages"] == 1
        assert c["resumable_failures"] == 1
    finally:
        store.close()


def test_transport_taxonomy():
    assert classify_transport_error("Connection refused") == ERROR_CONNECTION_REFUSED
    assert classify_transport_error("SSL: UNEXPECTED_EOF_WHILE_READING") == ERROR_TLS_EOF
    assert classify_transport_error(None, 429) == ERROR_HTTP_429
    assert classify_transport_error(None, 404) == "archive_not_found"
    assert classify_fetch_error("Connection refused") == "transport_failure_resumable"
    assert classify_fetch_error("page missing", 404) is None
    assert is_circuit_failure(ERROR_CONNECTION_REFUSED)
    assert not is_circuit_failure("archive_not_found")


def test_circuit_opens_at_threshold_and_blocks():
    cb = CircuitBreaker(
        config=CircuitBreakerConfig(
            enabled=True,
            rolling_window_requests=5,
            failure_threshold=3,
            initial_cooldown_seconds=0.01,
            max_circuit_cycles_before_exit=2,
        )
    )
    assert cb.state == CircuitState.CLOSED
    for i in range(3):
        cb.record_failure(url=f"u{i}", error="refused", category=ERROR_CONNECTION_REFUSED)
    assert cb.state == CircuitState.OPEN
    assert cb.should_block_requests()
    assert cb.openings == 1


def test_circuit_half_open_success_closes():
    cb = CircuitBreaker(
        config=CircuitBreakerConfig(
            failure_threshold=1,
            initial_cooldown_seconds=0,
            health_probe_successes_required=2,
        )
    )
    cb.record_failure(url="u", error="x", category=ERROR_TLS_EOF)
    assert cb.state == CircuitState.OPEN
    assert cb.enter_half_open_if_ready()
    assert cb.state == CircuitState.HALF_OPEN
    cb.close_after_probes()
    assert cb.state == CircuitState.CLOSED
    assert not cb.should_block_requests()


def test_circuit_probe_failure_extends_cooldown_and_exits():
    cb = CircuitBreaker(
        config=CircuitBreakerConfig(
            failure_threshold=1,
            initial_cooldown_seconds=10,
            cooldown_multiplier=2,
            max_cooldown_seconds=100,
            max_circuit_cycles_before_exit=2,
        )
    )
    cb.record_failure(url="u", error="x", category=ERROR_HTTP_429)
    assert cb.cooldown_seconds == 10
    cb.enter_half_open_if_ready()  # cooldown may still be >0 if open_since just set
    cb.open_since = 0  # force ready
    assert cb.enter_half_open_if_ready()
    cb.reopen_after_failed_probes()
    assert cb.cooldown_seconds == 20
    assert cb.circuit_cycles == 1
    cb.reopen_after_failed_probes()
    assert cb.exhausted_cycles()


def test_health_probes_require_consecutive():
    calls = {"n": 0}

    def ok():
        calls["n"] += 1
        return True

    def fail():
        calls["n"] += 1
        return False

    out = run_health_probes(probes=[ok, fail, ok], required_successes=2)
    assert out["ok"] is False
    assert calls["n"] == 2
    out2 = run_health_probes(probes=[ok, ok], required_successes=2)
    assert out2["ok"] is True


def test_fetcher_reuses_valid_cache_without_network(tmp_path: Path):
    cache_dir = tmp_path / "html"
    state_db = tmp_path / "state.sqlite"
    policy = TransportPolicy(
        max_attempts_per_request=1,
        inter_request_delay_seconds=0,
        jitter_seconds=0,
        circuit_breaker=CircuitBreakerConfig(enabled=False),
    )
    fetcher = ResumableRescueFetcher(
        user_agent="test",
        cache_dir=cache_dir,
        state_db=state_db,
        policy=policy,
        sleep_fn=lambda _s: None,
    )
    try:
        key = page_cache_key("https://example.de/page", "20200101120000")
        content = b"<html>cached</html>"
        path, digest = fetcher.cache.write_atomic(
            key, content, metadata={"http_status": 200, "mime_type": "text/html"}
        )
        fetcher.store.upsert(
            PageFetchRecord(
                page_cache_key=key,
                firm_id="10",
                original_url="https://example.de/page",
                replay_url="https://web.archive.org/web/20200101120000id_/https://example.de/page",
                archive_timestamp="20200101120000",
                fetch_status=STATUS_FETCHED,
                content_hash=digest,
                bytes_received=len(content),
                http_status=200,
                mime_type="text/html",
                cache_path=str(path),
                cache_valid=True,
            )
        )
        with patch.object(fetcher, "_client_get") as mock_client:
            result = fetcher.fetch("https://example.de/page", "20200101120000")
            mock_client.assert_not_called()
        assert result.content == content
        assert fetcher.stats["cache_hits"] == 1
    finally:
        fetcher.close()


def test_fetcher_retries_resumable_failure(tmp_path: Path):
    policy = TransportPolicy(
        max_attempts_per_request=2,
        inter_request_delay_seconds=0,
        jitter_seconds=0,
        backoff_base_seconds=0,
        post_failure_pause_seconds=0,
        circuit_breaker=CircuitBreakerConfig(enabled=False),
    )
    fetcher = ResumableRescueFetcher(
        user_agent="test",
        cache_dir=tmp_path / "html",
        state_db=tmp_path / "s.sqlite",
        policy=policy,
        sleep_fn=lambda _s: None,
    )
    try:
        key = page_cache_key("https://example.de/", "20200101120000")
        fetcher.store.upsert(
            PageFetchRecord(
                page_cache_key=key,
                firm_id="10",
                original_url="https://example.de/",
                replay_url="r",
                archive_timestamp="20200101120000",
                fetch_status=STATUS_FETCH_FAILED_RESUMABLE,
                transport_error_type=ERROR_CONNECTION_REFUSED,
            )
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html>recovered</html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://web.archive.org/web/20200101120000id_/https://example.de/"
        client = MagicMock()
        client.get.return_value = mock_resp
        with patch.object(fetcher, "_client_get", return_value=client):
            result = fetcher.fetch("https://example.de/", "20200101120000")
        assert result.content == b"<html>recovered</html>"
        rec = fetcher.store.get(key)
        assert rec is not None
        assert rec.fetch_status == STATUS_FETCHED
    finally:
        fetcher.close()


def test_transport_failure_never_archive_unavailable():
    from ffb_webminer.rescue.compare import decide_rescue

    out = decide_rescue(
        firm_id="10",
        original_obs=None,
        rescue_obs=None,
        original_snap=None,
        rescue_snap=None,
        entity_change_flag=False,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
        transport_failure=True,
    )
    assert out["rescue_decision"] == "transport_failure_resumable"
    assert "unavailable" not in str(out["rescue_decision"]).lower() or "archive" not in str(
        out.get("decision_reason", "")
    ).lower()


def test_circuit_open_blocks_further_requests(tmp_path: Path):
    sleeps: list[float] = []
    policy = TransportPolicy(
        max_attempts_per_request=1,
        inter_request_delay_seconds=0,
        jitter_seconds=0,
        post_failure_pause_seconds=0,
        circuit_breaker=CircuitBreakerConfig(
            enabled=True,
            rolling_window_requests=3,
            failure_threshold=2,
            initial_cooldown_seconds=0.001,
            max_circuit_cycles_before_exit=1,
            health_probe_successes_required=2,
        ),
    )
    fetcher = ResumableRescueFetcher(
        user_agent="test",
        cache_dir=tmp_path / "html",
        state_db=tmp_path / "s.sqlite",
        policy=policy,
        sleep_fn=lambda s: sleeps.append(s),
        resume_command="python scripts/run_full_sample_rescue.py --resume",
    )
    try:
        # Seed circuit already open with exhausted cycles via probe failure
        fetcher.circuit.state = CircuitState.OPEN
        fetcher.circuit.open_since = 0
        fetcher.circuit.circuit_cycles = 1
        fetcher.circuit.last_reason = "test"
        with patch.object(fetcher, "_run_default_probes", return_value={"ok": False, "successes": 0}):
            with pytest.raises(TransportPausedError) as ei:
                fetcher.fetch("https://example.de/", "20200101120000")
        assert "RESCUE_PAUSED_TRANSPORT_UNSTABLE" in str(ei.value)
    finally:
        fetcher.close()


def test_retry_after_handling(tmp_path: Path):
    sleeps: list[float] = []
    policy = TransportPolicy(
        max_attempts_per_request=2,
        inter_request_delay_seconds=0,
        jitter_seconds=0,
        backoff_base_seconds=0,
        post_failure_pause_seconds=0,
        respect_retry_after=True,
        circuit_breaker=CircuitBreakerConfig(enabled=False),
    )
    fetcher = ResumableRescueFetcher(
        user_agent="test",
        cache_dir=tmp_path / "html",
        state_db=tmp_path / "s.sqlite",
        policy=policy,
        sleep_fn=lambda s: sleeps.append(s),
    )
    try:
        req = httpx.Request("GET", "https://web.archive.org/web/20200101120000id_/https://example.de/")
        resp429 = httpx.Response(429, headers={"Retry-After": "7"}, request=req)
        resp200 = MagicMock()
        resp200.status_code = 200
        resp200.content = b"<html>ok</html>"
        resp200.headers = {"content-type": "text/html"}
        resp200.url = str(req.url)
        client = MagicMock()
        client.get.side_effect = [
            resp429,
            resp200,
        ]
        with patch.object(fetcher, "_client_get", return_value=client):
            # First attempt raises via HTTPStatusError path inside _fetch_once
            result = fetcher.fetch("https://example.de/", "20200101120000")
        assert 7.0 in sleeps or any(s >= 7 for s in sleeps)
        assert result.content == b"<html>ok</html>"
    finally:
        fetcher.close()


def test_ssl_eof_resets_session(tmp_path: Path):
    policy = TransportPolicy(
        max_attempts_per_request=2,
        inter_request_delay_seconds=0,
        jitter_seconds=0,
        backoff_base_seconds=0,
        post_failure_pause_seconds=0,
        circuit_breaker=CircuitBreakerConfig(enabled=False),
    )
    fetcher = ResumableRescueFetcher(
        user_agent="test",
        cache_dir=tmp_path / "html",
        state_db=tmp_path / "s.sqlite",
        policy=policy,
        sleep_fn=lambda _s: None,
    )
    try:
        resets = {"n": 0}
        original_reset = fetcher._reset_client

        def counting_reset():
            resets["n"] += 1
            original_reset()

        fetcher._reset_client = counting_reset  # type: ignore[method-assign]
        client = MagicMock()
        client.get.side_effect = [
            httpx.ConnectError("SSL: UNEXPECTED_EOF_WHILE_READING"),
            MagicMock(
                status_code=200,
                content=b"<html>ok</html>",
                headers={"content-type": "text/html"},
                url="https://web.archive.org/x",
            ),
        ]
        with patch.object(fetcher, "_client_get", return_value=client):
            result = fetcher.fetch("https://example.de/", "20200101120000")
        assert resets["n"] >= 1
        assert result.content == b"<html>ok</html>"
    finally:
        fetcher.close()


def test_bbraun_smoke_summary(tmp_path: Path):
    path = write_bbraun_smoke_report(
        tmp_path / "bbraun_smoke_test.md",
        payload={
            "final_status": "SMOKE_TEST_PAUSED_TRANSPORT_RESUMABLE",
            "firm_id": "10",
            "company": "B. Braun",
            "timepoints": ["pre_event", "event"],
            "discovered_captures": 5,
            "pages_planned": 40,
            "pages_cached_before": 17,
            "pages_newly_fetched": 0,
            "cache_hits": 17,
            "pending_pages": 23,
            "transport_failures_by_category": {"transport_connection_refused": 3},
            "retries": 3,
            "circuit_openings": 1,
            "cooldown_durations": 300,
            "cdx_probe_results": 2,
            "replay_probe_results": {"ok": 4, "fail": 1},
            "observations_extracted": None,
            "german_pages_tokens": None,
            "rescue_decisions": None,
            "longitudinal_ready": None,
            "parent_release_integrity": "unchanged",
            "resume_command": "python scripts/run_full_sample_rescue.py --resume",
            "notes": "paused",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "SMOKE_TEST_PAUSED_TRANSPORT_RESUMABLE" in text
    assert "B. Braun" in text
    assert "17" in text


def test_lingua_api_compatible_with_2_1_1():
    # API used by extract/language_detection.py must work on lingua 2.1.1+
    from lingua import Language, LanguageDetectorBuilder

    detector = LanguageDetectorBuilder.from_languages(Language.GERMAN, Language.ENGLISH).build()
    confidences = detector.compute_language_confidence_values(
        "Dies ist ein deutscher Text über Familie und Unternehmen."
    )
    assert confidences
    assert confidences[0].language in {Language.GERMAN, Language.ENGLISH}
    result = detect_page_language(
        "Dies ist ein längerer deutscher Firmenbeschreibungstext über Werte und Familie.",
        min_chars=20,
        confidence_threshold=0.5,
    )
    assert result.language in {"de", "en", "unknown"}
    assert result.method == "lingua"


def test_preflight_success_and_failure_mocked():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_full_sample_rescue", ROOT / "scripts/run_full_sample_rescue.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    class FakeResp:
        def __init__(self, status: int, content: bytes):
            self.status_code = status
            self.content = content

    class FakeClient:
        def __init__(self, *a, **k):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            self.calls += 1
            # CDX + replay successes
            if "cdx" in str(a) or "cdx" in str(k):
                return FakeResp(200, b'[["ts","orig","200"]]')
            return FakeResp(200, b"<html>" + (b"x" * 200) + b"</html>")

    orch = MagicMock()
    orch.no_network = False
    orch.dry_run = False
    orch.rescue_doc = {
        "preflight": {
            "cdx_requests": 2,
            "replay_requests": 5,
            "min_replay_success_rate": 0.8,
            "require_no_sustained_transport_cluster": True,
            "cdx_urls": ["https://www.bbraun.de/"],
            "replay_urls": [
                "https://web.archive.org/web/20190704175027id_/https://www.bbraun.com/",
                "https://web.archive.org/web/20210706194317id_/https://www.bbraun.de/de.html",
            ],
        }
    }
    orch.transport_policy = TransportPolicy(
        inter_request_delay_seconds=0, jitter_seconds=0
    )
    orch.preflight_metrics = {}
    orch.validate = MagicMock(return_value=0)

    with patch.object(mod, "time") as mock_time:
        mock_time.time.side_effect = lambda: 0.0
        mock_time.sleep = lambda _s: None
        with patch("httpx.Client", FakeClient):
            # Bind unbound method
            rc = mod.RescueOrchestrator.preflight(orch)
    assert rc == 0
    assert orch.preflight_metrics.get("ok") is True

    class FailClient(FakeClient):
        def get(self, *a, **k):
            raise ConnectionRefusedError("Connection refused")

    orch2 = MagicMock()
    orch2.no_network = False
    orch2.dry_run = False
    orch2.rescue_doc = orch.rescue_doc
    orch2.transport_policy = orch.transport_policy
    orch2.preflight_metrics = {}
    orch2.validate = MagicMock(return_value=0)
    with patch.object(mod, "time") as mock_time:
        mock_time.time.side_effect = lambda: 0.0
        mock_time.sleep = lambda _s: None
        with patch("httpx.Client", FailClient):
            rc2 = mod.RescueOrchestrator.preflight(orch2)
    assert rc2 == mod.EXIT_PREFLIGHT_FAILED
    assert orch2.preflight_metrics.get("ok") is False


def test_lingua_constraint_in_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "lingua-language-detector>=2.1.1,<3" in text


def test_process_restart_reuses_sqlite_state(tmp_path: Path):
    db = tmp_path / "page_fetch_state.sqlite"
    store1 = PageFetchStateStore(db)
    key = page_cache_key("https://example.de/", "20200101120000")
    store1.upsert(
        PageFetchRecord(
            page_cache_key=key,
            firm_id="10",
            original_url="https://example.de/",
            replay_url="r",
            archive_timestamp="20200101120000",
            fetch_status=STATUS_FETCHED,
            cache_valid=True,
            content_hash="abc",
        )
    )
    store1.close()
    store2 = PageFetchStateStore(db)
    try:
        rec = store2.get(key)
        assert rec is not None
        assert rec.fetch_status == STATUS_FETCHED
        assert store2.counts()["cached_valid_pages"] == 1
    finally:
        store2.close()


def test_page_fetch_store_reopens_after_close(tmp_path: Path):
    """Extract may still read cache after an accidental close; reopen, do not crash."""
    db = tmp_path / "page_fetch_state.sqlite"
    store = PageFetchStateStore(db)
    key = page_cache_key("https://example.de/", "20200101120000")
    store.upsert(
        PageFetchRecord(
            page_cache_key=key,
            firm_id="10",
            original_url="https://example.de/",
            replay_url="r",
            archive_timestamp="20200101120000",
            fetch_status=STATUS_FETCHED,
            cache_valid=True,
            content_hash="abc",
        )
    )
    store.close()
    rec = store.get(key)
    assert rec is not None
    assert rec.fetch_status == STATUS_FETCHED
    store.close()
