"""Candidate-level comparison and replacement decisions for Phase B rescue."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ffb_webminer.quality.checks import as_bool


PRE = frozenset({"pre_pre_event", "pre_event"})
POST = frozenset({"post_event", "post_post_event"})


def _num(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _fit_rank(quality: Any) -> int:
    order = {"high": 0, "moderate": 1, "low": 2, "very_low": 3}
    return order.get(str(quality or "").lower(), 9)


def corpus_bucket(rec: Any, german_eligible: bool, text_eligible: bool) -> str:
    r = str(rec or "")
    if r == "include" and german_eligible:
        return "primary"
    if r in {"include", "sensitivity_analysis"} and (german_eligible or text_eligible):
        return "sensitivity"
    return "excluded"


def decide_rescue(
    *,
    firm_id: str,
    original_obs: pd.Series | None,
    rescue_obs: pd.Series | None,
    original_snap: pd.Series | None,
    rescue_snap: pd.Series | None,
    entity_change_flag: bool,
    migration_flag: bool,
    force_sensitivity_firms: set[str],
    min_branding_tokens: int,
    transport_failure: bool = False,
) -> dict[str, Any]:
    """Apply replacement policy using existing metrics only."""
    fid = str(firm_id)
    if transport_failure:
        packed = _pack(
            "transport_failure_resumable",
            "transport_failure_resumable",
            original_obs,
            rescue_obs,
            original_snap,
            rescue_snap,
            as_bool(original_obs.get("german_text_analysis_eligible")) if original_obs is not None else False,
            False,
            as_bool(original_obs.get("text_analysis_eligible")) if original_obs is not None else False,
            False,
            original_obs.get("observation_recommendation") if original_obs is not None else None,
            None,
            entity_change_flag,
            False,
            _num(original_obs.get("tokens_de") if original_obs is not None else 0),
            0.0,
            _num(original_obs.get("n_pages_de") if original_obs is not None else 0),
            0.0,
            original_snap.get("temporal_fit_quality") if original_snap is not None else None,
            None,
            _num(original_snap.get("temporal_distance_days") if original_snap is not None else None, default=10**9),
            10**9,
        )
        return packed
    o_ge = as_bool(original_obs.get("german_text_analysis_eligible")) if original_obs is not None else False
    r_ge = as_bool(rescue_obs.get("german_text_analysis_eligible")) if rescue_obs is not None else False
    o_te = as_bool(original_obs.get("text_analysis_eligible")) if original_obs is not None else False
    r_te = as_bool(rescue_obs.get("text_analysis_eligible")) if rescue_obs is not None else False
    o_tok_de = _num(original_obs.get("tokens_de") if original_obs is not None else 0)
    r_tok_de = _num(rescue_obs.get("tokens_de") if rescue_obs is not None else 0)
    o_pages_de = _num(original_obs.get("n_pages_de") if original_obs is not None else 0)
    r_pages_de = _num(rescue_obs.get("n_pages_de") if rescue_obs is not None else 0)
    o_rec = original_obs.get("observation_recommendation") if original_obs is not None else None
    r_rec = rescue_obs.get("observation_recommendation") if rescue_obs is not None else None
    o_fit = original_snap.get("temporal_fit_quality") if original_snap is not None else None
    r_fit = rescue_snap.get("temporal_fit_quality") if rescue_snap is not None else None
    o_dist = _num(original_snap.get("temporal_distance_days") if original_snap is not None else None, default=10**9)
    r_dist = _num(rescue_snap.get("temporal_distance_days") if rescue_snap is not None else None, default=10**9)
    o_status = str(original_snap.get("snapshot_status") if original_snap is not None else "")
    r_status = str(rescue_snap.get("snapshot_status") if rescue_snap is not None else "")

    # MSF threshold
    if fid == "5" and rescue_obs is not None:
        branding_tok = _num(rescue_obs.get("branding_token_count"))
        # German eligibility already encodes min branding tokens; explicit report fields:
        if r_ge and branding_tok < min_branding_tokens:
            r_ge = False
            r_te = False

    force_sens = fid in force_sensitivity_firms or (
        migration_flag and fid in {"21", "22"}
    ) or (r_fit == "very_low")

    decision = "remain_unavailable"
    reason = "no_usable_rescue"

    if r_status != "selected" or rescue_obs is None:
        if o_status == "selected" and (o_ge or o_te):
            decision, reason = "retain_original", "rescue_not_selected_or_missing"
        elif o_status == "selected":
            decision, reason = "retain_original", "rescue_not_selected_keep_original_structure"
        else:
            decision, reason = "remain_unavailable", "rescue_outside_tolerance_or_not_found"
            if r_status == "beyond_tolerance":
                decision, reason = "rejected_outside_tolerance", "rescue_beyond_tolerance"
        return _pack(
            decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
            o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
            o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
        )

    if not r_ge and not r_te:
        # insufficient text / wrong language
        excl = str(rescue_obs.get("german_text_analysis_exclusion_reason") or rescue_obs.get("text_analysis_exclusion_reason") or "")
        if "insufficient" in excl:
            decision, reason = "rejected_insufficient_text", excl or "insufficient_branding_tokens"
        elif "language" in excl or "german" in excl:
            decision, reason = "rejected_wrong_language", excl or "not_german_eligible"
        else:
            decision, reason = "rejected_insufficient_text", excl or "not_text_eligible"
        if o_status == "selected":
            # keep original alongside rejection
            pass
        return _pack(
            decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
            o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
            o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
        )

    # Entity change: do not auto-exclude; flag and prefer sensitivity alternative when risky
    if entity_change_flag and r_ge:
        if o_ge and _fit_rank(o_fit) <= _fit_rank(r_fit):
            decision, reason = "add_as_sensitivity_alternative", "entity_change_flagged_keep_original_primary_path"
        elif force_sens or not o_ge:
            decision, reason = "add_as_sensitivity_alternative", "entity_change_accepted_as_sensitivity"
        else:
            decision, reason = "manual_review_required", "entity_change_comparability"
        return _pack(
            decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
            o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, True,
            o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
        )

    # Freudenberg / STIHL sensitivity treatment
    if force_sens and r_ge:
        if o_ge and str(o_rec) == "include" and _fit_rank(o_fit) < _fit_rank(r_fit):
            decision, reason = "add_as_sensitivity_alternative", "migration_or_distance_sensitivity_keep_original"
        elif not o_ge:
            decision, reason = "replace_with_rescue", "rescue_german_eligible_forced_sensitivity_scope"
            # recommendation stays whatever enrich assigned; compare layer records sensitivity treatment
        else:
            decision, reason = "add_as_sensitivity_alternative", "forced_sensitivity_treatment"
        return _pack(
            decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
            o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, True,
            o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
        )

    # Temporal quality must be equal or better to replace
    if o_status == "selected" and o_ge:
        if _fit_rank(r_fit) > _fit_rank(o_fit):
            decision, reason = "add_as_sensitivity_alternative", "rescue_weaker_temporal_fit"
            return _pack(
                decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
                o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
                o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
            )
        if r_tok_de <= o_tok_de and r_pages_de <= o_pages_de:
            decision, reason = "retain_original", "rescue_not_better_german_evidence"
            return _pack(
                decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
                o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
                o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
            )
        decision, reason = "replace_with_rescue", "better_german_branding_within_equal_or_better_temporal"
        return _pack(
            decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
            o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
            o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
        )

    # Original missing German / unavailable
    if r_ge:
        decision, reason = "replace_with_rescue", "rescue_provides_german_where_original_lacked"
        return _pack(
            decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
            o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
            o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
        )

    decision, reason = "retain_original", "no_german_gain"
    return _pack(
        decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
        o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
        o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
    )


def _pack(
    decision, reason, original_obs, rescue_obs, original_snap, rescue_snap,
    o_ge, r_ge, o_te, r_te, o_rec, r_rec, entity_change_flag, force_sens,
    o_tok_de, r_tok_de, o_pages_de, r_pages_de, o_fit, r_fit, o_dist, r_dist,
) -> dict[str, Any]:
    return {
        "rescue_decision": decision,
        "rescue_decision_reason": reason,
        "original_german_text_eligible": bool(o_ge),
        "rescue_german_text_eligible": bool(r_ge),
        "original_text_analysis_eligible": bool(o_te),
        "rescue_text_analysis_eligible": bool(r_te),
        "original_observation_recommendation": o_rec,
        "rescue_observation_recommendation": r_rec,
        "original_primary_or_sensitivity": corpus_bucket(o_rec, o_ge, o_te),
        "rescue_primary_or_sensitivity": (
            "sensitivity" if force_sens and r_ge else corpus_bucket(r_rec, r_ge, r_te)
        ),
        "original_branding_tokens_de": o_tok_de,
        "rescue_branding_tokens_de": r_tok_de,
        "original_branding_pages_de": o_pages_de,
        "rescue_branding_pages_de": r_pages_de,
        "original_temporal_fit_quality": o_fit,
        "rescue_temporal_fit_quality": r_fit,
        "original_temporal_distance_days": None if o_dist >= 10**9 else o_dist,
        "rescue_temporal_distance_days": None if r_dist >= 10**9 else r_dist,
        "entity_change_flag": bool(entity_change_flag),
        "forced_sensitivity_treatment": bool(force_sens),
        "original_selected_capture": original_snap.get("selected_capture_date") if original_snap is not None else None,
        "rescue_selected_capture": rescue_snap.get("selected_capture_date") if rescue_snap is not None else None,
        "original_seed_url": original_snap.get("canonical_original_url") if original_snap is not None else None,
        "rescue_seed_url": (
            None
            if rescue_snap is None
            else (rescue_snap.get("rescue_seed_url") or rescue_snap.get("canonical_original_url"))
        ),
        "original_domain": None,
        "rescue_domain": rescue_snap.get("rescue_domain") if rescue_snap is not None else None,
    }
