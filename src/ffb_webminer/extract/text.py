"""Multi-stage main text extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import trafilatura
from readability import Document

from ffb_webminer.extract.language_detection import detect_page_language
from ffb_webminer.extract.text_utils import compute_text_stats

logger = logging.getLogger(__name__)

WAYBACK_TOOLBAR_RE = re.compile(
    r"(wayback|archive\.org|screenshot|toolbar)",
    re.IGNORECASE,
)

NAV_TAGS = frozenset({"nav", "header", "footer", "aside", "menu"})
NAV_CLASS_RE = re.compile(
    r"(nav|menu|footer|header|sidebar|breadcrumb|sprunglink|servicehead|menuhead)",
    re.IGNORECASE,
)
CONTENT_SELECTORS = [
    "#inhalt",
    ".colInhalt",
    ".contWrap",
    "#content",
    "#main",
    "main",
    "article",
    "[role=main]",
    ".main-content",
    ".content",
    ".frame-content",
]

FAMILY_TERMS = re.compile(
    r"\b(familie|familiengeführt|familiengefuehrt|generation|nachfolge|mittelständ|"
    r"mittelstaend|unternehmer|inhaber|holding|tradition|geschichte|historie)\b",
    re.IGNORECASE,
)

MIN_STAGE_WORDS = 80
LOW_QUALITY_SCORE = 0.35


@dataclass
class TextExtraction:
    main_text: str | None
    visible_text: str | None
    extracted_text: str | None
    extraction_method: str | None
    text_language: str | None
    text_language_confidence: float | None
    text_language_method: str | None
    text_language_reason: str | None
    character_count: int
    word_count: int
    token_count: int
    token_count_reason: str | None
    lexical_token_count: int | None
    analysis_token_count: int | None
    tokenization_status: str | None
    tokenization_method: str | None
    extraction_quality_score: float | None
    boilerplate_ratio: float | None
    archive_toolbar_removed_flag: bool


@dataclass
class _StageCandidate:
    text: str
    method: str
    score: float
    boilerplate_ratio: float | None
    lang: str | None = None


def extract_text(
    html: bytes,
    primary: str = "trafilatura",
    fallback: str = "readability",
    replay_url: str | None = None,
    language_min_chars: int = 80,
    language_confidence_threshold: float = 0.80,
) -> TextExtraction:
    """Run staged extraction and return the highest-quality candidate."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    visible_raw = soup.get_text(" ", strip=True) if soup else ""
    visible_text, toolbar_removed = _strip_wayback_noise(visible_raw)

    candidates: list[_StageCandidate] = []

    # Stage A: trafilatura
    if primary == "trafilatura":
        cand = _stage_trafilatura(html)
        if cand:
            candidates.append(cand)

    # Stage B: readability
    if fallback == "readability":
        cand = _stage_readability(html)
        if cand:
            candidates.append(cand)

    # Stage C: visible DOM with nav stripping
    cand = _stage_visible_dom(soup)
    if cand:
        candidates.append(cand)

    # Stage D: Playwright rendered DOM (optional)
    if replay_url:
        cand = _stage_playwright(replay_url)
        if cand:
            candidates.append(cand)

    best = _pick_best(candidates, visible_raw)

    if not best:
        return TextExtraction(
            main_text=None,
            visible_text=visible_text or None,
            extracted_text=None,
            extraction_method=None,
            text_language=None,
            text_language_confidence=None,
            text_language_method=None,
            text_language_reason="empty_text",
            character_count=0,
            word_count=0,
            token_count=0,
            token_count_reason="empty_text",
            lexical_token_count=0,
            analysis_token_count=0,
            tokenization_status="empty",
            tokenization_method="none",
            extraction_quality_score=0.0,
            boilerplate_ratio=None,
            archive_toolbar_removed_flag=toolbar_removed,
        )

    main_text, removed = _strip_wayback_noise(best.text)
    toolbar_removed = toolbar_removed or removed
    lang = detect_page_language(
        main_text,
        min_chars=language_min_chars,
        confidence_threshold=language_confidence_threshold,
    )
    stats = compute_text_stats(main_text, language_hint=lang.language)
    return TextExtraction(
        main_text=stats.normalized_text,
        visible_text=visible_text or None,
        extracted_text=stats.normalized_text,
        extraction_method=best.method,
        text_language=lang.language,
        text_language_confidence=lang.confidence,
        text_language_method=lang.method,
        text_language_reason=lang.reason,
        character_count=stats.character_count,
        word_count=stats.word_count,
        token_count=stats.token_count,
        token_count_reason=stats.token_count_reason,
        lexical_token_count=stats.lexical_token_count,
        analysis_token_count=stats.analysis_token_count,
        tokenization_status=stats.tokenization_status,
        tokenization_method=stats.tokenization_method,
        extraction_quality_score=best.score,
        boilerplate_ratio=best.boilerplate_ratio,
        archive_toolbar_removed_flag=toolbar_removed,
    )


def _stage_trafilatura(html: bytes) -> _StageCandidate | None:
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    if not text or len(text.strip()) < 20:
        return None
    lang = None
    meta = trafilatura.extract_metadata(html)
    if meta:
        lang = meta.language
    score, br = _score_text(text, html)
    return _StageCandidate(text=text.strip(), method="trafilatura", score=score, boilerplate_ratio=br, lang=lang)


def _stage_readability(html: bytes) -> _StageCandidate | None:
    from bs4 import BeautifulSoup

    try:
        doc = Document(html.decode("utf-8", errors="replace"))
        summary = doc.summary()
        if not summary:
            return None
        text = BeautifulSoup(summary, "lxml").get_text("\n", strip=True)
        if len(text) < 20:
            return None
        score, br = _score_text(text, html)
        return _StageCandidate(text=text, method="readability", score=score, boilerplate_ratio=br)
    except Exception as exc:
        logger.debug("readability stage failed: %s", exc)
        return None


def _stage_visible_dom(soup) -> _StageCandidate | None:
    from bs4 import BeautifulSoup

    work = BeautifulSoup(str(soup), "lxml")
    _remove_boilerplate_nodes(work)

    # Prefer known content containers
    for selector in CONTENT_SELECTORS:
        node = work.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text.split()) >= 15:
                html_bytes = str(work).encode("utf-8")
                score, br = _score_text(text, html_bytes)
                return _StageCandidate(
                    text=_dedupe_lines(text),
                    method="visible_dom",
                    score=score,
                    boilerplate_ratio=br,
                )

    body = work.body
    if not body:
        return None
    text = body.get_text("\n", strip=True)
    text = _dedupe_lines(text)
    if len(text.split()) < 15:
        return None
    html_bytes = str(work).encode("utf-8")
    score, br = _score_text(text, html_bytes)
    return _StageCandidate(text=text, method="visible_dom", score=score, boilerplate_ratio=br)


def _stage_playwright(replay_url: str) -> _StageCandidate | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(replay_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            text = page.inner_text("body")
            browser.close()
        if not text or len(text.split()) < 15:
            return None
        text = _dedupe_lines(text)
        score, br = _score_text(text, text.encode("utf-8"))
        # Slight penalty vs static DOM to prefer cheaper stages when comparable
        return _StageCandidate(
            text=text,
            method="playwright",
            score=round(score * 0.95, 3),
            boilerplate_ratio=br,
        )
    except Exception as exc:
        logger.debug("playwright stage failed: %s", exc)
        return None


def _remove_boilerplate_nodes(soup) -> None:
    for tag_name in NAV_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    for tag in soup.find_all(True):
        if not getattr(tag, "attrs", None):
            continue
        classes = " ".join(tag.get("class") or [])
        tag_id = tag.get("id") or ""
        if NAV_CLASS_RE.search(classes) or NAV_CLASS_RE.search(tag_id):
            tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"\bhide\b", re.I)):
        tag.decompose()


def _dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        norm = " ".join(line.split())
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return "\n".join(out)


def _pick_best(candidates: list[_StageCandidate], visible_raw: str) -> _StageCandidate | None:
    if not candidates:
        return None
    # Prefer higher score; tie-break by word count
    return max(candidates, key=lambda c: (c.score, len(c.text.split())))


def _score_text(text: str, html: bytes) -> tuple[float, float | None]:
    words = text.split()
    word_count = len(words)
    if word_count == 0:
        return 0.0, None

    from bs4 import BeautifulSoup

    full = BeautifulSoup(html, "lxml").get_text(" ", strip=True) if html else text
    br = round(1.0 - (len(text) / max(len(full), 1)), 3) if full else None

    length_score = min(1.0, word_count / 200)
    density = len(text) / max(len(html), 1)
    density_score = min(1.0, density * 8)
    family_bonus = min(0.15, len(FAMILY_TERMS.findall(text)) * 0.03)
    heading_bonus = 0.05 if re.search(r"^.{10,80}$", text.split("\n")[0], re.M) else 0.0
    nav_penalty = 0.2 if _navigation_heavy(words) else 0.0
    boilerplate_penalty = 0.15 if br is not None and br > 0.85 else 0.0
    address_penalty = 0.25 if re.search(r"\b\d{4,5}\b", text) and "Manager" in text else 0.0

    score = (
        length_score * 0.45
        + density_score * 0.2
        + family_bonus
        + heading_bonus
        - nav_penalty
        - boilerplate_penalty
        - address_penalty
    )
    return round(max(0.0, min(1.0, score)), 3), br


def _navigation_heavy(words: list[str]) -> bool:
    if len(words) < 30:
        return True
    nav_terms = {
        "home", "kontakt", "contact", "impressum", "datenschutz", "privacy",
        "login", "navigation", "menu", "sitemap",
    }
    hits = sum(1 for w in words[:50] if w.lower().strip(".,;:") in nav_terms)
    return hits >= 8 and len(words) < 120


def _strip_wayback_noise(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    filtered = [ln for ln in lines if not WAYBACK_TOOLBAR_RE.search(ln)]
    removed = len(filtered) != len(lines)
    return "\n".join(filtered).strip(), removed


def count_family_terms(text: str | None) -> int:
    if not text:
        return 0
    return len(FAMILY_TERMS.findall(text))
