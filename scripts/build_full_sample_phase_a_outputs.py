#!/usr/bin/env python3
"""Phase A analytical exports for full_sample_v1 (reporting only).

Reads the frozen release bundle and writes additional analytical tables /
documentation. Does not crawl, extract, regenerate observations, or modify
pipeline / crawler / existing corpus CSV contents.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "data" / "releases" / "full_sample_v1"
REL_DATA = REL / "data"
REL_REPORTS = REL / "reports"
ROOT_REPORTS = ROOT / "reports"
OUTPUT = ROOT / "data" / "output"

PRE_EVENT = frozenset({"pre_pre_event", "pre_event"})
POST_EVENT = frozenset({"post_event", "post_post_event"})

SENS_ALL_NAME = "full_sample_branding_corpus_observations_sensitivity.csv"
SENS_DE_NAME = "full_sample_branding_corpus_observations_sensitivity_de.csv"
PRIMARY_NAME = "full_sample_branding_corpus_observations_primary.csv"
OBS_NAME = "full_sample_observation_text_summary.csv"
FIRMS_NAME = "firms.csv"
COVERAGE_NAME = "firm_longitudinal_coverage.csv"


def as_bool(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])


def load_csv(name: str) -> pd.DataFrame:
    path = REL_DATA / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype=str)


def write_csv(df: pd.DataFrame, *paths: Path) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)


def build_sensitivity_de(sens: pd.DataFrame) -> pd.DataFrame:
    """Filter existing all-language sensitivity table by German eligibility flag."""
    if "german_text_analysis_eligible" not in sens.columns:
        raise KeyError("german_text_analysis_eligible missing from sensitivity export")
    out = sens.loc[as_bool(sens["german_text_analysis_eligible"])].copy()
    # Preserve exact column order from the source export.
    return out[list(sens.columns)]


def coverage_notes(
    *,
    n_pre_obs: int,
    n_post_obs: int,
    n_pre_de: int,
    n_post_de: int,
    n_german_any: int,
    n_primary: int,
    n_selected: int,
    n_unavailable: int,
    ready: bool,
) -> str:
    notes: list[str] = []
    if ready:
        if n_primary == 0 and n_german_any > 0:
            notes.append("sensitivity_only")
        return ";".join(notes) if notes else "ready"

    if n_german_any == 0:
        notes.append("no_german")
    if n_pre_de == 0:
        notes.append("missing_pre")
    if n_post_de == 0:
        notes.append("missing_post")
    if n_pre_obs == 0 and n_post_obs == 0 and n_unavailable > 0 and n_selected == 0:
        notes.append("unavailable")
    elif n_selected == 0 or (n_pre_obs + n_post_obs == 0 and n_unavailable > 0):
        notes.append("unavailable")
    if n_primary == 0 and n_german_any > 0:
        notes.append("sensitivity_only")

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ";".join(ordered) if ordered else "not_ready"


def build_firm_coverage(
    firms: pd.DataFrame,
    obs: pd.DataFrame,
    snaps: pd.DataFrame,
    primary: pd.DataFrame,
    sens: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    firm_ids = firms["firm_id"].astype(str).tolist()
    for firm_id in firm_ids:
        firm = firms.loc[firms["firm_id"].astype(str) == firm_id].iloc[0]
        o = obs.loc[obs["firm_id"].astype(str) == firm_id]
        s = snaps.loc[snaps["firm_id"].astype(str) == firm_id] if len(snaps) else pd.DataFrame()
        pre = o.loc[o["relative_timepoint"].isin(PRE_EVENT)]
        post = o.loc[o["relative_timepoint"].isin(POST_EVENT)]
        pre_de = pre.loc[as_bool(pre["german_text_analysis_eligible"])]
        post_de = post.loc[as_bool(post["german_text_analysis_eligible"])]
        german_any = o.loc[as_bool(o["german_text_analysis_eligible"])]
        n_primary = int((primary["firm_id"].astype(str) == firm_id).sum())
        n_sens = int((sens["firm_id"].astype(str) == firm_id).sum())
        n_selected = 0
        n_unavailable = 0
        if len(s) and "snapshot_status" in s.columns:
            status = s["snapshot_status"].fillna("").astype(str).str.lower()
            n_selected = int((status == "selected").sum())
            n_unavailable = int((status != "selected").sum())
        ready = len(pre_de) > 0 and len(post_de) > 0
        rows.append(
            {
                "firm_id": firm_id,
                "company": firm.get("company"),
                "event_year": firm.get("event_year"),
                "n_pre_event_observations": int(len(pre)),
                "n_post_event_observations": int(len(post)),
                "n_pre_event_german_eligible": int(len(pre_de)),
                "n_post_event_german_eligible": int(len(post_de)),
                "n_primary_observations": n_primary,
                "n_sensitivity_observations": n_sens,
                "german_longitudinal_ready": "TRUE" if ready else "FALSE",
                "coverage_notes": coverage_notes(
                    n_pre_obs=len(pre),
                    n_post_obs=len(post),
                    n_pre_de=len(pre_de),
                    n_post_de=len(post_de),
                    n_german_any=len(german_any),
                    n_primary=n_primary,
                    n_selected=n_selected,
                    n_unavailable=n_unavailable,
                    ready=ready,
                ),
            }
        )
    return pd.DataFrame(rows)


def write_coverage_summary(coverage: pd.DataFrame, path: Path) -> dict:
    ready = coverage.loc[coverage["german_longitudinal_ready"].astype(str).str.upper() == "TRUE"]
    not_ready = coverage.loc[coverage["german_longitudinal_ready"].astype(str).str.upper() != "TRUE"]

    def dist(col: str) -> dict[str, int]:
        return {str(k): int(v) for k, v in sorted(Counter(coverage[col].astype(int)).items())}

    german_pre_post = coverage["n_pre_event_german_eligible"].astype(int) + coverage[
        "n_post_event_german_eligible"
    ].astype(int)
    # Also count event-time German separately from obs via primary+sens is optional;
    # distribution of German eligible observation counts per firm uses pre+post+ (from notes).
    # Prefer total german eligible from obs-backed columns: sum of pre+post only understates
    # firms with event-only German. Recompute from coverage_notes fields already present.
    # Use n_primary + sensitivity_de isn't total german. Keep distribution of:
    # - sum of german eligible pre+post (longitudinal slots)
    # - and n_primary / n_sensitivity as requested

    rescue = not_ready.copy()
    rescue_rows = []
    for _, r in rescue.iterrows():
        rescue_rows.append(
            f"| {r['firm_id']} | {r['company']} | {r['n_pre_event_german_eligible']} | "
            f"{r['n_post_event_german_eligible']} | {r['n_primary_observations']} | "
            f"{r['n_sensitivity_observations']} | `{r['coverage_notes']}` |"
        )

    def fmt_dist(d: dict[str, int]) -> str:
        lines = ["| Count | Firms |", "|------:|------:|"]
        for k, v in d.items():
            lines.append(f"| {k} | {v} |")
        return "\n".join(lines)

    body = f"""# Firm Longitudinal Coverage Summary — `full_sample_v1`

**Phase:** A (analytical exports only; no extraction changes)  
**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
**Source release:** `data/releases/full_sample_v1/`

## Headline

| Metric | Value |
|--------|------:|
| Total firms | {len(coverage)} |
| German longitudinal-ready firms | {len(ready)} |
| Non-ready firms | {len(not_ready)} |

**Definition:** `german_longitudinal_ready = TRUE` iff the firm has ≥1 German text-eligible
observation in {{`pre_pre_event`, `pre_event`}} **and** ≥1 in {{`post_event`, `post_post_event`}}.

## Distribution of German eligible observations (pre + post slots)

Counts are `n_pre_event_german_eligible + n_post_event_german_eligible` per firm.

{fmt_dist(dict(sorted(Counter(german_pre_post.astype(int)).items())))}

## Distribution of primary observations per firm

{fmt_dist(dist("n_primary_observations"))}

## Distribution of sensitivity observations (all-language) per firm

{fmt_dist(dist("n_sensitivity_observations"))}

## Firms requiring rescue (not German longitudinal-ready)

| firm_id | company | pre_DE | post_DE | primary | sensitivity_all | notes |
|--------:|---------|-------:|--------:|--------:|----------------:|-------|
{chr(10).join(rescue_rows)}

## Notes

- German eligibility uses the existing release flag `german_text_analysis_eligible`.
- Sensitivity observation counts refer to the all-language sensitivity export.
- This summary does not modify extraction outputs.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return {
        "total_firms": len(coverage),
        "german_ready_firms": len(ready),
        "non_ready_firms": len(not_ready),
    }


def validate(
    *,
    sens: pd.DataFrame,
    sens_de: pd.DataFrame,
    primary: pd.DataFrame,
    obs: pd.DataFrame,
    coverage: pd.DataFrame,
    original_sens_hash: str,
    current_sens_hash: str,
) -> list[str]:
    errors: list[str] = []

    if list(sens_de.columns) != list(sens.columns):
        errors.append("sensitivity_de columns differ from sensitivity_all")

    if not as_bool(sens_de["german_text_analysis_eligible"]).all():
        errors.append("sensitivity_de contains non-German-eligible rows")

    expected = sens.loc[as_bool(sens["german_text_analysis_eligible"])]
    if len(sens_de) != len(expected):
        errors.append(f"sensitivity_de count {len(sens_de)} != expected {len(expected)}")

    key_cols = ["firm_id", "relative_timepoint"]
    a = set(map(tuple, sens_de[key_cols].astype(str).values.tolist()))
    b = set(map(tuple, expected[key_cols].astype(str).values.tolist()))
    if a != b:
        errors.append("sensitivity_de firm×timepoint keys differ from expected German filter")

    # Counts reconcile with existing release
    if len(primary) != 51:
        errors.append(f"primary count changed unexpectedly: {len(primary)}")
    if len(sens) != 84:
        errors.append(f"sensitivity_all count changed unexpectedly: {len(sens)}")
    if int(as_bool(obs["german_text_analysis_eligible"]).sum()) != 61:
        errors.append("observation_text_summary german eligible count != 61")
    if len(sens_de) != 61:
        errors.append(f"sensitivity_de expected 61, got {len(sens_de)}")

    # Primary keys ⊆ sensitivity_de keys (German include rows)
    prim_keys = set(map(tuple, primary[key_cols].astype(str).values.tolist()))
    if not prim_keys.issubset(a):
        errors.append("primary keys not subset of sensitivity_de keys")

    if original_sens_hash != current_sens_hash:
        errors.append("existing sensitivity_all file contents were modified")

    if len(coverage) != 30:
        errors.append(f"coverage rows != 30 firms ({len(coverage)})")

    ready_n = int((coverage["german_longitudinal_ready"].astype(str).str.upper() == "TRUE").sum())
    # recompute independently
    recomputed = 0
    for firm_id, g in obs.groupby(obs["firm_id"].astype(str)):
        pre = g.loc[g["relative_timepoint"].isin(PRE_EVENT)]
        post = g.loc[g["relative_timepoint"].isin(POST_EVENT)]
        if as_bool(pre["german_text_analysis_eligible"]).any() and as_bool(
            post["german_text_analysis_eligible"]
        ).any():
            recomputed += 1
    if ready_n != recomputed:
        errors.append(f"ready firm count mismatch coverage={ready_n} recomputed={recomputed}")

    return errors


def file_sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def update_documentation() -> list[str]:
    """Documentation-only updates distinguishing corpus language scopes."""
    touched: list[str] = []

    corpus_block = """
## Branding observation corpora (language scope)

| Corpus | File | Language scope |
|--------|------|----------------|
| Primary | `full_sample_branding_corpus_observations_primary.csv` | **German only** |
| Sensitivity | `full_sample_branding_corpus_observations_sensitivity.csv` | **All languages** |
| Sensitivity (German) | `full_sample_branding_corpus_observations_sensitivity_de.csv` | **German only** |

Phase A added the German sensitivity export and firm longitudinal coverage tables without
modifying extraction outputs.
""".strip()

    targets = [
        ROOT_REPORTS / "full_sample_quality_report.md",
        REL_REPORTS / "full_sample_quality_report.md",
        ROOT_REPORTS / "full_sample_readiness.md",
        REL_REPORTS / "full_sample_readiness.md",
        ROOT_REPORTS / "full_sample_reproducibility.md",
        REL_REPORTS / "full_sample_reproducibility.md",
    ]

    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "Sensitivity (German)" in text and "All languages" in text:
            continue
        # Insert after Corpora section or at end of Outputs / Headline metrics.
        if "## Branding observation corpora (language scope)" in text:
            continue
        if path.name == "full_sample_quality_report.md":
            needle = "## Corpora\n"
            if needle in text:
                # After corpora table block — insert before ## Governance
                if "## Governance" in text and corpus_block not in text:
                    text = text.replace("## Governance", corpus_block + "\n\n## Governance", 1)
                    path.write_text(text, encoding="utf-8")
                    touched.append(str(path.relative_to(ROOT)))
                    continue
        if path.name == "full_sample_readiness.md":
            if "51** primary / **84** sensitivity" in text:
                text = text.replace(
                    "**51** primary / **84** sensitivity NLP observations",
                    "**51** primary (German) / **84** sensitivity (all languages) / "
                    "**61** sensitivity (German) NLP observations",
                )
            if corpus_block.splitlines()[0] not in text:
                text = text.rstrip() + "\n\n" + corpus_block + "\n"
            path.write_text(text, encoding="utf-8")
            touched.append(str(path.relative_to(ROOT)))
            continue
        if path.name == "full_sample_reproducibility.md":
            addition = (
                "\n### Phase A analytical outputs (no re-crawl)\n\n"
                "```bash\n"
                "python scripts/build_full_sample_phase_a_outputs.py\n"
                "```\n\n"
                + corpus_block
                + "\n\nAlso writes `firm_longitudinal_coverage.csv` and "
                "`firm_longitudinal_coverage_summary.md`.\n"
            )
            if "build_full_sample_phase_a_outputs.py" not in text:
                if "## Tests" in text:
                    text = text.replace("## Tests", addition + "\n## Tests", 1)
                else:
                    text = text.rstrip() + "\n" + addition
                path.write_text(text, encoding="utf-8")
                touched.append(str(path.relative_to(ROOT)))
    return touched


def write_phase_a_report(
    *,
    sens_n: int,
    sens_de_n: int,
    primary_n: int,
    ready_n: int,
    errors: list[str],
    doc_updates: list[str],
    paths_created: list[str],
) -> None:
    ok = len(errors) == 0
    body = f"""# Phase A Outputs — `full_sample_v1`

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
**Mode:** metadata / reporting only  
**Extraction pipeline modified:** **No**  
**Crawler modified:** **No**  
**Existing corpus CSV contents modified:** **No**

## Files created

{chr(10).join(f"- `{p}`" for p in paths_created)}

## Observation counts

| Corpus | Language scope | N |
|--------|----------------|--:|
| Primary | German only | {primary_n} |
| Sensitivity | All languages | {sens_n} |
| Sensitivity (German) | German only | {sens_de_n} |

German longitudinal-ready firms: **{ready_n}** / 30

## Validation checks

| Check | Status |
|-------|--------|
| German sensitivity export only German-eligible | {"PASS" if ok else "FAIL"} |
| Observation counts reconcile with release | {"PASS" if ok else "FAIL"} |
| Existing sensitivity_all file unchanged | {"PASS" if ok else "FAIL"} |
| No observation regeneration | PASS |
| No crawl / extraction rerun | PASS |

{("Validation errors:\\n" + chr(10).join(f"- {e}" for e in errors)) if errors else "All validation checks passed."}

## Documentation updates (labels only)

{chr(10).join(f"- `{p}`" for p in doc_updates) if doc_updates else "- (none)"}

## Confirmation

Phase A produces additional analytical exports from the frozen `full_sample_v1` release.
It does **not** alter validated extraction logic, crawler behavior, snapshot selection,
deduplication, language detection, tokenization, governance/branding extraction, or
observation eligibility rules.
"""
    for path in (
        ROOT_REPORTS / "phase_a_outputs.md",
        REL_REPORTS / "phase_a_outputs.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def main() -> int:
    sens_path = REL_DATA / SENS_ALL_NAME
    original_sens_hash = file_sha256(sens_path)

    firms = load_csv(FIRMS_NAME)
    obs = load_csv(OBS_NAME)
    primary = load_csv(PRIMARY_NAME)
    sens = load_csv(SENS_ALL_NAME)
    snaps = load_csv("full_sample_snapshots.csv")

    sens_de = build_sensitivity_de(sens)
    coverage = build_firm_coverage(firms, obs, snaps, primary, sens)

    paths_created: list[str] = []

    # Release data
    write_csv(sens_de, REL_DATA / SENS_DE_NAME, OUTPUT / SENS_DE_NAME)
    paths_created.extend(
        [
            f"data/releases/full_sample_v1/data/{SENS_DE_NAME}",
            f"data/output/{SENS_DE_NAME}",
        ]
    )
    write_csv(coverage, REL_DATA / COVERAGE_NAME, OUTPUT / COVERAGE_NAME)
    paths_created.extend(
        [
            f"data/releases/full_sample_v1/data/{COVERAGE_NAME}",
            f"data/output/{COVERAGE_NAME}",
        ]
    )

    summary_stats = write_coverage_summary(
        coverage, REL_REPORTS / "firm_longitudinal_coverage_summary.md"
    )
    # Mirror under root reports
    write_coverage_summary(coverage, ROOT_REPORTS / "firm_longitudinal_coverage_summary.md")
    paths_created.extend(
        [
            "data/releases/full_sample_v1/reports/firm_longitudinal_coverage_summary.md",
            "reports/firm_longitudinal_coverage_summary.md",
        ]
    )

    current_sens_hash = file_sha256(sens_path)
    errors = validate(
        sens=sens,
        sens_de=sens_de,
        primary=primary,
        obs=obs,
        coverage=coverage,
        original_sens_hash=original_sens_hash,
        current_sens_hash=current_sens_hash,
    )

    doc_updates = update_documentation()
    write_phase_a_report(
        sens_n=len(sens),
        sens_de_n=len(sens_de),
        primary_n=len(primary),
        ready_n=summary_stats["german_ready_firms"],
        errors=errors,
        doc_updates=doc_updates,
        paths_created=paths_created
        + [
            "reports/phase_a_outputs.md",
            "data/releases/full_sample_v1/reports/phase_a_outputs.md",
        ],
    )

    result = {
        "ok": len(errors) == 0,
        "primary_n": len(primary),
        "sensitivity_all_n": len(sens),
        "sensitivity_de_n": len(sens_de),
        "german_ready_firms": summary_stats["german_ready_firms"],
        "errors": errors,
        "doc_updates": doc_updates,
    }
    interim = ROOT / "data" / "interim" / "phase_a_outputs_validation.json"
    interim.parent.mkdir(parents=True, exist_ok=True)
    interim.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
