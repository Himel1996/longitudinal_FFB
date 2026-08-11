"""Rescue discovery-state persistence tests — no Wayback."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ffb_webminer.rescue.compare import decide_rescue
from ffb_webminer.rescue.discovery_state import (
    ATTEMPT_CDX_EMPTY,
    ATTEMPT_TRANSPORT,
    DiscoveryStateStore,
    atomic_write_rescue_snapshots,
    count_selected_snapshots,
    import_snapshots_csv_to_store,
    load_authoritative_rescue_snapshots,
    merge_authoritative_snapshots,
    validate_rescue_snapshots_regression,
)
from ffb_webminer.rescue.page_cache import (
    STATUS_FETCHED,
    PageFetchRecord,
    PageFetchStateStore,
    page_cache_key,
)
from ffb_webminer.rescue.runner import RescuePipelineRunner
from ffb_webminer.rescue.transport import TRANSPORT_FAILURE_RESUMABLE


def _selected_row(
    *,
    firm_id: str = "10",
    tp: str = "post_event",
    ts: str = "20210706194317",
    seed: str = "https://www.bbraun.de/de.html",
    domain: str = "bbraun.de",
    dist: float = 3.0,
) -> dict:
    return {
        "firm_id": firm_id,
        "relative_timepoint": tp,
        "target_date": "2021-07-01",
        "snapshot_status": "selected",
        "archive_timestamp": ts,
        "canonical_original_url": seed,
        "temporal_distance_days": dist,
        "temporal_fit_quality": "high",
        "selection_reason": "closest",
        "rescue_seed_url": seed,
        "rescue_source_row_id": "5",
        "rescue_candidate_type": "locale_path",
        "rescue_domain": domain,
        "analysis_eligible": True,
    }


@pytest.fixture
def store(tmp_path: Path) -> DiscoveryStateStore:
    s = DiscoveryStateStore(tmp_path / "state" / "rescue_discovery_state.sqlite")
    yield s
    s.close()


def test_a_successful_discovery_survives_later_connection_refused(store: DiscoveryStateStore):
    row = _selected_row()
    store.persist_selection(row, alias_meta={"candidate_seed_url": row["rescue_seed_url"]})
    store.record_attempt(
        firm_id="10",
        relative_timepoint="post_event",
        candidate_seed_url=row["rescue_seed_url"],
        attempt_status=ATTEMPT_TRANSPORT,
        error="[Errno 61] Connection refused",
    )
    rec = store.get("10", "post_event")
    assert rec is not None
    assert rec.has_valid_selection
    assert rec.selected_capture_timestamp == "20210706194317"
    assert rec.latest_discovery_attempt_status == ATTEMPT_TRANSPORT


def test_b_successful_discovery_survives_transport_empty_attempt(store: DiscoveryStateStore):
    row = _selected_row(tp="pre_event", ts="20190704175027")
    store.persist_selection(row)
    store.record_attempt(
        firm_id="10",
        relative_timepoint="pre_event",
        candidate_seed_url=row["rescue_seed_url"],
        attempt_status=ATTEMPT_CDX_EMPTY,
    )
    rec = store.get("10", "pre_event")
    assert rec.has_valid_selection
    assert rec.latest_discovery_attempt_status == ATTEMPT_CDX_EMPTY


def test_c_better_valid_capture_may_update_selection(store: DiscoveryStateStore):
    old = _selected_row(dist=120.0)
    store.persist_selection(old)
    newer = _selected_row(dist=5.0)
    updated = store.persist_selection(newer)
    assert updated is True
    rec = store.get("10", "post_event")
    assert rec.temporal_distance_days == 5.0

    worse = _selected_row(dist=200.0)
    assert store.persist_selection(worse) is False
    rec = store.get("10", "post_event")
    assert rec.temporal_distance_days == 5.0


def test_d_empty_dataframe_cannot_overwrite_populated_snapshots(tmp_path: Path, store: DiscoveryStateStore):
    row = _selected_row()
    store.persist_selection(row)
    df = pd.DataFrame([row])
    out = tmp_path / "rescue_snapshots.csv"
    atomic_write_rescue_snapshots(out, df, firm_ids={"10"})

    previous = pd.read_csv(out, dtype=str)
    empty = pd.DataFrame(columns=previous.columns)
    ok, reason = validate_rescue_snapshots_regression(previous, empty, firm_ids={"10"})
    assert not ok
    assert "empty" in reason.lower() or "drop" in reason.lower()

    with pytest.raises(ValueError):
        atomic_write_rescue_snapshots(out, empty, previous=previous, firm_ids={"10"})

    assert count_selected_snapshots(pd.read_csv(out, dtype=str), {"10"}) == 1


def test_e_resume_loads_state_without_new_cdx(store: DiscoveryStateStore):
    for tp, ts in [
        ("pre_event", "20190704175027"),
        ("post_event", "20210706194317"),
        ("post_post_event", "20230701145021"),
    ]:
        store.persist_selection(_selected_row(tp=tp, ts=ts))
    rows = store.snapshot_rows(firm_ids=["10"])
    assert len(rows) == 3
    assert all(r["snapshot_status"] == "selected" for r in rows)


def test_f_parent_and_rescue_both_reach_compare_distinctly():
    parent_obs = pd.Series(
        {
            "german_text_analysis_eligible": False,
            "text_analysis_eligible": True,
            "observation_recommendation": "sensitivity_analysis",
            "tokens_de": 0,
            "n_pages_de": 0,
        }
    )
    rescue_obs = pd.Series(
        {
            "german_text_analysis_eligible": True,
            "text_analysis_eligible": True,
            "observation_recommendation": "include",
            "tokens_de": 450,
            "n_pages_de": 8,
        }
    )
    parent_snap = pd.Series({"temporal_fit_quality": "very_low", "temporal_distance_days": 448})
    rescue_snap = pd.Series(
        {
            "snapshot_status": "selected",
            "temporal_fit_quality": "high",
            "temporal_distance_days": 3,
            "rescue_domain": "bbraun.de",
            "rescue_seed_url": "https://www.bbraun.de/de.html",
        }
    )
    decision = decide_rescue(
        firm_id="10",
        original_obs=parent_obs,
        rescue_obs=rescue_obs,
        original_snap=parent_snap,
        rescue_snap=rescue_snap,
        entity_change_flag=False,
        migration_flag=False,
        force_sensitivity_firms=set(),
        min_branding_tokens=100,
    )
    assert decision["rescue_decision"] == "replace_with_rescue"
    assert decision["original_german_text_eligible"] is False
    assert decision["rescue_german_text_eligible"] is True


def test_g_cached_pages_reused_with_persisted_snapshot(tmp_path: Path, store: DiscoveryStateStore):
    row = _selected_row()
    store.persist_selection(row)
    page_store = PageFetchStateStore(tmp_path / "state" / "page_fetch_state.sqlite")
    url = "https://www.bbraun.de/de/unternehmen.html"
    ts = row["archive_timestamp"]
    key = page_cache_key(url, ts)
    rec = PageFetchRecord(
        page_cache_key=key,
        firm_id="10",
        relative_timepoint="post_event",
        original_url=url,
        replay_url=f"https://web.archive.org/web/{ts}id_/{url}",
        archive_timestamp=ts,
        fetch_status=STATUS_FETCHED,
        cache_valid=True,
        content_hash="abc123",
    )
    page_store.upsert(rec)
    loaded = page_store.get(key)
    page_store.close()
    assert loaded is not None
    assert loaded.firm_id == "10"
    assert loaded.relative_timepoint == "post_event"
    assert loaded.archive_timestamp == ts


def test_h_cached_pages_without_snapshot_not_synthesized(tmp_path: Path):
    page_store = PageFetchStateStore(tmp_path / "state" / "page_fetch_state.sqlite")
    url = "https://www.bbraun.de/de/unternehmen.html"
    key = page_cache_key(url, "20210706194317")
    page_store.upsert(
        PageFetchRecord(
            page_cache_key=key,
            firm_id="10",
            relative_timepoint="post_event",
            original_url=url,
            replay_url="https://web.archive.org/web/20210706194317id_/https://www.bbraun.de/de/unternehmen.html",
            archive_timestamp="20210706194317",
            fetch_status=STATUS_FETCHED,
            cache_valid=True,
        )
    )
    page_store.close()
    disc = DiscoveryStateStore(tmp_path / "state" / "rescue_discovery_state.sqlite")
    try:
        assert disc.snapshot_rows(firm_ids=["10"]) == []
        auth = load_authoritative_rescue_snapshots(tmp_path, disc, firm_ids=["10"])
        assert auth.empty
    finally:
        disc.close()


def test_i_non_targeted_firms_unchanged_in_merge(tmp_path: Path, store: DiscoveryStateStore):
    store.persist_selection(_selected_row(firm_id="10"))
    new_df = pd.DataFrame(
        [
            _selected_row(firm_id="6", tp="pre_event", ts="20150101010101", seed="https://example.com/"),
        ]
    )
    merged = merge_authoritative_snapshots(new_df, store, firm_ids=["10", "6"])
    assert len(merged[merged["firm_id"].astype(str) == "10"]) >= 1
    assert len(merged[merged["firm_id"].astype(str) == "6"]) == 1


def test_runner_skips_parent_fallback_on_transport_only():
    """Rescue aliases with transport-only failures must not fall back to parent domain."""
    import pandas as pd
    from types import SimpleNamespace

    runner = RescuePipelineRunner.__new__(RescuePipelineRunner)
    runner.config = SimpleNamespace(
        snapshot_selection=SimpleNamespace(
            allowed_status_codes=["200"],
            allowed_mimetypes=["text/html"],
            event_pre_window_days=90,
        )
    )
    runner.run_id = "test"
    runner.pipeline_run_date = None
    runner.rescue_discovery_log = []
    runner.discovery_store = None
    runner.discovery_resume = False
    runner.config_hash = None
    runner.candidate_file_hash = None

    alias = SimpleNamespace(
        candidate_seed_url="https://www.bbraun.de/de.html",
        source_row_id="5",
        candidate_domain="bbraun.de",
        historical_domain_flag=False,
        locale_path_flag=True,
        migration_warning=False,
        entity_change_warning=False,
        priority=1,
        candidate_type="locale_path",
        archive_evidence="test",
    )
    runner.seed_aliases = {("10", "post_event"): [alias]}

    row = pd.Series(
        {
            "firm_id": "10",
            "relative_timepoint": "post_event",
            "target_date": "2021-07-01",
            "website": "https://www.bbraun.com/",
            "rank": 1,
            "company": "B. BRAUN SE",
            "event_type": "x",
            "event_year": 2019,
            "event_label": "y",
        }
    )

    class FailClient:
        def search(self, *args, **kwargs):
            raise ConnectionError("[Errno 61] Connection refused")

    out = RescuePipelineRunner._discover_one_snapshot(runner, row, FailClient(), [])
    assert TRANSPORT_FAILURE_RESUMABLE in str(out.get("selection_reason", ""))
    assert out.get("rescue_domain") == "bbraun.de"
    assert out.get("snapshot_status") != "selected"


def test_import_snapshots_csv_to_store(tmp_path: Path, store: DiscoveryStateStore):
    csv_path = tmp_path / "rescue_snapshots.csv"
    pd.DataFrame([_selected_row(), _selected_row(tp="pre_event", ts="20190704175027")]).to_csv(
        csv_path, index=False
    )
    n = import_snapshots_csv_to_store(store, csv_path)
    assert n == 2
    assert store.counts(firm_id="10")["selected_rescue_snapshots"] == 2


def test_merge_authoritative_overlays_persisted_on_failed_rediscovery(store: DiscoveryStateStore):
    store.persist_selection(_selected_row())
    failed = pd.DataFrame(
        [
            {
                "firm_id": "10",
                "relative_timepoint": "post_event",
                "snapshot_status": "not_found",
                "selection_reason": TRANSPORT_FAILURE_RESUMABLE,
            }
        ]
    )
    merged = merge_authoritative_snapshots(failed, store, firm_ids=["10"])
    sel = merged[merged["relative_timepoint"] == "post_event"].iloc[0]
    assert sel["snapshot_status"] == "selected"
    assert sel["archive_timestamp"] == "20210706194317"
