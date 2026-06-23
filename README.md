# Financial-Analytics-Work

## Mutual fund ingestion Phase 1

Phase 1A bootstraps a provenance-aware source registry from curated entries,
AMFI, and optional SEBI evidence. Phase 1B profiles enabled primary AMC/provider
websites and persists how each site exposes investor disclosure documents.

AMFI and SEBI remain secondary reference indexes. Direct provider websites are
the primary sources. Phase 1 does not download disclosure files, parse
documents, load PostgreSQL, run analytics, or control a VLM.

Install the dependencies and optional Chromium browser:

```bash
python -m pip install -r requirements.txt
playwright install chromium
```

Run Phase 1:

```bash
# Preview a registry refresh without network access or file writes.
python -m mutual_fund_ingestion bootstrap-sources --no-reference-network --dry-run

# Refresh the registry using available reference sources.
python -m mutual_fund_ingestion bootstrap-sources

# Profile three primary providers.
python -m mutual_fund_ingestion profile-providers --limit 3 --force

# Run Phase 1A followed by a bounded Phase 1B smoke.
python -m mutual_fund_ingestion phase-1 --limit 3
```

`profile-sites` remains a compatibility alias for `profile-providers`.
`--registry` remains an alias for `--config`.

Phase 1 artifacts:

```text
configs/amc_sources.yaml
data/raw/mutual_funds/source_registry/source_registry_candidates.jsonl
data/raw/mutual_funds/source_registry/source_registry.latest.json
data/reports/mutual_funds/source_registry_report.html
data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
data/reports/mutual_funds/provider_profile_report.html
data/reports/mutual_funds/provider_profile_summary.csv
data/debug/mutual_funds/provider_profiles/<safe_amc_name>/
```

Useful options:

```text
--limit N
--amc "HDFC Mutual Fund"
--force
--dry-run
--log-level INFO
--use-playwright true|false
--no-reference-network
--output-dir data/raw/mutual_funds/provider_profiles
--timeout 30
--no-browser
```

## AMFI portfolio disclosure ingestion

Discover portfolio disclosure files from AMFI, follow relevant AMC disclosure
pages by one hop, and download the raw files:

```bash
python -m pip install -r requirements.txt
playwright install chromium
python -m amfi_disclosure run
```

Useful bounded and diagnostic runs:

```bash
# Discover without writing metadata or downloading files.
python -m amfi_disclosure discover --dry-run

# Download the latest five discovered files for every AMC.
python -m amfi_disclosure run --limit-per-amc 5

# Disable browser fallback when testing direct HTTP discovery.
python -m amfi_disclosure discover --no-browser
```

Discovery metadata is written to
`data/raw/amfi/links/amfi_portfolio_links.jsonl`. Raw files and their JSON
metadata sidecars are written to `data/raw/amfi/files/`. Browser failure
artifacts are written to `data/debug/amfi/`.

## Task-URL Driven Ingestion Agent

The agent accepts task URLs, discovers relevant data sources, extracts raw data,
parses it, validates it, and inserts records into PostgreSQL.

```bash
# Install dependencies (requires psycopg2-binary)
pip install -r requirements.txt

# Initialize database schema
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"

# Dry-run: discover URLs without writing to DB
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "$DATABASE_URL" \
  --max-pages 5 --max-depth 1 --dry-run

# Live run with Playwright browser fallback
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "$DATABASE_URL" \
  --max-pages 500 --max-depth 5 \
  --use-browser --headless

# Live run with VLM-guided page analysis
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "$DATABASE_URL" \
  --use-browser --use-vlm \
  --vlm-endpoint "http://localhost:11434"
```

Key flags:

| Flag | Default | Description |
|---|---|---|
| `--task-url` | required | Task URL(s). Repeat for multiple. |
| `--task-url-file` | — | File with URLs (one per line) |
| `--database-url` | required | PostgreSQL connection string |
| `--max-pages` | 500 | Max pages to crawl |
| `--max-depth` | 5 | Max crawl depth |
| `--max-files` | 200 | Max files to download |
| `--use-browser` | False | Enable Playwright fallback |
| `--headless` | True | Run browser headless |
| `--use-vlm` | False | Enable VLM page analysis |
| `--keep-raw-files` | False | Retain raw files after parse |
| `--keep-failed-raw-files` | True | Retain failed parse files |
| `--dry-run` | False | No DB writes |

The agent produces 17 PostgreSQL tables: `ingestion_runs`, `task_urls`,
`source_pages`, `discovered_links`, `dataset_candidates`, `raw_artifacts`,
`amcs`, `schemes`, `nav_history`, `documents`, `instruments`,
`portfolio_snapshots`, `portfolio_holdings`, `staging_rows`,
`validation_results`, `quarantine_rows`, `retry_queue`.

Run all tests:

```bash
python -m pytest tests/ -v
# 118 tests: 38 Phase 1 + 36 agent + 11 amfi_disclosure + 22 DB integration + 11 parser/routing
```
