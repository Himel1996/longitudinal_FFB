from ffb_webminer.extract.language_detection import detect_page_language
from ffb_webminer.extract.text_utils import compute_text_stats, lexical_tokens, normalize_analysis_text


def test_tokenizer_handles_umlauts_and_hyphenated_compounds():
    stats = compute_text_stats("Familiengeführte Öl-&-Gas-Lösungen für Süddeutschland und Großküchen.")
    assert stats.token_count > 4
    assert "Familiengeführte" in normalize_analysis_text("Familiengeführte")


def test_tokenizer_decodes_html_entities():
    stats = compute_text_stats("M&uuml;ller &amp; S&ouml;hne wachsen in K&ouml;ln.")
    assert "Müller & Söhne wachsen in Köln." == stats.normalized_text
    assert stats.token_count >= 5


def test_tokenizer_ignores_punctuation_only():
    stats = compute_text_stats("... --- !!!")
    assert stats.token_count == 0
    assert stats.token_count_reason == "no_lexical_tokens"


def test_language_detection_german_and_unknown():
    de = detect_page_language(
        "Wir sind ein familiengeführtes Unternehmen mit Tradition, Verantwortung und Innovation in Deutschland.",
        min_chars=20,
        confidence_threshold=0.5,
    )
    assert de.language == "de"
    assert de.confidence is not None

    unknown = detect_page_language("Home Kontakt Impressum", min_chars=40, confidence_threshold=0.5)
    assert unknown.language == "unknown"
    assert unknown.reason == "insufficient_text"
