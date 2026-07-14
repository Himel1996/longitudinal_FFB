"""Tests for observation grid / timepoints."""

from datetime import date

import pandas as pd

from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline.runner import PipelineRunner


def test_observation_grid_five_timepoints(tmp_path):
    input_csv = tmp_path / "firms.csv"
    pd.DataFrame([{
        "rank": 1, "company": "TEST GMBH", "event_type": "succession",
        "event_year": 2015, "event_label": "test", "source_confidence": "high",
        "wayback_tier": "A", "screening_recommendation": "prioritize",
        "pre_html_pages": 10, "post_html_pages": 10, "primary_domain": "example.de",
        "website": "https://www.example.de/", "event_source_url": "", "notes": "",
    }]).to_csv(input_csv, index=False)

    config = PipelineConfig()
    config.run.input_csv = str(input_csv)
    config.run.output_dir = str(tmp_path / "output")
    config.run.interim_dir = str(tmp_path / "interim")
    config.run.reports_dir = str(tmp_path / "reports")
    config.run.top_n = 1

    runner = PipelineRunner(config, project_root=tmp_path)
    runner.prepare(input_csv=str(input_csv), top_n=1)
    obs = pd.read_csv(tmp_path / "interim" / "state" / "observations.csv")
    assert len(obs) == 5
    years = sorted(obs["target_year"].tolist())
    assert years == [2011, 2013, 2015, 2017, 2019]
