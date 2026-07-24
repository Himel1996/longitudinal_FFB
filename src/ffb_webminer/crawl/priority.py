"""Reserved-slot crawl prioritization with path-segment-aware matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from ffb_webminer.archive.wayback_url import unwrap_wayback_url
from ffb_webminer.crawl.language_paths import infer_path_language

LEGAL_SEGMENTS = frozenset(
    {
        "impressum",
        "imprint",
        "datenschutz",
        "datenschutzerklaerung",
        "datenschutzerklärung",
        "privacy",
        "agb",
        "terms",
        "cookie",
        "cookies",
        "legal-notice",
        "legal_notice",
        "rechtliches",
        "disclaimer",
    }
)

TIER1_ALIASES: dict[str, frozenset[str]] = {
    "company_about": frozenset(
        {
            "unternehmen",
            "ueber-uns",
            "uber-uns",
            "über-uns",
            "about",
            "about-us",
            "aboutus",
            "company",
            "firma",
        }
    ),
    "history_heritage": frozenset(
        {"geschichte", "historie", "history", "heritage", "tradition"}
    ),
    "family_owners": frozenset(
        {"familie", "family", "inhaber", "eigentuemer", "eigentümer", "owners", "owner"}
    ),
    "values_responsibility": frozenset(
        {
            "werte",
            "values",
            "leitbild",
            "verantwortung",
            "responsibility",
            "nachhaltigkeit",
        }
    ),
    "management_leadership": frozenset(
        {
            "management",
            "geschaeftsfuehrung",
            "geschäftsführung",
            "leadership",
            "holding",
            "organisation",
            "organization",
            "governance",
        }
    ),
}

TIER2_ALIASES: dict[str, frozenset[str]] = {
    "careers_employer": frozenset(
        {"karriere", "careers", "career", "jobs", "stellen", "employer", "job"}
    ),
    "sustainability": frozenset({"nachhaltigkeit", "sustainability", "csr"}),
    "news_press": frozenset(
        {
            "presse",
            "press",
            "news",
            "newsletter",
            "newsletters",
            "aktuelles",
            "pressemitteilungen",
            "pressemitteilung",
            "newsroom",
            "pr-bereich",
            "medien",
            "media",
        }
    ),
    "regional": frozenset({"standort", "standorte", "region", "local"}),
}

TIER3_ALIASES: dict[str, frozenset[str]] = {
    "products_services": frozenset(
        {
            "produkte",
            "produkt",
            "products",
            "product",
            "services",
            "service",
            "leistungen",
            "download",
            "downloads",
        }
    ),
    "technical": frozenset({"technik", "technical", "support"}),
}

# Parent-like about segments that lose to careers/news/products siblings
WEAK_ABOUT_SEGMENTS = frozenset({"unternehmen", "company", "firma"})

BLOCK_RESERVED_SEGMENTS = (
    TIER2_ALIASES["careers_employer"]
    | TIER2_ALIASES["news_press"]
    | TIER3_ALIASES["products_services"]
)

STEM_EXT_RE = re.compile(r"\.(html?|php|aspx?|jsp|cfm)$", re.IGNORECASE)
# Typo3-style pageid suffixes: Ueber-uns.9.0.html → ueber-uns
TYPO3_ID_STEM_RE = re.compile(r"^(.+?)(?:\.\d+)+$")


@dataclass
class PathMatch:
    crawl_priority_tier: int
    reserved_slot_category: str | None
    score_bonus: int
    matched_priority_segment: str | None
    priority_match_type: str
    priority_rule_id: str
    priority_match_confidence: str
    eligible_for_reserved_slot: bool


@dataclass
class CrawlPriority:
    crawl_priority_tier: int
    crawl_priority_score: int
    reserved_slot_category: str | None
    selected_under_reserved_slot: bool
    crawl_selection_reason: str
    path_language_hint: str
    path_language_priority: str
    language_path_reason: str
    matched_priority_segment: str | None = None
    priority_match_type: str | None = None
    priority_rule_id: str | None = None
    priority_match_confidence: str | None = None


def _path_of(url: str) -> str:
    return unquote(urlparse(unwrap_wayback_url(url)).path or "/").lower()


def normalize_path_segments(path: str) -> list[str]:
    """Return normalized path segments and filename stems (complete tokens only)."""
    raw = (path or "/").lower()
    if not raw.startswith("/"):
        raw = "/" + raw
    parts: list[str] = []
    for part in raw.split("/"):
        part = part.strip().split("?")[0].split("#")[0]
        if not part:
            continue
        parts.append(part)
        stem = STEM_EXT_RE.sub("", part)
        if stem and stem != part:
            parts.append(stem)
        # Delimited filename stems (Typo3 pageid / speaking-URL suffixes)
        for candidate in (stem, part):
            if not candidate or "." not in candidate:
                continue
            m = TYPO3_ID_STEM_RE.match(candidate)
            if m and m.group(1):
                parts.append(m.group(1))
            head = candidate.split(".", 1)[0]
            if head:
                parts.append(head)
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _segment_hits(segments: list[str], aliases: frozenset[str]) -> str | None:
    for seg in segments:
        if seg in aliases:
            return seg
    return None


def classify_path_match(url: str, is_homepage: bool = False) -> PathMatch:
    if is_homepage:
        return PathMatch(1, "homepage", 1000, "", "homepage_flag", "R_HOME_01", "high", True)

    path = _path_of(url)
    if path in {"", "/"}:
        return PathMatch(1, "homepage", 1000, "/", "root_path", "R_HOME_02", "high", True)

    segments = normalize_path_segments(path)

    legal_hit = _segment_hits(segments, LEGAL_SEGMENTS)
    if legal_hit:
        return PathMatch(
            3, None, 10, legal_hit, "legal_segment_exclusion", "R_LEGAL_01", "high", False
        )

    conflict = _segment_hits(segments, BLOCK_RESERVED_SEGMENTS)

    # Prefer explicit careers/news/products segments over weak parent about segments
    if conflict:
        for category, aliases in TIER2_ALIASES.items():
            hit = _segment_hits(segments, aliases)
            if hit:
                return PathMatch(
                    2,
                    category,
                    400 + (30 - min(len(path), 30)),
                    hit,
                    "exact_path_segment",
                    f"R_T2_SEG_{category}",
                    "high",
                    False,
                )
        for category, aliases in TIER3_ALIASES.items():
            hit = _segment_hits(segments, aliases)
            if hit:
                return PathMatch(
                    3,
                    category,
                    100 + (20 - min(len(path), 20)),
                    hit,
                    "exact_path_segment",
                    f"R_T3_SEG_{category}",
                    "high",
                    False,
                )

    for category, aliases in TIER1_ALIASES.items():
        hit = _segment_hits(segments, aliases)
        if not hit:
            continue
        if conflict and hit in WEAK_ABOUT_SEGMENTS and category == "company_about":
            # Should have been handled above; skip reserved assignment
            continue
        return PathMatch(
            1,
            category,
            800 + (50 - min(len(path), 50)),
            hit,
            "exact_path_segment",
            f"R_T1_SEG_{category}",
            "high",
            True,
        )

    for category, aliases in TIER2_ALIASES.items():
        hit = _segment_hits(segments, aliases)
        if hit:
            return PathMatch(
                2,
                category,
                400 + (30 - min(len(path), 30)),
                hit,
                "exact_path_segment",
                f"R_T2_SEG_{category}",
                "high",
                False,
            )

    for category, aliases in TIER3_ALIASES.items():
        hit = _segment_hits(segments, aliases)
        if hit:
            return PathMatch(
                3,
                category,
                100 + (20 - min(len(path), 20)),
                hit,
                "exact_path_segment",
                f"R_T3_SEG_{category}",
                "high",
                False,
            )

    return PathMatch(
        3, None, max(0, 40 - len(path)), None, "fallback_broad", "R_FALLBACK_01", "low", False
    )


def classify_reserved_category(url: str, is_homepage: bool = False) -> tuple[int, str | None, int]:
    m = classify_path_match(url, is_homepage=is_homepage)
    category = m.reserved_slot_category
    if m.crawl_priority_tier == 1 and not m.eligible_for_reserved_slot:
        category = None
    return m.crawl_priority_tier, category, m.score_bonus


def score_candidate(
    url: str,
    depth: int,
    is_homepage: bool = False,
) -> CrawlPriority:
    lang = infer_path_language(url)
    match = classify_path_match(url, is_homepage=is_homepage)

    tier = match.crawl_priority_tier
    bonus = match.score_bonus
    category = match.reserved_slot_category
    eligible_reserved = match.eligible_for_reserved_slot and tier == 1

    if lang.path_language_priority == "foreign_language_deprioritized":
        tier = max(tier, 3)
        bonus -= 500
        eligible_reserved = False
        category = None if tier == 1 else category
        reason = f"foreign_deprioritized:{lang.language_path_reason}"
    elif eligible_reserved:
        reason = f"reserved_tier1:{category}"
    elif tier == 2:
        reason = f"secondary:{category or match.priority_rule_id}"
    else:
        reason = f"broad:{category or 'other'}"

    score = bonus - (depth * 20)
    if lang.path_language_priority == "preferred_german":
        score += 50

    return CrawlPriority(
        crawl_priority_tier=tier,
        crawl_priority_score=score,
        reserved_slot_category=category if (eligible_reserved or tier >= 2) else None,
        selected_under_reserved_slot=False,
        crawl_selection_reason=reason,
        path_language_hint=lang.path_language_hint,
        path_language_priority=lang.path_language_priority,
        language_path_reason=lang.language_path_reason,
        matched_priority_segment=match.matched_priority_segment,
        priority_match_type=match.priority_match_type,
        priority_rule_id=match.priority_rule_id,
        priority_match_confidence=match.priority_match_confidence,
    )
