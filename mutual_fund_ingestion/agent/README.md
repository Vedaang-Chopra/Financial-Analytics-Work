# Mutual Fund Ingestion Agent

Task-URL driven mutual fund ingestion agent. Accepts task URLs, discovers data sources, extracts raw data, parses it, validates it, and loads records into PostgreSQL.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database schema
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"

# Run agent (dry-run)
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "$DATABASE_URL" \
  --max-pages 10 \
  --dry-run

# Run agent (live)
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "$DATABASE_URL" \
  --max-pages 500 \
  --use-browser
```

## CLI Commands

| Command | Description |
|---|---|
| `python -m mutual_fund_ingestion run-agent` | Run ingestion from task URLs |
| `python -m mutual_fund_ingestion init-db` | Create database schema |
| `python -m mutual_fund_ingestion bootstrap-sources` | Refresh Phase 1A source registry |
| `python -m mutual_fund_ingestion profile-providers` | Run Phase 1B provider profiling |

## Module Structure

| File | Layer | Description |
|---|---|---|
| `agent/runner.py` | 3 | `IngestionRunner` — orchestrates the full pipeline |
| `agent/discovery.py` | 4 | `DiscoveryEngine` — URL queue, fetch, link extraction, relevance scoring |
| `agent/browser.py` | 4 | `extract_with_browser` — Playwright extraction |
| `agent/extract.py` | 4 | `ArtifactCollector` — file download, checksum, temp management |
| `agent/parser/nav.py` | 4 | NAV text/CSV parser → `nav_history` rows |
| `agent/parser/amc.py` | 4 | AMC list HTML parser → `amcs` rows |
| `agent/parser/portfolio.py` | 4 | Excel portfolio parser → `portfolio_holdings` rows |
| `agent/validate.py` | 4 | Validation rules, quarantine, retry queue |
| `agent/vlm.py` | 4 | `VLMClient` interface (null + Ollama) |
| `agent/db.py` | 5 | 17 SQLAlchemy models, `create_tables()`, `get_session_maker()` |
| `agent/models.py` | 5 | `AgentResult`, `ParserResult`, runtime dataclasses |
| `agent/config.py` | 5 | `AgentConfig` from CLI args |

## Supported Dataset Types

| Dataset Type | File Types | Parser |
|---|---|---|
| `nav_history` | text, csv | `nav_text_v1`, `nav_csv_v1` |
| `amc_provider_list` | html | `amc_html_v1` |
| `portfolio_disclosure` | xlsx, xls, csv | `portfolio_excel_v1` |

## Configuration

See `AgentConfig` in `agent/config.py` for all available options. Key flags:

```bash
--max-pages 500      # Max pages to crawl
--max-depth 5        # Max crawl depth
--use-browser        # Enable Playwright fallback
--use-vlm            # Enable VLM-guided analysis
--keep-raw-files     # Retain raw files after parse
--dry-run            # No database writes
--fail-fast          # Stop on first error
```

## Architecture

```
task_urls → IngestionRunner
  → DiscoveryEngine (URL queue, fetch, link extraction)
  → extract_with_browser (Playwright, optional)
  → ArtifactCollector (download, checksum)
  → ParserRouter (route by dataset_type + file_type)
  → validate_and_filter_records
  → staging + canonical upsert
  → quarantine + retry queue
```

## Tests

```bash
python -m pytest tests/test_agent.py -v  # 21 tests
python -m pytest tests/ -v               # 50 tests total
```