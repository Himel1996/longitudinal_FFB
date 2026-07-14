"""Tests for Wayback URL helpers."""

from ffb_webminer.archive.wayback_url import (
    build_replay_url,
    is_wayback_url,
    normalize_original_url,
    parse_wayback_url,
    unwrap_wayback_url,
)


def test_build_replay_url():
    url = build_replay_url("https://www.example.com/", "20150301000000")
    assert "web.archive.org/web/20150301000000id_/" in url
    assert "example.com" in url


def test_parse_and_unwrap():
    replay = "https://web.archive.org/web/20150301000000id_/http://www.example.com/about"
    parsed = parse_wayback_url(replay)
    assert parsed is not None
    ts, mod, orig = parsed
    assert ts == "20150301000000"
    assert unwrap_wayback_url(replay) == "http://www.example.com/about"


def test_is_wayback_url():
    assert is_wayback_url("https://web.archive.org/web/20150101000000/http://example.com/")
    assert not is_wayback_url("https://www.example.com/")


def test_normalize_original_url():
    assert normalize_original_url("https://www.Example.com/path/") == "https://www.example.com/path"
