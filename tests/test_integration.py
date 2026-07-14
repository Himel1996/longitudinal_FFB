"""Integration test with cached CDX fixture."""

import json
from datetime import date
from pathlib import Path

from ffb_webminer.archive.cdx_client import CDXClient
from ffb_webminer.archive.snapshot_selector import select_snapshot
from ffb_webminer.config import SnapshotSelectionConfig


def test_cdx_cache_and_selection(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "cdx_sample.json"
    rows = json.loads(fixture.read_text())
    cache_dir = tmp_path / "cdx"
    cache_dir.mkdir()
    key_file = list(cache_dir.glob("*.json"))
    # Pre-seed cache by calling client with mocked response via direct cache write
    import hashlib
    from ffb_webminer.archive.cdx_client import CDXClient as Client

    client = CDXClient(
        api_url="https://web.archive.org/cdx/search/cdx",
        cache_dir=cache_dir,
        user_agent="test",
        throttle_seconds=0,
    )
    cache_key = client._cache_key("http://www.example.de/", {"status": [], "mime": []})
    (cache_dir / f"{cache_key}.json").write_text(json.dumps(rows[1:]))

    results = client.search("http://www.example.de/", use_cache=True, status_codes=None, mimetypes=None)
    assert len(results) == 2
    assert results[0]["timestamp"] == "20150615120000"

    config = SnapshotSelectionConfig(tolerance_days=548)
    sel = select_snapshot(results, date(2015, 7, 1), config, run_date=date(2026, 7, 13))
    assert sel.snapshot_status == "selected"
    assert "web.archive.org" in (sel.wayback_replay_url or "")
