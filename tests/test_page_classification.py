from ffb_webminer.quality.page_classification import classify_page


def _row(**overrides):
    base = {
        "path": "/",
        "page_priority_reason": "homepage",
        "document_title": "Company",
        "h1_text": "Company",
        "h2_text": "",
        "meta_description": "",
        "visible_text": "Welcome to our company with history values and services.",
        "main_text": "Welcome to our company with history values and services.",
        "usable_for_analysis": True,
        "likely_navigation_only": False,
        "normalized_url": "https://example.com/",
        "original_archived_url": "https://example.com/",
        "final_url": "https://example.com/",
        "canonical_url": "https://example.com/",
    }
    base.update(overrides)
    return base


def test_classify_privacy_page_excludes_branding():
    result = classify_page(
        _row(
            path="/datenschutz",
            page_priority_reason="branding_score:5",
            document_title="Datenschutzerklärung",
            original_archived_url="https://example.com/datenschutz",
            normalized_url="https://example.com/datenschutz",
        )
    )
    assert result.page_category == "privacy_policy"
    assert result.branding_corpus_eligible is False
    assert result.classification_rule_priority == 10
    assert result.governance_metadata_eligible is False


def test_christian_blue_moon_impressum_not_branding():
    result = classify_page(
        _row(
            path="/impressum",
            page_priority_reason="branding_score:5",
            document_title="Impressum | BLUE MOON",
            h1_text="News and products",
            visible_text="press news products services impressum datenschutz",
            original_archived_url="https://www.bluemoon.de/impressum",
            normalized_url="https://www.bluemoon.de/impressum",
            final_url="https://www.bluemoon.de/impressum/",
        )
    )
    assert result.page_category == "impressum"
    assert result.branding_corpus_eligible is False
    assert result.governance_metadata_eligible is True
    assert result.classification_rule_priority <= 30


def test_christian_peter_lacke_impressum_html():
    result = classify_page(
        _row(
            path="/deu/peter-lacke/impressum/impressum.html",
            page_priority_reason="branding_score:3",
            document_title="Unternehmen - Presse",
            h1_text="Produkte",
            visible_text="news presse produkte",
            original_archived_url="http://www.peter-lacke.de/deu/peter-lacke/impressum/impressum.html",
            normalized_url="http://www.peter-lacke.de/deu/peter-lacke/impressum/impressum.html",
        )
    )
    assert result.page_category == "impressum"
    assert result.branding_corpus_eligible is False
    assert result.governance_metadata_eligible is True


def test_christian_peter_lacke_agb_html():
    result = classify_page(
        _row(
            path="/deu/peter-lacke/agb/agb.html",
            page_priority_reason="branding_score:2",
            document_title="Kontakt und Produkte",
            h1_text="Services",
            visible_text="contact products services",
            original_archived_url="http://www.peter-lacke.de/deu/peter-lacke/agb/agb.html",
            normalized_url="http://www.peter-lacke.de/deu/peter-lacke/agb/agb.html",
        )
    )
    assert result.page_category == "terms_conditions"
    assert result.branding_corpus_eligible is False
    assert result.governance_metadata_eligible is False


def test_footer_impressum_mention_does_not_reclassify_homepage():
    result = classify_page(
        _row(
            path="/",
            page_priority_reason="homepage",
            document_title="BLUE MOON Home",
            visible_text="Welcome. Footer: Impressum Datenschutz AGB Cookie",
            main_text="Welcome to our family company with tradition and values.",
        )
    )
    assert result.page_category == "homepage"
    assert result.branding_corpus_eligible is True


def test_management_body_keyword_not_enough_for_governance():
    result = classify_page(
        _row(
            path="/produkte/lacksysteme",
            page_priority_reason="branding_score:4",
            document_title="Produkte",
            h1_text="Lacksysteme",
            visible_text="Unsere Produkte und das Management-Team stellen Lösungen vor.",
            original_archived_url="https://example.com/produkte/lacksysteme",
            normalized_url="https://example.com/produkte/lacksysteme",
        )
    )
    assert result.page_category == "products_services"
    assert result.governance_metadata_eligible is False


def test_contact_page_requires_substantive_text():
    result = classify_page(
        _row(
            path="/kontakt",
            page_priority_reason="branding_score:5",
            main_text="Kontakt Musterstraße 1 12345 Bonn",
            document_title="Kontakt",
            original_archived_url="https://example.com/kontakt",
            normalized_url="https://example.com/kontakt",
        )
    )
    assert result.page_category == "contact"
    assert result.branding_corpus_eligible is False

    result2 = classify_page(
        _row(
            path="/kontakt",
            page_priority_reason="branding_score:5",
            document_title="Kontakt",
            main_text=(
                "Kontaktieren Sie unser familiengeführtes Unternehmen mit Geschichte, "
                "Werten und internationaler Ausrichtung über unser Team in Bonn für "
                "Rückfragen zu Leistungen und Unternehmen."
            ),
            original_archived_url="https://example.com/kontakt",
            normalized_url="https://example.com/kontakt",
        )
    )
    assert result2.page_category == "contact"
    assert result2.branding_corpus_eligible is True
