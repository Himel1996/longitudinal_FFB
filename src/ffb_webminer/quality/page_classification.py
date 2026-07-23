"""Deterministic page classification with strict legal precedence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from ffb_webminer.extract.text_utils import normalize_analysis_text
from ffb_webminer.quality.checks import as_bool

# Priority tiers (lower = earlier / stronger)
PRIORITY_LEGAL = 10
PRIORITY_TECHNICAL = 20
PRIORITY_IMPRESSUM = 30
PRIORITY_BRANDING = 40
PRIORITY_FALLBACK = 50

BRANDING_EXCLUDE_CATEGORIES = {
    "impressum",
    "legal_notice",
    "privacy_policy",
    "terms_conditions",
    "cookie_notice",
    "legal_other",
    "technical_system",
    "search_archive",
    "navigation_only",
    "management_legal_representatives",
    "corporate_affiliation",
    "ownership_disclosure",
}

GOVERNANCE_CATEGORIES = {
    "impressum",
    "legal_notice",
    "management_legal_representatives",
    "corporate_affiliation",
    "ownership_disclosure",
}


@dataclass
class PageClassification:
    page_category: str
    page_category_reason: str
    branding_corpus_eligible: bool
    branding_corpus_exclusion_reason: str | None
    governance_metadata_eligible: bool
    classification_rule_priority: int
    classification_rule_id: str
    governance_inclusion_reason: str | None = None
    governance_rule_id: str | None = None
    governance_evidence_type: str | None = None


def _path_blob(row: dict) -> str:
    parts: list[str] = []
    for key in ("path", "normalized_url", "original_archived_url", "final_url", "canonical_url", "requested_url"):
        raw = row.get(key)
        if raw is None or (isinstance(raw, float) and raw != raw):
            continue
        text = unquote(str(raw)).lower()
        parts.append(text)
        try:
            parsed = urlparse(text if "://" in text else f"http://x{text if text.startswith('/') else '/' + text}")
            if parsed.path:
                parts.append(unquote(parsed.path).lower())
        except Exception:
            pass
    return " | ".join(parts)


def _title_blob(row: dict) -> str:
    return " ".join(
        normalize_analysis_text(row.get(key)).lower()
        for key in ("document_title", "h1_text", "og_title", "meta_description")
        if row.get(key) is not None
    )


def _path_token_match(path_blob: str, tokens: tuple[str, ...]) -> str | None:
    """Match legal/admin tokens against URL/path evidence only (not body text)."""
    for token in tokens:
        # path segment or filename forms: /token, /token/, token.html, token.php
        patterns = [
            rf"(^|/){re.escape(token)}(/|$|\.html|\.htm|\.php|\.asp|\.aspx)",
            rf"(^|/){re.escape(token)}\.",
        ]
        for pat in patterns:
            if re.search(pat, path_blob):
                return token
        # also allow bare filename-like hits in archived paths
        if f"/{token}" in path_blob or path_blob.endswith(token):
            return token
    return None


def _title_token_match(title_blob: str, tokens: tuple[str, ...]) -> str | None:
    for token in tokens:
        # whole-word-ish for short tokens like agb
        if len(token) <= 4:
            if re.search(rf"(^|[^a-z0-9]){re.escape(token)}([^a-z0-9]|$)", title_blob):
                return token
        elif token in title_blob:
            return token
    return None


PRIVACY_PATH = (
    "datenschutz",
    "datenschutzerklaerung",
    "datenschutzerklärung",
    "privacy-policy",
    "privacy",
)
TERMS_PATH = (
    "agb",
    "allgemeine-geschaeftsbedingungen",
    "allgemeine-geschäftsbedingungen",
    "nutzungsbedingungen",
    "terms-and-conditions",
    "terms",
)
COOKIE_PATH = ("cookie-richtlinie", "cookie-policy", "cookies", "cookie")
LEGAL_OTHER_PATH = (
    "rechtliche-hinweise",
    "rechtliches",
    "haftungsausschluss",
    "disclaimer",
)
IMPRESSUM_PATH = ("impressum", "imprint", "legal-notice", "legalnotice")
TECHNICAL_PATH = ("login", "admin", "wp-admin", "system")
SEARCH_PATH = ("suche", "search", "sitemap")

PRIVACY_TITLE = ("datenschutz", "datenschutzerklärung", "datenschutzerklaerung", "privacy policy", "privacy")
TERMS_TITLE = (
    "agb",
    "allgemeine geschäftsbedingungen",
    "allgemeine geschaeftsbedingungen",
    "nutzungsbedingungen",
    "terms and conditions",
    "terms of use",
    "terms",
)
COOKIE_TITLE = ("cookie", "cookies", "cookie-richtlinie", "cookie policy")
LEGAL_OTHER_TITLE = ("rechtliche hinweise", "rechtliches", "haftungsausschluss", "disclaimer")
IMPRESSUM_TITLE = ("impressum", "imprint", "legal notice", "legal-notice")

MANAGEMENT_LEGAL_PATH = (
    "geschaeftsfuehrung",
    "geschäftsführung",
    "geschaeftsfuehrer",
    "geschäftsführer",
    "legal-representatives",
    "legal_representatives",
    "vertretungsberechtigt",
    "vorstand",
    "aufsichtsrat",
)
MANAGEMENT_LEGAL_TITLE = (
    "geschäftsführung",
    "geschaeftsfuehrung",
    "geschäftsführer",
    "geschaeftsfuehrer",
    "legal representatives",
    "vertretungsberechtigt",
    "vertreten durch",
    "vorstand",
    "aufsichtsrat",
    "managing director",
)
AFFILIATION_PATH = ("muttergesellschaft", "parent-company", "unternehmensgruppe", "shareholder", "gesellschafter")
AFFILIATION_TITLE = ("muttergesellschaft", "parent company", "gesellschafter", "shareholder", "beteiligung")
OWNERSHIP_PATH = ("eigentuemer", "eigentümer", "ownership", "inhaber")
OWNERSHIP_TITLE = ("eigentümer", "eigentuemer", "ownership", "inhaberstruktur")

BRANDING_PATTERNS: dict[str, tuple[str, ...]] = {
    "contact": ("kontakt", "contact", "anfahrt"),
    "company_about": ("ueber-uns", "über-uns", "about", "company", "unternehmen"),
    "history_heritage": ("geschichte", "historie", "history", "heritage", "tradition"),
    "family_values": ("familie", "family", "werte", "values", "leitbild"),
    "management_leadership": ("management", "leadership"),
    "careers_employer": ("karriere", "jobs", "stellen", "careers"),
    "news_press": ("news", "presse", "press", "aktuelles"),
    "products_services": ("produkte", "services", "leistungen", "solutions", "product"),
    "sustainability_responsibility": ("nachhaltigkeit", "sustainability", "responsibility", "verantwortung"),
}


def _match_strict_legal(path_blob: str, title_blob: str) -> tuple[str, str, int, str] | None:
    # Privacy
    hit = _path_token_match(path_blob, PRIVACY_PATH) or _title_token_match(title_blob, PRIVACY_TITLE)
    if hit:
        return "privacy_policy", f"strict_legal:{hit}", PRIORITY_LEGAL, "legal.privacy"
    # Terms / AGB
    hit = _path_token_match(path_blob, TERMS_PATH) or _title_token_match(title_blob, TERMS_TITLE)
    if hit:
        return "terms_conditions", f"strict_legal:{hit}", PRIORITY_LEGAL, "legal.terms"
    # Cookies
    hit = _path_token_match(path_blob, COOKIE_PATH) or _title_token_match(title_blob, COOKIE_TITLE)
    if hit:
        return "cookie_notice", f"strict_legal:{hit}", PRIORITY_LEGAL, "legal.cookie"
    # Other legal notices (not impressum)
    hit = _path_token_match(path_blob, LEGAL_OTHER_PATH) or _title_token_match(title_blob, LEGAL_OTHER_TITLE)
    if hit:
        return "legal_other", f"strict_legal:{hit}", PRIORITY_LEGAL, "legal.other"
    return None


def _match_technical(path_blob: str, title_blob: str, row: dict) -> tuple[str, str, int, str] | None:
    hit = _path_token_match(path_blob, TECHNICAL_PATH)
    if hit:
        return "technical_system", f"strict_technical:{hit}", PRIORITY_TECHNICAL, "tech.system"
    hit = _path_token_match(path_blob, SEARCH_PATH)
    if hit:
        return "search_archive", f"strict_search:{hit}", PRIORITY_TECHNICAL, "tech.search"
    if "wayback machine" in title_blob or "internet archive" in title_blob:
        return "search_archive", "strict_search:wayback_title", PRIORITY_TECHNICAL, "tech.search_wayback"
    if as_bool(row.get("likely_navigation_only")):
        return "navigation_only", "strict_technical:navigation_only", PRIORITY_TECHNICAL, "tech.navigation_only"
    return None


def _match_impressum(path_blob: str, title_blob: str) -> tuple[str, str, int, str] | None:
    hit = _path_token_match(path_blob, IMPRESSUM_PATH)
    if hit:
        category = "legal_notice" if hit in {"imprint", "legal-notice", "legalnotice"} else "impressum"
        return category, f"strict_impressum:{hit}", PRIORITY_IMPRESSUM, "gov.impressum_path"
    hit = _title_token_match(title_blob, IMPRESSUM_TITLE)
    if hit:
        category = "legal_notice" if hit in {"imprint", "legal notice", "legal-notice"} else "impressum"
        return category, f"strict_impressum_title:{hit}", PRIORITY_IMPRESSUM, "gov.impressum_title"
    return None


def _match_governance_dedicated(path_blob: str, title_blob: str) -> tuple[str, str, int, str] | None:
    """Strong URL/title/H1 evidence only — not body-text keyword hits."""
    hit = _path_token_match(path_blob, MANAGEMENT_LEGAL_PATH) or _title_token_match(title_blob, MANAGEMENT_LEGAL_TITLE)
    if hit:
        return (
            "management_legal_representatives",
            f"governance_management:{hit}",
            PRIORITY_IMPRESSUM,
            "gov.management_legal",
        )
    hit = _path_token_match(path_blob, AFFILIATION_PATH) or _title_token_match(title_blob, AFFILIATION_TITLE)
    if hit:
        return "corporate_affiliation", f"governance_affiliation:{hit}", PRIORITY_IMPRESSUM, "gov.affiliation"
    hit = _path_token_match(path_blob, OWNERSHIP_PATH) or _title_token_match(title_blob, OWNERSHIP_TITLE)
    if hit:
        return "ownership_disclosure", f"governance_ownership:{hit}", PRIORITY_IMPRESSUM, "gov.ownership"
    return None


def _match_allowlist(row: dict, allowlist: list[str] | None) -> tuple[str, str, int, str] | None:
    if not allowlist:
        return None
    path_blob = _path_blob(row)
    for entry in allowlist:
        token = str(entry).strip().lower()
        if token and token in path_blob:
            return "impressum", f"config_allowlist:{token}", PRIORITY_IMPRESSUM, "gov.allowlist"
    return None


def _match_branding(path_blob: str, title_blob: str, row: dict) -> tuple[str, str, int, str]:
    path = unquote(str(row.get("path") or "/")).lower()
    if str(row.get("page_priority_reason")) == "homepage" or path in ("", "/"):
        return "homepage", "homepage_path_or_priority", PRIORITY_BRANDING, "brand.homepage"

    # Prefer path/title evidence over body text for branding categories
    evidence = f"{path_blob} {title_blob}"
    scores: dict[str, int] = {}
    for category_name, patterns in BRANDING_PATTERNS.items():
        hits = sum(1 for pat in patterns if pat in evidence)
        if hits:
            scores[category_name] = hits
    if scores:
        category = max(scores.items(), key=lambda kv: kv[1])[0]
        return category, "branding_path_title_hits", PRIORITY_BRANDING, f"brand.{category}"

    # Weak body-text fallback only when no path/title branding signal
    visible = normalize_analysis_text(row.get("visible_text")).lower()[:800]
    body_scores: dict[str, int] = {}
    for category_name, patterns in BRANDING_PATTERNS.items():
        hits = sum(1 for pat in patterns if pat in visible)
        if hits:
            body_scores[category_name] = hits
    if body_scores:
        category = max(body_scores.items(), key=lambda kv: kv[1])[0]
        return category, "branding_body_fallback", PRIORITY_BRANDING, f"brand.body.{category}"

    return "unknown", "fallback_unknown", PRIORITY_FALLBACK, "fallback.unknown"


def _governance_fields(category: str, rule_id: str) -> tuple[bool, str | None, str | None, str | None]:
    if category not in GOVERNANCE_CATEGORIES:
        return False, None, None, None
    evidence = {
        "impressum": "impressum_url_title",
        "legal_notice": "legal_notice_url_title",
        "management_legal_representatives": "management_legal_url_title",
        "corporate_affiliation": "affiliation_url_title",
        "ownership_disclosure": "ownership_url_title",
    }.get(category, "governance_url_title")
    if rule_id == "gov.allowlist":
        evidence = "config_allowlist"
    return True, f"included_as_{category}", rule_id, evidence


def classify_page(row: dict, governance_allowlist: list[str] | None = None) -> PageClassification:
    path_blob = _path_blob(row)
    title_blob = _title_blob(row)

    matched = (
        _match_strict_legal(path_blob, title_blob)
        or _match_technical(path_blob, title_blob, row)
        or _match_impressum(path_blob, title_blob)
        or _match_allowlist(row, governance_allowlist)
        or _match_governance_dedicated(path_blob, title_blob)
        or _match_branding(path_blob, title_blob, row)
    )
    category, reason, priority, rule_id = matched

    normalized_main = normalize_analysis_text(row.get("main_text"))
    has_substantive_text = len(normalized_main.split()) >= 20 or any(
        marker in normalized_main.lower()
        for marker in ("famil", "tradition", "werte", "innovation", "global", "unternehmen")
    )

    branding_eligible = as_bool(row.get("usable_for_analysis"))
    exclusion_reason = None
    if category in BRANDING_EXCLUDE_CATEGORIES:
        branding_eligible = False
        exclusion_reason = category
    elif category == "contact" and not has_substantive_text:
        branding_eligible = False
        exclusion_reason = "contact_low_substance"
    elif category == "unknown" and not has_substantive_text:
        branding_eligible = False
        exclusion_reason = "unknown_low_substance"

    gov_eligible, gov_reason, gov_rule, gov_evidence = _governance_fields(category, rule_id)

    return PageClassification(
        page_category=category,
        page_category_reason=reason,
        branding_corpus_eligible=branding_eligible,
        branding_corpus_exclusion_reason=exclusion_reason,
        governance_metadata_eligible=gov_eligible,
        classification_rule_priority=priority,
        classification_rule_id=rule_id,
        governance_inclusion_reason=gov_reason,
        governance_rule_id=gov_rule,
        governance_evidence_type=gov_evidence,
    )
