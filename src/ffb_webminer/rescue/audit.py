"""Non-targeted immutability and parent-release protection audits."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from ffb_webminer.rescue.paths import PARENT_RELEASE_NAME, assert_not_parent_release


COMPARE_COLS = [
    "observation_id",
    "firm_id",
    "relative_timepoint",
    "archive_timestamp",
    "canonical_original_url",
    "selected_capture_date",
    "n_pages",
    "branding_token_count",
    "tokens_de",
    "primary_language",
    "text_analysis_eligible",
    "german_text_analysis_eligible",
    "observation_recommendation",
]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def assert_parent_unchanged(parent_data: Path, expected_primary_sha256: str | None = None) -> dict[str, Any]:
    primary = parent_data / "full_sample_branding_corpus_observations_primary.csv"
    if not primary.exists():
        raise FileNotFoundError(f"missing parent primary corpus: {primary}")
    sha = file_sha256(primary)
    out = {"parent_primary_path": str(primary), "parent_primary_sha256": sha, "ok": True}
    if expected_primary_sha256 and sha != expected_primary_sha256:
        out["ok"] = False
        raise RuntimeError(
            f"parent release primary corpus hash changed: expected {expected_primary_sha256}, got {sha}"
        )
    return out


def audit_non_targeted_immutability(
    *,
    parent_obs: pd.DataFrame,
    rescue_obs: pd.DataFrame,
    targeted_firm_ids: set[str],
) -> dict[str, Any]:
    """Hard-fail on drift for firms not in the rescue target set."""
    targeted = {str(x) for x in targeted_firm_ids}
    p = parent_obs[parent_obs["firm_id"].astype(str).isin(set(parent_obs["firm_id"].astype(str)) - targeted)].copy()
    r = rescue_obs[rescue_obs["firm_id"].astype(str).isin(set(rescue_obs["firm_id"].astype(str)) - targeted)].copy()

    key = ["firm_id", "relative_timepoint"]
    for df in (p, r):
        for c in key:
            df[c] = df[c].astype(str)

    p = p.sort_values(key).reset_index(drop=True)
    r = r.sort_values(key).reset_index(drop=True)

    if len(p) != len(r):
        raise RuntimeError(
            f"non-targeted observation count drift: parent={len(p)} rescue={len(r)}"
        )

    cols = [c for c in COMPARE_COLS if c in p.columns and c in r.columns]
    mismatches: list[dict[str, Any]] = []
    for i in range(len(p)):
        for c in cols:
            pv = "" if pd.isna(p.at[i, c]) else str(p.at[i, c])
            rv = "" if pd.isna(r.at[i, c]) else str(r.at[i, c])
            if pv != rv:
                mismatches.append(
                    {
                        "firm_id": p.at[i, "firm_id"],
                        "relative_timepoint": p.at[i, "relative_timepoint"],
                        "column": c,
                        "parent": pv,
                        "rescue": rv,
                    }
                )
                if len(mismatches) >= 25:
                    break
        if len(mismatches) >= 25:
            break
    if mismatches:
        raise RuntimeError(f"non-targeted immutability failed: {mismatches[:5]}")
    return {"ok": True, "n_non_targeted": len(p), "compared_columns": cols}


def guard_release_destination(release_dir: Path, project_root: Path) -> None:
    assert_not_parent_release(release_dir, project_root=project_root)
    if release_dir.resolve().name == PARENT_RELEASE_NAME:
        raise RuntimeError(f"refusing to use parent release name as destination: {release_dir}")
