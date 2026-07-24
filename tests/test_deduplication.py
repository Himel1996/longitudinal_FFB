"""Tests for URL canonicalization and within-observation deduplication."""

from ffb_webminer.crawl.url_canonical import canonicalize_page_url
from ffb_webminer.quality.deduplication import deduplicate_within_observations


def test_canonicalize_www_and_ports_and_index():
    a = canonicalize_page_url("https://www.example.com/index.html")
    b = canonicalize_page_url("http://example.com/")
    c = canonicalize_page_url("https://example.com:443/")
    assert a.url_variant_group_id == b.url_variant_group_id == c.url_variant_group_id
    assert a.canonical_host == "example.com"
    assert a.canonical_page_url.endswith("example.com/")


def test_canonicalize_preserves_distinct_paths():
    a = canonicalize_page_url("https://example.com/about")
    b = canonicalize_page_url("https://example.com/history")
    assert a.url_variant_group_id != b.url_variant_group_id


def test_www_non_www_same_timepoint_deduped():
    pages = [
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://www.myrenne.de/about",
            "hostname": "www.myrenne.de",
            "path": "/about",
            "page_category": "company_about",
            "main_text": "Familienunternehmen seit 1900 mit Werten und Tradition.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 2,
            "token_count": 8,
            "word_count": 8,
        },
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://myrenne.de/about",
            "hostname": "myrenne.de",
            "path": "/about",
            "page_category": "company_about",
            "main_text": "Familienunternehmen seit 1900 mit Werten und Tradition.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 5,
            "token_count": 8,
            "word_count": 8,
        },
    ]
    out = deduplicate_within_observations(pages)
    flags = [r["duplicate_content_flag"] for r in out]
    assert flags.count(True) == 1
    assert flags.count(False) == 1
    loser = next(r for r in out if r["duplicate_content_flag"])
    assert loser["branding_corpus_eligible"] is False
    assert loser["branding_corpus_exclusion_reason"] == "duplicate_within_observation"
    assert loser["duplicate_reason"] in {"duplicate_host_variant", "duplicate_url_variant"}


def test_http_https_same_timepoint_deduped():
    pages = [
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "http://example.com/ueber-uns",
            "hostname": "example.com",
            "path": "/ueber-uns",
            "page_category": "company_about",
            "main_text": "Über uns: familiengeführtes Unternehmen.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 1,
        },
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://example.com/ueber-uns",
            "hostname": "example.com",
            "path": "/ueber-uns",
            "page_category": "company_about",
            "main_text": "Über uns: familiengeführtes Unternehmen.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 2,
        },
    ]
    out = deduplicate_within_observations(pages)
    assert sum(1 for r in out if r["duplicate_content_flag"]) == 1


def test_cross_timepoint_content_preserved():
    text = "Unveränderte Familienkommunikation über Jahre hinweg."
    pages = [
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://example.com/werte",
            "path": "/werte",
            "page_category": "family_values",
            "main_text": text,
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 1,
        },
        {
            "firm_id": "1",
            "relative_timepoint": "post_event",
            "original_archived_url": "https://example.com/werte",
            "path": "/werte",
            "page_category": "family_values",
            "main_text": text,
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 1,
        },
    ]
    out = deduplicate_within_observations(pages)
    assert all(not r["duplicate_content_flag"] for r in out)
    assert all(r["branding_corpus_eligible"] for r in out)


def test_same_title_different_content_kept():
    pages = [
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://example.com/a",
            "document_title": "Unternehmen",
            "path": "/a",
            "page_category": "company_about",
            "main_text": "Text A über Geschichte der Familie.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 1,
        },
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://example.com/b",
            "document_title": "Unternehmen",
            "path": "/b",
            "page_category": "company_about",
            "main_text": "Text B über aktuelle Produkte und Märkte.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 2,
        },
    ]
    out = deduplicate_within_observations(pages)
    assert all(not r["duplicate_content_flag"] for r in out)


def test_canonical_selection_deterministic():
    pages = [
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://www.example.com/news/x",
            "hostname": "www.example.com",
            "path": "/news/x",
            "page_category": "news_press",
            "main_text": "Identischer Inhalt für Determinismus.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 9,
        },
        {
            "firm_id": "1",
            "relative_timepoint": "pre_event",
            "original_archived_url": "https://example.com/ueber-uns",
            "hostname": "example.com",
            "path": "/ueber-uns",
            "page_category": "company_about",
            "main_text": "Identischer Inhalt für Determinismus.",
            "branding_corpus_eligible": True,
            "usable_for_analysis": True,
            "crawl_budget_position": 3,
        },
    ]
    out1 = deduplicate_within_observations(pages)
    out2 = deduplicate_within_observations(pages)
    winner1 = next(r for r in out1 if not r["duplicate_content_flag"])
    winner2 = next(r for r in out2 if not r["duplicate_content_flag"])
    assert winner1["original_archived_url"] == winner2["original_archived_url"]
    assert "ueber-uns" in winner1["original_archived_url"]
