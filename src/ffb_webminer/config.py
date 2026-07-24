"""Configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SnapshotSelectionConfig(BaseModel):
    target_date_strategy: str = "mid_year"
    target_month_day: str = "07-01"
    tolerance_days: int = 548
    prefer: list[str] = Field(default_factory=lambda: ["closest", "earlier_on_tie"])
    allowed_status_codes: list[str] = Field(default_factory=lambda: ["200"])
    allowed_mimetypes: list[str] = Field(default_factory=lambda: ["text/html"])
    url_variants: list[str] = Field(
        default_factory=lambda: [
            "https://www.{domain}/",
            "http://www.{domain}/",
            "https://{domain}/",
            "http://{domain}/",
        ]
    )
    event_year_precision_note: str = ""
    event_dates_config: str = "config/event_dates.yaml"
    event_pre_window_days: int = 90
    adjacent_period_min_days: int = 180
    override_very_low_usable: bool = False


class CrawlConfig(BaseModel):
    mode: str = "focused_site_crawl"
    max_pages_per_snapshot: int = 25
    max_depth: int = 2
    timeout_seconds: int = 45
    retries: int = 3
    max_response_bytes: int = 10_485_760
    strip_query_strings: bool = False
    exclude_query_patterns: list[str] = Field(default_factory=list)
    user_agent: str = "FFB-WebMiner/0.1"
    throttle_seconds: float = 1.5
    extract_pdf: bool = False
    prefer_german_paths: bool = True
    branding_path_patterns: dict[str, list[str]] = Field(default_factory=dict)
    reserved_slots: dict[str, int] = Field(
        default_factory=lambda: {
            "homepage": 1,
            "company_about": 4,
            "history_heritage": 3,
            "family_owners": 3,
            "values_responsibility": 3,
            "management_leadership": 3,
        }
    )
    flexible_slots: dict[str, int] = Field(
        default_factory=lambda: {
            "secondary_pages": 5,
            "broad_context": 3,
        }
    )


class ExtractConfig(BaseModel):
    methods: dict[str, str] = Field(default_factory=lambda: {"primary": "trafilatura", "fallback": "readability"})
    store_raw_html: bool = True
    raw_html_dir: str = "data/interim/html"
    min_text_chars: int = 50


class DeduplicationConfig(BaseModel):
    within_observation: bool = True
    near_duplicate_threshold: float = 0.98
    near_duplicate_enabled: bool = True


class AnalysisConfig(BaseModel):
    min_branding_pages: int = 1
    min_branding_tokens: int = 100
    preferred_branding_tokens: int = 300
    short_text_language_chars: int = 80
    language_confidence_threshold: float = 0.80
    low_quality_token_threshold: int = 100
    moderate_quality_token_threshold: int = 300
    governance_url_allowlist: list[str] = Field(default_factory=list)
    primary_corpus_language: str = "de"
    german_token_share_min: float = 0.70
    allow_unknown_in_german_corpus: bool = False
    near_duplicate_threshold: float = 0.98


class VisualConfig(BaseModel):
    enabled: bool = True
    viewport_width: int = 1280
    viewport_height: int = 800
    screenshot_dir: str = "data/interim/screenshots"
    heading_rule: str = ""


class ArchiveConfig(BaseModel):
    cdx_api_url: str = "https://web.archive.org/cdx/search/cdx"
    cache_dir: str = "data/interim/cdx"
    retry_max: int = 5
    retry_backoff_base: float = 2.0


class QualityConfig(BaseModel):
    max_temporal_distance_days: int = 548
    min_text_chars: int = 50
    manual_validation_sample_size: int = 15


class TimepointsConfig(BaseModel):
    relative: list[str] = Field(
        default_factory=lambda: ["pre_pre_event", "pre_event", "event", "post_event", "post_post_event"]
    )
    year_offsets: dict[str, int] = Field(
        default_factory=lambda: {
            "pre_pre_event": -4,
            "pre_event": -2,
            "event": 0,
            "post_event": 2,
            "post_post_event": 4,
        }
    )


class RunConfig(BaseModel):
    run_id: str | None = None
    top_n: int = 5
    input_csv: str = "data/input/family_firm_event_longlist_30_trimmed.csv"
    output_dir: str = "data/output"
    interim_dir: str = "data/interim"
    reports_dir: str = "reports"


class PipelineConfig(BaseModel):
    run: RunConfig = Field(default_factory=RunConfig)
    timepoints: TimepointsConfig = Field(default_factory=TimepointsConfig)
    snapshot_selection: SnapshotSelectionConfig = Field(default_factory=SnapshotSelectionConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    visual: VisualConfig = Field(default_factory=VisualConfig)
    archive: ArchiveConfig = Field(default_factory=ArchiveConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    deduplication: DeduplicationConfig = Field(default_factory=DeduplicationConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> PipelineConfig:
        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        return cls.model_validate(raw)

    def resolve_paths(self, project_root: Path | None = None) -> PipelineConfig:
        root = project_root or Path.cwd()
        self.run.output_dir = str((root / self.run.output_dir).resolve())
        self.run.interim_dir = str((root / self.run.interim_dir).resolve())
        self.run.reports_dir = str((root / self.run.reports_dir).resolve())
        self.run.input_csv = str((root / self.run.input_csv).resolve())
        self.extract.raw_html_dir = str((root / self.extract.raw_html_dir).resolve())
        self.visual.screenshot_dir = str((root / self.visual.screenshot_dir).resolve())
        self.archive.cache_dir = str((root / self.archive.cache_dir).resolve())
        return self
