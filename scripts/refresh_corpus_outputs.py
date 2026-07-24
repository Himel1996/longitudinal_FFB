#!/usr/bin/env python3
"""Re-apply classification, deduplication, language inclusion, and regenerate corpora."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.extract.domain import parse_domain
from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.corpus_outputs import (
    build_branding_corpus_observations,
    build_branding_corpus_pages,
    build_duplicate_summary,
    build_governance_metadata_observations,
    build_governance_metadata_pages,
    build_observation_text_summary,
)
from ffb_webminer.pipeline.runner import PipelineRunner
from ffb_webminer.pipeline.schemas import (
    BRANDING_CORPUS_OBSERVATION_COLUMNS,
    BRANDING_CORPUS_PAGE_COLUMNS,
    DUPLICATE_SUMMARY_COLUMNS,
    GOVERNANCE_METADATA_OBSERVATION_COLUMNS,
    GOVERNANCE_METADATA_PAGE_COLUMNS,
    OBSERVATION_TEXT_SUMMARY_COLUMNS,
    PAGE_COLUMNS,
    QUALITY_SUMMARY_COLUMNS,
)
from ffb_webminer.quality.checks import check_page, summarize_snapshot_pages
from ffb_webminer.quality.deduplication import deduplicate_within_observations
from ffb_webminer.quality.language_inclusion import annotate_language_inclusion
from ffb_webminer.quality.page_classification import classify_page
from ffb_webminer.quality.page_validation import validate_page_for_analysis


def _apply_classification(row: dict, domain: str, config: PipelineConfig) -> dict:
    row = check_page(row, domain, config.quality)
    row = validate_page_for_analysis(
        row,
        domain,
        config.quality,
        max_temporal_distance=config.quality.max_temporal_distance_days,
    )
    classification = classify_page(
        row,
        governance_allowlist=config.analysis.governance_url_allowlist,
    )
    row.update({
        "page_category": classification.page_category,
        "page_category_reason": classification.page_category_reason,
        "classification_rule_priority": classification.classification_rule_priority,
        "classification_rule_id": classification.classification_rule_id,
        "branding_corpus_eligible": classification.branding_corpus_eligible,
        "branding_corpus_exclusion_reason": classification.branding_corpus_exclusion_reason,
        "governance_metadata_eligible": classification.governance_metadata_eligible,
        "governance_inclusion_reason": classification.governance_inclusion_reason,
        "governance_rule_id": classification.governance_rule_id,
        "governance_evidence_type": classification.governance_evidence_type,
    })
    return row


def _write_language_corpora(out: Path, observation_summary, pages, config: PipelineConfig) -> tuple:
    branding_pages_all = build_branding_corpus_pages(pages, observation_summary, language_scope="all")
    branding_pages_de = build_branding_corpus_pages(
        pages, observation_summary, language_scope="de", require_german_observation=True
    )
    branding_pages_en = build_branding_corpus_pages(pages, observation_summary, language_scope="en")
    branding_pages_other = build_branding_corpus_pages(pages, observation_summary, language_scope="other")

    use_german = (config.analysis.primary_corpus_language or "de").lower() == "de"
    branding_obs_all = build_branding_corpus_observations(
        observation_summary, branding_pages_all, primary_only=None, corpus_language_scope="all"
    )
    branding_obs_primary = build_branding_corpus_observations(
        observation_summary,
        branding_pages_de if use_german else branding_pages_all,
        primary_only=True,
        corpus_language_scope="de" if use_german else "all",
        use_german_eligibility=use_german,
    )
    branding_obs_sens = build_branding_corpus_observations(
        observation_summary, branding_pages_all, primary_only=False, corpus_language_scope="all"
    )
    branding_obs_de = build_branding_corpus_observations(
        observation_summary,
        branding_pages_de,
        primary_only=None,
        corpus_language_scope="de",
        use_german_eligibility=True,
    )
    branding_obs_en = build_branding_corpus_observations(
        observation_summary, branding_pages_en, primary_only=None, corpus_language_scope="en"
    )
    branding_obs_other = build_branding_corpus_observations(
        observation_summary, branding_pages_other, primary_only=None, corpus_language_scope="other"
    )

    for path, df in [
        (out / "branding_corpus_pages.csv", branding_pages_all),
        (out / "branding_corpus_pages_all_languages.csv", branding_pages_all),
        (out / "branding_corpus_pages_de.csv", branding_pages_de),
        (out / "branding_corpus_pages_en.csv", branding_pages_en),
        (out / "branding_corpus_pages_other.csv", branding_pages_other),
        (out / "branding_corpus_observations.csv", branding_obs_all),
        (out / "branding_corpus_observations_all_languages.csv", branding_obs_all),
        (out / "branding_corpus_observations_de.csv", branding_obs_de),
        (out / "branding_corpus_observations_en.csv", branding_obs_en),
        (out / "branding_corpus_observations_other.csv", branding_obs_other),
        (out / "branding_corpus_observations_primary.csv", branding_obs_primary),
        (out / "branding_corpus_observations_sensitivity.csv", branding_obs_sens),
    ]:
        pipeline_io.write_csv(df, path, BRANDING_CORPUS_PAGE_COLUMNS if "pages" in path.name else BRANDING_CORPUS_OBSERVATION_COLUMNS)

    return branding_pages_all, branding_obs_primary, branding_obs_sens


def main() -> int:
    config = PipelineConfig.from_yaml(ROOT / "config/pilot.yaml")
    runner = PipelineRunner(config, project_root=ROOT)
    out = Path(config.run.output_dir)
    firms = pd.read_csv(out / "firms.csv")
    snapshots = pd.read_csv(out / "snapshots.csv")
    pages = pd.read_csv(out / "pages.csv")

    firm_domains = {
        str(int(float(row["firm_id"]))): row["primary_domain"] for _, row in firms.iterrows()
    }
    preferred_hosts = {}
    for _, firm in firms.iterrows():
        host = parse_domain(str(firm.get("website") or "")).hostname or ""
        preferred_hosts[str(int(float(firm["firm_id"])))] = host.lstrip("www.")

    refreshed_rows = []
    for _, page in pages.iterrows():
        row = page.to_dict()
        firm_id = str(int(float(row["firm_id"])))
        refreshed_rows.append(_apply_classification(row, firm_domains[firm_id], config))

    near_thresh = float(config.deduplication.near_duplicate_threshold)
    refreshed_rows = deduplicate_within_observations(
        refreshed_rows,
        preferred_hosts=preferred_hosts,
        near_duplicate_threshold=near_thresh,
    )
    refreshed_rows = annotate_language_inclusion(refreshed_rows, config.analysis)
    pages = pd.DataFrame(refreshed_rows)
    pipeline_io.write_csv(pages, out / "pages.csv", PAGE_COLUMNS)

    governance_pages = build_governance_metadata_pages(pages)
    governance_obs = build_governance_metadata_observations(snapshots, governance_pages)
    observation_summary = build_observation_text_summary(
        snapshots, pages, governance_obs, config.analysis
    )
    branding_pages, branding_obs_primary, branding_obs_sens = _write_language_corpora(
        out, observation_summary, pages, config
    )
    duplicate_summary = build_duplicate_summary(pages)

    pipeline_io.write_csv(
        governance_pages, out / "governance_metadata_pages.csv", GOVERNANCE_METADATA_PAGE_COLUMNS
    )
    pipeline_io.write_csv(
        governance_obs, out / "governance_metadata_observations.csv", GOVERNANCE_METADATA_OBSERVATION_COLUMNS
    )
    pipeline_io.write_csv(
        observation_summary, out / "observation_text_summary.csv", OBSERVATION_TEXT_SUMMARY_COLUMNS
    )
    pipeline_io.write_csv(duplicate_summary, out / "duplicate_summary.csv", DUPLICATE_SUMMARY_COLUMNS)

    summaries = []
    for _, snap in snapshots.iterrows():
        snap_pages = pages[
            (pages["firm_id"].astype(str) == str(int(float(snap["firm_id"]))))
            & (pages["relative_timepoint"] == snap["relative_timepoint"])
        ]
        summaries.append(
            summarize_snapshot_pages(
                snap_pages.to_dict("records"),
                runner.run_id,
                str(snap["firm_id"]),
                int(snap["rank"]),
                snap["company"],
                snap["relative_timepoint"],
                int(snap["target_year"]),
                snap["snapshot_status"],
            )
        )
    summary_df = pd.DataFrame(summaries)
    pipeline_io.write_csv(summary_df, out / "quality_summary.csv", QUALITY_SUMMARY_COLUMNS)
    runner._write_corpus_quality_report()
    print("Refreshed corpus outputs and quality summary")
    print(f"branding_pages={len(branding_pages)}")
    print(f"primary_obs={len(branding_obs_primary)} sensitivity_obs={len(branding_obs_sens)}")
    print(f"governance_pages={len(governance_pages)}")
    print(f"duplicate_rows={len(duplicate_summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
