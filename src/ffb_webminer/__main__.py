"""CLI entry point for FFB WebMiner."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ffb_webminer.config import PipelineConfig
from ffb_webminer.pipeline.runner import PipelineRunner


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ffb-webminer", description="Archived-web research pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default="config/pilot.yaml", help="Path to YAML config")

    p_prepare = sub.add_parser("prepare", help="Load firms and build observation grid")
    add_common(p_prepare)
    p_prepare.add_argument("--input", dest="input_csv", default=None)
    p_prepare.add_argument("--top-n", type=int, default=None)

    for name, help_text in [
        ("discover-snapshots", "Query CDX and select snapshots"),
        ("crawl", "Crawl selected snapshots and extract text"),
        ("extract", "Alias for crawl (extraction included in crawl)"),
        ("visuals", "Optional homepage visual extraction"),
        ("report", "Generate quality reports and manifest"),
        ("validate", "Regenerate pages from snapshots and export analysis tables"),
    ]:
        p = sub.add_parser(name, help=help_text)
        add_common(p)
        p.add_argument("--firm-id", action="append", dest="firm_ids")

    p_run = sub.add_parser("run", help="Run full pipeline")
    add_common(p_run)
    p_run.add_argument("--firm-id", action="append", dest="firm_ids", help="Limit to firm_id(s)")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    project_root = Path.cwd()
    config = PipelineConfig.from_yaml(project_root / args.config)
    runner = PipelineRunner(config, project_root=project_root)

    if args.command == "prepare":
        runner.prepare(input_csv=args.input_csv, top_n=args.top_n)
    elif args.command == "discover-snapshots":
        if not (runner.output_dir / "firms.csv").exists():
            runner.prepare()
        runner.discover_snapshots(firm_ids=getattr(args, "firm_ids", None))
    elif args.command in ("crawl", "extract"):
        runner.crawl_and_extract(firm_ids=getattr(args, "firm_ids", None))
    elif args.command == "visuals":
        runner.extract_visuals(firm_ids=getattr(args, "firm_ids", None))
    elif args.command == "report":
        runner.report()
    elif args.command == "validate":
        runner.prepare()
        runner.refresh_snapshot_metadata()
        runner.crawl_and_extract(firm_ids=getattr(args, "firm_ids", None))
        stats = runner.validate_and_export()
        logging.getLogger(__name__).info("Validation complete: %s", stats)
    elif args.command == "run":
        runner.prepare()
        firm_ids = getattr(args, "firm_ids", None)
        runner.discover_snapshots(firm_ids=firm_ids)
        runner.crawl_and_extract(firm_ids=firm_ids)
        runner.extract_visuals(firm_ids=firm_ids)
        runner.report()

    return 0


if __name__ == "__main__":
    sys.exit(main())
