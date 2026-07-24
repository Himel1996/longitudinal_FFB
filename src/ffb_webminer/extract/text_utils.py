"""Centralized text normalization and token counting.

Token terminology
-----------------
- ``lexical_token_count``: Latin/German-style alphanumeric tokens (regex).
- ``analysis_token_count``: language-appropriate tokens used for corpus aggregation.
- ``token_count``: **alias of ``analysis_token_count``** (choice A — consistent aggregation).

For CJK text, analysis tokens are Unicode CJK ideograph characters
(``tokenization_method=unicode_cjk_chars``), which is deterministic and offline.
German/English continue to use lexical tokenization
(``tokenization_method=latin_lexical_regex``).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß0-9]+(?:[-/][A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß0-9]+)*")
WHITESPACE_RE = re.compile(r"\s+")
# CJK Unified Ideographs + Extension A + common punctuation-adjacent blocks used in web copy
CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


@dataclass
class TextStats:
    normalized_text: str
    character_count: int
    word_count: int
    token_count: int  # == analysis_token_count
    token_count_reason: str | None
    lexical_token_count: int = 0
    analysis_token_count: int = 0
    tokenization_status: str = "ok"
    tokenization_method: str = "latin_lexical_regex"


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


def cjk_chars(text: str | None) -> list[str]:
    normalized = normalize_analysis_text(text)
    return CJK_CHAR_RE.findall(normalized)


def compute_text_stats(text: str | None, language_hint: str | None = None) -> TextStats:
    normalized = normalize_analysis_text(text)
    lexical = lexical_tokens(normalized)
    cjk = cjk_chars(normalized)

    lang = (language_hint or "").lower()
    use_cjk = lang in {"zh", "zh-cn", "zh-tw", "ja", "ko", "chinese"} or (
        len(cjk) >= 8 and len(cjk) >= max(1, len(lexical)) * 2
    )

    if not normalized:
        return TextStats(
            normalized_text="",
            character_count=0,
            word_count=0,
            token_count=0,
            token_count_reason="empty_text",
            lexical_token_count=0,
            analysis_token_count=0,
            tokenization_status="empty",
            tokenization_method="none",
        )

    if use_cjk and cjk:
        analysis = cjk
        method = "unicode_cjk_chars"
        status = "ok"
        reason = None
        word_count = len(analysis)
    else:
        analysis = lexical
        method = "latin_lexical_regex"
        if analysis:
            status = "ok"
            reason = None
        else:
            # Substantive non-Latin without enough CJK detection, or punctuation-only
            if cjk:
                analysis = cjk
                method = "unicode_cjk_chars"
                status = "ok"
                reason = None
                word_count = len(analysis)
                return TextStats(
                    normalized_text=normalized,
                    character_count=len(normalized),
                    word_count=word_count,
                    token_count=len(analysis),
                    token_count_reason=reason,
                    lexical_token_count=len(lexical),
                    analysis_token_count=len(analysis),
                    tokenization_status=status,
                    tokenization_method=method,
                )
            status = "no_tokens"
            reason = "no_lexical_tokens"
        word_count = len(lexical)

    return TextStats(
        normalized_text=normalized,
        character_count=len(normalized),
        word_count=word_count,
        token_count=len(analysis),  # analysis_token_count alias
        token_count_reason=reason,
        lexical_token_count=len(lexical),
        analysis_token_count=len(analysis),
        tokenization_status=status,
        tokenization_method=method,
    )
