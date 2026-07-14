.PHONY: install test lint run-pilot run-one discover crawl report clean

install:
	pip install -e ".[dev]"

install-visual:
	pip install -e ".[dev,visual]"
	playwright install chromium

test:
	pytest -q

lint:
	ruff check src tests

prepare:
	python -m ffb_webminer prepare --config config/pilot.yaml

discover:
	python -m ffb_webminer discover-snapshots --config config/pilot.yaml

crawl:
	python -m ffb_webminer crawl --config config/pilot.yaml

report:
	python -m ffb_webminer report --config config/pilot.yaml

run-pilot:
	python -m ffb_webminer run --config config/pilot.yaml

run-one:
	python -m ffb_webminer run --config config/pilot.yaml --firm-id 5

clean:
	rm -rf data/interim/cdx data/interim/html data/interim/state data/output/*.csv data/output/*.json data/output/*.parquet
