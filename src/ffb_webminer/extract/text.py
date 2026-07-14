"""Main text extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import trafilatura
from readability import Document

logger = logging.getLogger(__name__)

WAYBACK_TOOLBAR_RE = re.compile(
    r"(wayback|archive\.org|screenshot|toolbar)",
    re.IGNORECASE,
)


@dataclass
class TextExtraction:
    main_text: str | None
    visible_text: str | None
    extracted_text: str | None
    extraction_method: str | None
    text_language: str | None
    character_count: int
    word_count: int
    token_count: int
    extraction_quality_score: float | None
    boilerplate_ratio: float | None
    archive_toolbar_removed_flag: bool


def extract_text(html: bytes, primary: str = "trafilatura", fallback: str = "readability") -> TextExtraction:
    from bs4 import BeautifulSoup

    main_text = None
    method = None
    lang = None

    if primary == "trafilatura":
        main_text = trafilatura.extract(html, include_comments=False, include_tables=True)
        if main_text:
            method = "trafilatura"
            meta = trafilatura.extract_metadata(html)
            lang = meta.language if meta else None

    if not main_text and fallback == "readability":
        try:
            doc = Document(html.decode("utf-8", errors="replace"))
            summary = doc.summary()
            if summary:
                main_text = BeautifulSoup(summary, "lxml").get_text(" ", strip=True)
                method = "readability"
        except Exception as exc:
            logger.debug("readability fallback failed: %s", exc)

    soup = BeautifulSoup(html, "lxml")
    visible_text = soup.get_text(" ", strip=True) if soup else None

    toolbar_removed = False
    if main_text:
        main_text, removed = _strip_wayback_noise(main_text)
        toolbar_removed = toolbar_removed or removed
    if visible_text:
        visible_text, removed = _strip_wayback_noise(visible_text)
        toolbar_removed = toolbar_removed or removed

    char_count = len(main_text) if main_text else 0
    words = main_text.split() if main_text else []
    word_count = len(words)

    return TextExtraction(
        main_text=main_text,
        visible_text=visible_text,
        extracted_text=main_text,
        extraction_method=method,
        text_language=lang,
        character_count=char_count,
        word_count=word_count,
        token_count=word_count,
        extraction_quality_score=_quality_score(main_text, html) if main_text else 0.0,
        boilerplate_ratio=_boilerplate_ratio(main_text, html) if main_text else None,
        archive_toolbar_removed_flag=toolbar_removed,
    )


def _strip_wayback_noise(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    filtered = [ln for ln in lines if not WAYBACK_TOOLBAR_RE.search(ln)]
    removed = len(filtered) != len(lines)
    return "\n".join(filtered).strip(), removed


def _quality_score(text: str | None, html: bytes) -> float:
    if not text:
        return 0.0
    ratio = len(text) / max(len(html), 1)
    score = min(1.0, len(text) / 500) * 0.7 + min(1.0, ratio * 10) * 0.3
    return round(score, 3)


def _boilerplate_ratio(text: str | None, html: bytes) -> float | None:
    if not text:
        return None
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    full = soup.get_text(" ", strip=True)
    if not full:
        return None
    return round(1.0 - (len(text) / len(full)), 3)
