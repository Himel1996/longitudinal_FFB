"""Tests for domain parsing."""

from ffb_webminer.extract.domain import parse_domain, same_registrable_domain


def test_parse_subdomain():
    info = parse_domain("https://www.example.co.uk/about")
    assert info.registrable_domain == "example.co.uk"
    assert info.subdomain == "www"


def test_same_registrable_domain():
    assert same_registrable_domain("https://www.example.com", "http://example.com/path")
