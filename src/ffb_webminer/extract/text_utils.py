"""Centralized text normalization and token counting."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß0-9]+(?:[-/][A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß0-9]+)*")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class TextStats:
    normalized_text: str
    character_count: int
    word_count: int
    token_count: int
    token_count_reason: str | None


def normalize_analysis_text(text: str | None) -> str:
    if text is None:
        return ""
    if isinstance(text, float) and text != text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return ""
    normalized = html.unescape(text)
    normalized = normalized.replace("\xa0", " ")
    normalized = WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def lexical_tokens(text: str | None) -> list[str]:
    normalized = normalize_analysis_text(text)
    return TOKEN_RE.findall(normalized)


def compute_text_stats(text: str | None) -> TextStats:
    normalized = normalize_analysis_text(text)
    tokens = lexical_tokens(normalized)
    token_reason = None
    if normalized and not tokens:
        token_reason = "no_lexical_tokens"
    return TextStats(
        normalized_text=normalized,
        character_count=len(normalized),
        word_count=len(tokens),
        token_count=len(tokens),
        token_count_reason=token_reason,
    )
