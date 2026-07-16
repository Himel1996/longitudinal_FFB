"""Rule-based governance metadata extraction from Impressum-like pages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ffb_webminer.extract.text_utils import normalize_analysis_text


@dataclass
class GovernanceExtraction:
    managing_directors_raw: str | None
    legal_representatives_raw: str | None
    legal_entity_raw: str | None
    parent_company_raw: str | None
    registered_address_raw: str | None
    registration_number_raw: str | None
    vat_id_raw: str | None
    extraction_confidence: float
    extraction_notes: str | None


PATTERNS = {
    "managing_directors_raw": re.compile(r"(geschäftsführer(?:in)?|managing director[s]?)\s*:? ?([^\n.;]{3,120})", re.I),
    "legal_representatives_raw": re.compile(r"(vertretungsberechtigt|represented by|vertreten durch)\s*:? ?([^\n.;]{3,120})", re.I),
    "legal_entity_raw": re.compile(r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß&\-. ]{2,100}\b(?:GmbH|AG|KG|GmbH & Co\. KG|Ltd\.|Inc\.))", re.I),
    "parent_company_raw": re.compile(r"(muttergesellschaft|parent company|holding)\s*:? ?([^\n.;]{3,120})", re.I),
    "registration_number_raw": re.compile(r"(handelsregister|hrb|hra|register number)\s*:? ?([A-Za-z0-9 \-/]{3,40})", re.I),
    "vat_id_raw": re.compile(r"(ust-?id|vat id|umsatzsteuer)\s*:? ?([A-Za-z0-9 \-]{6,40})", re.I),
}
ADDRESS_RE = re.compile(r"([A-Za-zÄÖÜäöüß.\- ]+\d+[a-zA-Z]?,? \d{4,5} [A-Za-zÄÖÜäöüß.\- ]+)")


def extract_governance_metadata(text: str | None) -> GovernanceExtraction:
    normalized = normalize_analysis_text(text)
    if not normalized:
        return GovernanceExtraction(None, None, None, None, None, None, None, 0.0, "empty_text")

    results: dict[str, str | None] = {key: None for key in (
        "managing_directors_raw",
        "legal_representatives_raw",
        "legal_entity_raw",
        "parent_company_raw",
        "registered_address_raw",
        "registration_number_raw",
        "vat_id_raw",
    )}
    notes: list[str] = []
    hits = 0
    for field, pattern in PATTERNS.items():
        match = pattern.search(normalized)
        if match:
            results[field] = (match.group(2) if match.lastindex and match.lastindex > 1 else match.group(1)).strip()
            hits += 1
    address_match = ADDRESS_RE.search(normalized)
    if address_match:
        results["registered_address_raw"] = address_match.group(1).strip()
        hits += 1
    if hits == 0:
        notes.append("raw_text_retained_only")
    confidence = round(min(1.0, hits / 4), 2)
    return GovernanceExtraction(
        managing_directors_raw=results["managing_directors_raw"],
        legal_representatives_raw=results["legal_representatives_raw"],
        legal_entity_raw=results["legal_entity_raw"],
        parent_company_raw=results["parent_company_raw"],
        registered_address_raw=results["registered_address_raw"],
        registration_number_raw=results["registration_number_raw"],
        vat_id_raw=results["vat_id_raw"],
        extraction_confidence=confidence,
        extraction_notes="; ".join(notes) if notes else None,
    )


def merge_governance_texts(texts: list[str]) -> str | None:
    cleaned = [normalize_analysis_text(t) for t in texts if normalize_analysis_text(t)]
    if not cleaned:
        return None
    return "\n\n".join(cleaned)


def json_list(values: list[str]) -> str | None:
    cleaned = [v for v in values if v]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None
