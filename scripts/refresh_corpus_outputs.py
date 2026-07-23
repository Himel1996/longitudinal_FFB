#!/usr/bin/env python3
"""Re-apply page classification and regenerate corpus outputs without re-crawling."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline import io as pipeline_io
from ffb_webminer.pipeline.corpus_outputs import (
    build_branding_corpus_observations,
    build_branding_corpus_pages,
    build_governance_metadata_observations,
    build_governance_metadata_pages,
    build_observation_text_summary,
)
from ffb_webminer.pipeline.runner import PipelineRunner
from ffb_webminer.pipeline.schemas import (
    BRANDING_CORPUS_OBSERVATION_COLUMNS,
    BRANDING_CORPUS_PAGE_COLUMNS,
    GOVERNANCE_METADATA_OBSERVATION_COLUMNS,
    GOVERNANCE_METADATA_PAGE_COLUMNS,
    OBSERVATION_TEXT_SUMMARY_COLUMNS,
    PAGE_COLUMNS,
    QUALITY_SUMMARY_COLUMNS,
)
from ffb_webminer.quality.checks import check_page, summarize_snapshot_pages
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

    refreshed_rows = []
    for _, page in pages.iterrows():
        row = page.to_dict()
        firm_id = str(int(float(row["firm_id"])))
        refreshed_rows.append(_apply_classification(row, firm_domains[firm_id], config))

    pages = pd.DataFrame(refreshed_rows)
    pipeline_io.write_csv(pages, out / "pages.csv", PAGE_COLUMNS)

    governance_pages = build_governance_metadata_pages(pages)
    governance_obs = build_governance_metadata_observations(snapshots, governance_pages)
    observation_summary = build_observation_text_summary(
        snapshots, pages, governance_obs, config.analysis
    )
    branding_pages = build_branding_corpus_pages(pages, observation_summary)
    branding_obs_all = build_branding_corpus_observations(
        observation_summary, branding_pages, primary_only=None
    )
    branding_obs_primary = build_branding_corpus_observations(
        observation_summary, branding_pages, primary_only=True
    )
    branding_obs_sens = build_branding_corpus_observations(
        observation_summary, branding_pages, primary_only=False
    )

    pipeline_io.write_csv(
        governance_pages, out / "governance_metadata_pages.csv", GOVERNANCE_METADATA_PAGE_COLUMNS
    )
    pipeline_io.write_csv(
        governance_obs, out / "governance_metadata_observations.csv", GOVERNANCE_METADATA_OBSERVATION_COLUMNS
    )
    pipeline_io.write_csv(
        observation_summary, out / "observation_text_summary.csv", OBSERVATION_TEXT_SUMMARY_COLUMNS
    )
    pipeline_io.write_csv(branding_pages, out / "branding_corpus_pages.csv", BRANDING_CORPUS_PAGE_COLUMNS)
    pipeline_io.write_csv(
        branding_obs_all, out / "branding_corpus_observations.csv", BRANDING_CORPUS_OBSERVATION_COLUMNS
    )
    pipeline_io.write_csv(
        branding_obs_primary,
        out / "branding_corpus_observations_primary.csv",
        BRANDING_CORPUS_OBSERVATION_COLUMNS,
    )
    pipeline_io.write_csv(
        branding_obs_sens,
        out / "branding_corpus_observations_sensitivity.csv",
        BRANDING_CORPUS_OBSERVATION_COLUMNS,
    )

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
