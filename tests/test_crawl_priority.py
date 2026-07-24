"""Tests for reserved-slot crawl prioritization."""

from ffb_webminer.config import CrawlConfig
from ffb_webminer.crawl.priority import classify_reserved_category, score_candidate


def test_about_outranks_news():
    about = score_candidate("https://example.com/ueber-uns", depth=1)
    news = score_candidate("https://example.com/news/article-1", depth=1)
    assert about.crawl_priority_tier < news.crawl_priority_tier
    assert about.crawl_priority_score > news.crawl_priority_score


def test_history_outranks_products():
    history = score_candidate("https://example.com/geschichte", depth=1)
    products = score_candidate("https://example.com/produkte/xyz", depth=1)
    assert history.crawl_priority_tier == 1
    assert products.crawl_priority_tier == 3


def test_english_path_cannot_keep_reserved_tier():
    en_about = score_candidate("https://example.com/en/about", depth=1)
    assert en_about.path_language_priority == "foreign_language_deprioritized"
    assert en_about.crawl_priority_tier == 3


def test_homepage_category():
    tier, cat, _ = classify_reserved_category("https://example.com/", is_homepage=True)
    assert tier == 1
    assert cat == "homepage"


def test_deterministic_ordering():
    urls = [
        "https://example.com/news/a",
        "https://example.com/ueber-uns",
        "https://example.com/produkte/x",
        "https://example.com/geschichte",
    ]
    scored = sorted(
        [(u, score_candidate(u, depth=1)) for u in urls],
        key=lambda x: (x[1].crawl_priority_tier, -x[1].crawl_priority_score, x[0]),
    )
    assert "ueber-uns" in scored[0][0] or "geschichte" in scored[0][0]
    assert scored[0][1].crawl_priority_tier == 1
    assert scored[-1][1].crawl_priority_tier == 3


def test_reserved_slot_config_defaults():
    cfg = CrawlConfig()
    assert cfg.reserved_slots["homepage"] == 1
    assert sum(cfg.reserved_slots.values()) + sum(cfg.flexible_slots.values()) >= cfg.max_pages_per_snapshot


def test_legal_paths_do_not_consume_reserved_slots():
    impressum = score_candidate("https://example.com/unternehmen/impressum.html", depth=1)
    about = score_candidate("https://example.com/unternehmen", depth=1)
    assert impressum.crawl_priority_tier == 3
    assert impressum.reserved_slot_category is None
    assert about.crawl_priority_tier == 1
    assert about.reserved_slot_category == "company_about"
