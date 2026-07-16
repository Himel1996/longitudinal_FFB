"""Offline language detection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from lingua import Language, LanguageDetectorBuilder

from ffb_webminer.extract.text_utils import normalize_analysis_text

SUPPORTED = [Language.GERMAN, Language.ENGLISH]
DETECTOR = LanguageDetectorBuilder.from_languages(*SUPPORTED).with_preloaded_language_models().build()


@dataclass
class LanguageResult:
    language: str
    confidence: float | None
    method: str
    reason: str | None


def detect_page_language(
    text: str | None,
    min_chars: int,
    confidence_threshold: float,
) -> LanguageResult:
    normalized = normalize_analysis_text(text)
    if len(normalized) < min_chars:
        return LanguageResult("unknown", None, "lingua", "insufficient_text")

    values = DETECTOR.compute_language_confidence_values(normalized)
    if not values:
        return LanguageResult("unknown", None, "lingua", "no_prediction")

    top = values[0]
    code = "de" if top.language == Language.GERMAN else "en" if top.language == Language.ENGLISH else "unknown"
    confidence = round(float(top.value), 4)
    if code == "unknown":
        return LanguageResult("unknown", confidence, "lingua", "unsupported_language")
    if confidence < confidence_threshold:
        return LanguageResult("unknown", confidence, "lingua", "low_confidence")
    return LanguageResult(code, confidence, "lingua", None)
