"""Tests for URL normalization and link policy."""

from ffb_webminer.crawl.link_policy import branding_score, is_excluded_url, normalize_url


def test_normalize_strips_fragment():
    url = normalize_url("https://www.example.com/page#section")
    assert "#" not in url


def test_excluded_extension():
    assert is_excluded_url("https://www.example.com/logo.png")


def test_branding_score_german():
    patterns = {"de": ["ueber-uns", "geschichte"], "en": ["about"]}
    score_about = branding_score("https://www.example.com/about", patterns, prefer_german=True)
    score_ueber = branding_score("https://www.example.com/ueber-uns", patterns, prefer_german=True)
    assert score_ueber > score_about
