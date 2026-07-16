"""Transparent page classification and corpus eligibility rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

from ffb_webminer.extract.text_utils import normalize_analysis_text
from ffb_webminer.quality.checks import as_bool


@dataclass
class PageClassification:
    page_category: str
    page_category_reason: str
    branding_corpus_eligible: bool
    branding_corpus_exclusion_reason: str | None
    governance_metadata_eligible: bool


PATTERNS: dict[str, tuple[str, ...]] = {
    "impressum": ("impressum",),
    "privacy_policy": ("datenschutz", "datenschutzerklärung", "datenschutzerklaerung", "privacy", "privacy-policy"),
    "terms_conditions": ("agb", "allgemeine-geschäftsbedingungen", "allgemeine-geschaeftsbedingungen", "terms", "terms-and-conditions"),
    "cookie_notice": ("cookie", "cookies", "cookie-policy", "cookie-richtlinie"),
    "contact": ("kontakt", "contact", "anfahrt"),
    "company_about": ("ueber-uns", "über-uns", "about", "company", "unternehmen"),
    "history_heritage": ("geschichte", "historie", "history", "heritage", "tradition"),
    "family_values": ("familie", "family", "werte", "values", "leitbild"),
    "management_leadership": ("management", "geschäftsführung", "geschaeftsfuehrung", "leadership", "vorstand"),
    "careers_employer": ("karriere", "jobs", "stellen", "careers"),
    "news_press": ("news", "presse", "press", "aktuelles"),
    "products_services": ("produkte", "services", "leistungen", "solutions", "product"),
    "sustainability_responsibility": ("nachhaltigkeit", "sustainability", "responsibility", "verantwortung"),
    "technical_system": ("login", "admin", "wp-admin", "system"),
    "search_archive": ("suche", "search", "sitemap"),
}

LEGAL_EXCLUDE = {"privacy_policy", "terms_conditions", "cookie_notice", "legal_other", "technical_system", "search_archive", "navigation_only"}


def classify_page(row: dict) -> PageClassification:
    path = unquote(str(row.get("path") or "/")).lower()
    title = normalize_analysis_text(row.get("document_title")).lower()
    h1 = normalize_analysis_text(row.get("h1_text")).lower()
    h2 = normalize_analysis_text(row.get("h2_text")).lower()
    meta = normalize_analysis_text(row.get("meta_description")).lower()
    visible = normalize_analysis_text(row.get("visible_text")).lower()
    text = " ".join(part for part in (path, title, h1, h2, meta, visible[:1200]) if part)

    if str(row.get("page_priority_reason")) == "homepage" or path in ("", "/"):
        category = "homepage"
        reason = "homepage_path_or_priority"
    else:
        scores: dict[str, int] = {}
        for category_name, patterns in PATTERNS.items():
            hits = sum(1 for pat in patterns if pat in text)
            if hits:
                scores[category_name] = hits
        if row.get("likely_navigation_only"):
            scores["navigation_only"] = scores.get("navigation_only", 0) + 3
        if "wayback machine" in title or "internet archive" in visible[:500]:
            scores["search_archive"] = scores.get("search_archive", 0) + 3
        if "impressum" not in path and ("haftungsausschluss" in text or "disclaimer" in text or "rechtliche hinweise" in text):
            scores["legal_other"] = scores.get("legal_other", 0) + 2
        category = max(scores.items(), key=lambda kv: kv[1])[0] if scores else "unknown"
        reason = "pattern_hits"

    normalized_main = normalize_analysis_text(row.get("main_text"))
    has_substantive_text = len(normalized_main.split()) >= 20 or any(
        marker in normalized_main.lower()
        for marker in ("famil", "tradition", "werte", "innovation", "global", "unternehmen")
    )
    governance = category == "impressum" or category == "management_leadership"

    exclusion_reason = None
    branding_eligible = as_bool(row.get("usable_for_analysis"))
    if category in LEGAL_EXCLUDE:
        branding_eligible = False
        exclusion_reason = category
    elif category == "contact" and not has_substantive_text:
        branding_eligible = False
        exclusion_reason = "contact_low_substance"
    elif category == "impressum":
        branding_eligible = False
        exclusion_reason = "impressum"
    elif category == "unknown" and not has_substantive_text:
        branding_eligible = False
        exclusion_reason = "unknown_low_substance"

    return PageClassification(
        page_category=category,
        page_category_reason=reason,
        branding_corpus_eligible=branding_eligible,
        branding_corpus_exclusion_reason=exclusion_reason,
        governance_metadata_eligible=governance,
    )
