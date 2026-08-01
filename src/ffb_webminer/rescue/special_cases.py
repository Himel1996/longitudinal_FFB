"""Special-case metadata for Christian-identified Phase B firms."""

from __future__ import annotations

from typing import Any

# firm_id -> rule id
SPECIAL_CASE_RULES: dict[str, dict[str, Any]] = {
    "5": {
        "id": "msf_text_volume_threshold",
        "preserve_min_branding_tokens": True,
        "auto_promote_below_threshold": False,
    },
    "21": {
        "id": "freudenberg_sensitivity",
        "force_sensitivity": True,
        "auto_promote_to_primary": False,
        "record_migration": True,
    },
    "22": {
        "id": "stihl_sensitivity",
        "force_sensitivity": True,
        "auto_promote_to_primary": False,
        "record_migration": True,
    },
    "24": {
        "id": "viessmann_entity_change",
        "entity_change": True,
        "require_comparability_notes": True,
        "direct_comparability": False,
    },
    "30": {
        "id": "oetker_entity_change",
        "entity_change": True,
        "require_comparability_notes": True,
        "direct_comparability": False,
    },
}


def force_sensitivity_firm_ids() -> set[str]:
    return {fid for fid, rule in SPECIAL_CASE_RULES.items() if rule.get("force_sensitivity")}


def entity_change_firm_ids() -> set[str]:
    return {fid for fid, rule in SPECIAL_CASE_RULES.items() if rule.get("entity_change")}


def special_case_notes(firm_id: str) -> list[str]:
    rule = SPECIAL_CASE_RULES.get(str(firm_id))
    if not rule:
        return []
    notes = [str(rule["id"])]
    if rule.get("require_comparability_notes"):
        notes.append("comparability_not_assumed")
    if rule.get("force_sensitivity"):
        notes.append("sensitivity_only_unless_policy_allows")
    return notes
