"""Tests for URL port normalization."""

from ffb_webminer.archive.wayback_url import normalize_canonical_from_cdx, normalize_original_url


def test_strip_default_http_port():
    assert normalize_original_url("http://www.example.com:80/") == "http://www.example.com/"


def test_strip_default_https_port():
    assert normalize_original_url("https://www.example.com:443/about") == "https://www.example.com/about"


def test_cdx_original_preserved():
    canonical, raw = normalize_canonical_from_cdx("http://www.example.com:80/")
    assert canonical == "http://www.example.com/"
    assert raw == "http://www.example.com:80/"
