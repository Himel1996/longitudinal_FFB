"""Reserved-slot crawl prioritization for family-branding pages."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from ffb_webminer.archive.wayback_url import unwrap_wayback_url
from ffb_webminer.crawl.language_paths import infer_path_language

LEGAL_MARKERS = (
    "impressum",
    "imprint",
    "datenschutz",
    "privacy",
    "agb",
    "terms",
    "cookie",
    "legal-notice",
    "rechtliches",
)

TIER1 = {
    "homepage": ("", "/"),
    "company_about": ("ueber-uns", "über-uns", "unternehmen", "about", "company"),
    "history_heritage": ("geschichte", "historie", "history", "heritage", "tradition"),
    "family_owners": ("familie", "family", "inhaber", "eigentümer", "eigentuemer", "owners"),
    "values_responsibility": ("werte", "values", "leitbild", "verantwortung", "responsibility", "nachhaltigkeit"),
    "management_leadership": (
        "management",
        "geschäftsführung",
        "geschaeftsfuehrung",
        "leadership",
        "holding",
        "organisation",
        "governance",
    ),
}

TIER2 = {
    "careers_employer": ("karriere", "careers", "jobs", "stellen", "employer"),
    "sustainability": ("nachhaltigkeit", "sustainability", "csr"),
    "news_press": ("presse", "press", "news", "aktuelles"),
    "regional": ("standort", "region", "local"),
}

TIER3 = {
    "products_services": ("produkte", "products", "services", "leistungen", "download"),
    "technical": ("technik", "technical", "support"),
}


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


def _path_of(url: str) -> str:
    return unquote(urlparse(unwrap_wayback_url(url)).path or "/").lower()


def classify_reserved_category(url: str, is_homepage: bool = False) -> tuple[int, str | None, int]:
    """Return (tier, category, score_bonus). Tier 1 best."""
    if is_homepage:
        return 1, "homepage", 1000
    path = _path_of(url)
    if path in {"", "/"}:
        return 1, "homepage", 1000

    # Legal/technical pages must never consume reserved branding slots
    if any(m in path for m in LEGAL_MARKERS):
        return 3, None, 10

    for category, markers in TIER1.items():
        if category == "homepage":
            continue
        if any(m in path for m in markers):
            return 1, category, 800 + (50 - min(len(path), 50))

    for category, markers in TIER2.items():
        if any(m in path for m in markers):
            return 2, category, 400 + (30 - min(len(path), 30))

    for category, markers in TIER3.items():
        if any(m in path for m in markers):
            return 3, category, 100 + (20 - min(len(path), 20))

    return 3, None, max(0, 40 - len(path))


def score_candidate(
    url: str,
    depth: int,
    is_homepage: bool = False,
) -> CrawlPriority:
    lang = infer_path_language(url)
    tier, category, bonus = classify_reserved_category(url, is_homepage=is_homepage)
    # Foreign paths cannot consume reserved German/high-value priority
    if lang.path_language_priority == "foreign_language_deprioritized":
        tier = max(tier, 3)
        bonus -= 500
        reason = f"foreign_deprioritized:{lang.language_path_reason}"
    elif tier == 1:
        reason = f"reserved_tier1:{category}"
    elif tier == 2:
        reason = f"secondary:{category}"
    else:
        reason = f"broad:{category or 'other'}"

    score = bonus - (depth * 20)
    if lang.path_language_priority == "preferred_german":
        score += 50
    return CrawlPriority(
        crawl_priority_tier=tier,
        crawl_priority_score=score,
        reserved_slot_category=category,
        selected_under_reserved_slot=False,
        crawl_selection_reason=reason,
        path_language_hint=lang.path_language_hint,
        path_language_priority=lang.path_language_priority,
        language_path_reason=lang.language_path_reason,
    )
