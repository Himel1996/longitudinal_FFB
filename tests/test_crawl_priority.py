"""Tests for reserved-slot crawl prioritization."""

from ffb_webminer.config import CrawlConfig
from ffb_webminer.crawl.priority import (
    classify_path_match,
    classify_reserved_category,
    normalize_path_segments,
    score_candidate,
)


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


def test_exact_unternehmen_qualifies():
    for url in (
        "https://example.com/unternehmen",
        "https://example.com/unternehmen/",
        "https://example.com/unternehmen/ueber-uns",
        "https://example.com/de/unternehmen.html",
        "https://example.com/company",
        "https://example.com/about",
        "https://example.com/ueber-uns",
        "http://msf-technik.de/UEber-uns.9.0.html",
        "http://www.msf-technik.de/UEber-uns.antriebstechnikdezentrale.0.html",
    ):
        m = classify_path_match(url)
        assert m.crawl_priority_tier == 1, url
        assert m.reserved_slot_category == "company_about", url
        assert m.eligible_for_reserved_slot is True, url
        assert m.priority_match_type == "exact_path_segment", url


def test_news_slug_unternehmen_does_not_qualify():
    news = score_candidate("https://example.com/news/unser-unternehmen-expandiert", depth=1)
    assert news.crawl_priority_tier == 2
    assert news.reserved_slot_category == "news_press"
    assert news.crawl_selection_reason.startswith("secondary:")


def test_karriere_unternehmen_does_not_consume_about_slot():
    careers = score_candidate(
        "https://example.com/karriere/arbeiten-in-unserem-unternehmen", depth=1
    )
    assert careers.crawl_priority_tier == 2
    assert careers.reserved_slot_category == "careers_employer"
    nested = score_candidate(
        "http://www.peter-lacke.de/deu/peter-lacke/unternehmen/karriere/karriere.html",
        depth=1,
    )
    assert nested.crawl_priority_tier == 2
    assert nested.reserved_slot_category == "careers_employer"
    assert nested.matched_priority_segment == "karriere"


def test_presse_unternehmen_des_jahres_does_not_qualify():
    press = score_candidate("https://example.com/presse/unternehmen-des-jahres", depth=1)
    assert press.crawl_priority_tier == 2
    assert press.reserved_slot_category == "news_press"


def test_newsletter_under_unternehmen_does_not_consume_about_slot():
    scored = score_candidate(
        "http://www.peter-lacke.de/deu/peter-lacke/unternehmen/pr-bereich/newsletter/newsletter.html",
        depth=1,
    )
    assert scored.crawl_priority_tier == 2
    assert scored.reserved_slot_category == "news_press"
    assert scored.matched_priority_segment in {"newsletter", "pr-bereich"}


def test_press_slug_containing_unternehmen_word_does_not_get_about_slot():
    url = (
        "https://www.bluemoon.de/pressemitteilungen/"
        "quo-vadis-social-media-in-der-shk-branche-blue-moon-befragte-40-unternehmen-"
        "das-neue-whitepaper-zur-grossen-umfrage"
    )
    scored = score_candidate(url, depth=1)
    assert scored.crawl_priority_tier == 2
    assert scored.reserved_slot_category == "news_press"
    assert scored.matched_priority_segment == "pressemitteilungen"


def test_unternehmen_philosophie_may_qualify():
    scored = score_candidate(
        "http://www.peter-lacke.de/kontakt/unternehmen/philosophie.html", depth=1
    )
    assert scored.crawl_priority_tier == 1
    assert scored.reserved_slot_category == "company_about"
    assert scored.matched_priority_segment == "unternehmen"


def test_path_segments_are_complete_tokens_only():
    segs = normalize_path_segments("/news/unser-unternehmen-expandiert")
    assert "news" in segs
    assert "unternehmen" not in segs
    assert "unser-unternehmen-expandiert" in segs


def test_crawl_order_deterministic_with_segment_rules():
    urls = [
        "https://example.com/news/unser-unternehmen-expandiert",
        "https://example.com/unternehmen",
        "https://example.com/karriere/arbeiten-in-unserem-unternehmen",
        "https://example.com/geschichte",
    ]
    a = sorted(urls, key=lambda u: (score_candidate(u, 1).crawl_priority_tier, -score_candidate(u, 1).crawl_priority_score, u))
    b = sorted(urls, key=lambda u: (score_candidate(u, 1).crawl_priority_tier, -score_candidate(u, 1).crawl_priority_score, u))
    assert a == b
    assert a[0].endswith("/geschichte") or a[0].endswith("/unternehmen")
