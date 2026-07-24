from ffb_webminer.extract.language_detection import detect_page_language
from ffb_webminer.extract.text_utils import compute_text_stats, lexical_tokens, normalize_analysis_text
from ffb_webminer.quality.checks import check_page
from ffb_webminer.config import QualityConfig


def test_tokenizer_handles_umlauts_and_hyphenated_compounds():
    stats = compute_text_stats("Familiengeführte Öl-&-Gas-Lösungen für Süddeutschland und Großküchen.")
    assert stats.token_count > 4
    assert stats.analysis_token_count == stats.token_count
    assert stats.tokenization_method == "latin_lexical_regex"
    assert "Familiengeführte" in normalize_analysis_text("Familiengeführte")


def test_tokenizer_decodes_html_entities():
    stats = compute_text_stats("M&uuml;ller &amp; S&ouml;hne wachsen in K&ouml;ln.")
    assert "Müller & Söhne wachsen in Köln." == stats.normalized_text
    assert stats.token_count >= 5


def test_tokenizer_ignores_punctuation_only():
    stats = compute_text_stats("... --- !!!")
    assert stats.token_count == 0
    assert stats.analysis_token_count == 0
    assert stats.token_count_reason == "no_lexical_tokens"


def test_tokenizer_empty_text():
    stats = compute_text_stats("")
    assert stats.token_count == 0
    assert stats.tokenization_status == "empty"


def test_english_text_tokens():
    stats = compute_text_stats("Family owned company with values and tradition.")
    assert stats.token_count >= 6
    assert stats.lexical_token_count == stats.analysis_token_count


def test_chinese_text_has_analysis_tokens():
    chinese = (
        "公司介绍 - 佩特涂料 我们是以创新和市场为导向的企业，自己拥有整套完备的关于涂料研发和生产的系统。"
    )
    stats = compute_text_stats(chinese, language_hint="zh")
    assert stats.character_count > 20
    assert stats.lexical_token_count == 0 or stats.lexical_token_count < stats.analysis_token_count
    assert stats.analysis_token_count > 0
    assert stats.token_count == stats.analysis_token_count
    assert stats.tokenization_method == "unicode_cjk_chars"
    assert stats.tokenization_status == "ok"


def test_mixed_script_prefers_cjk_when_dominant():
    mixed = "Company 公司介绍 企业成功的关键还在于与客户建立直接广泛的业务沟通。"
    stats = compute_text_stats(mixed)
    assert stats.analysis_token_count > 0
    assert stats.tokenization_method in {"unicode_cjk_chars", "latin_lexical_regex"}


def test_substantive_chinese_cannot_remain_usable_with_zero_analysis_tokens():
    chinese = (
        "公司介绍 - 佩特涂料 我们是以创新和市场为导向的企业，自己拥有整套完备的关于涂料研发和生产的系统。"
        "时时刻刻为客户服务是企业的宗旨。"
    )
    stats = compute_text_stats(chinese, language_hint="zh")
    page = {
        "http_status": 200,
        "fetch_error": None,
        "main_text": chinese,
        "character_count": stats.character_count,
        "token_count": stats.token_count,
        "analysis_token_count": stats.analysis_token_count,
        "registrable_domain": "peter-lacke.de",
        "temporal_distance_days": 10,
    }
    out = check_page(page, "peter-lacke.de", QualityConfig(min_text_chars=50))
    assert out["usable_for_analysis"] is True
    assert int(out["analysis_token_count"]) > 0


def test_zero_analysis_tokens_with_substantive_text_not_usable():
    page = {
        "http_status": 200,
        "fetch_error": None,
        "main_text": "........",
        "character_count": 80,
        "token_count": 0,
        "analysis_token_count": 0,
        "registrable_domain": "example.com",
        "temporal_distance_days": 10,
    }
    out = check_page(page, "example.com", QualityConfig(min_text_chars=50))
    assert out["usable_for_analysis"] is False
    assert out["exclusion_reason"] == "zero_analysis_tokens"


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
