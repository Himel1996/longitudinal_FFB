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
    }
    base.update(overrides)
    return base


def test_classify_privacy_page_excludes_branding():
    result = classify_page(_row(path="/datenschutz", page_priority_reason="branding_score:5", document_title="Datenschutzerklärung"))
    assert result.page_category == "privacy_policy"
    assert result.branding_corpus_eligible is False
    assert result.branding_corpus_exclusion_reason == "privacy_policy"


def test_classify_impressum_keeps_governance_only():
    result = classify_page(_row(path="/impressum", page_priority_reason="branding_score:5", document_title="Impressum"))
    assert result.page_category == "impressum"
    assert result.branding_corpus_eligible is False
    assert result.governance_metadata_eligible is True


def test_contact_page_requires_substantive_text():
    result = classify_page(_row(path="/kontakt", page_priority_reason="branding_score:5", main_text="Kontakt Musterstraße 1 12345 Bonn"))
    assert result.page_category == "contact"
    assert result.branding_corpus_eligible is False

    result2 = classify_page(_row(path="/kontakt", page_priority_reason="branding_score:5", main_text="Kontaktieren Sie unser familiengeführtes Unternehmen mit Geschichte, Werten und internationaler Ausrichtung über unser Team in Bonn für Rückfragen zu Leistungen und Unternehmen."))
    assert result2.page_category == "contact"
    assert result2.branding_corpus_eligible is True
