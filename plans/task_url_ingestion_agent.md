# Task-URL Driven Mutual Fund Ingestion Agent — Implementation Plan

## Status

**Phase:** Active Development
**Last updated:** 2026-06-15
**Build:** ✅ Core agent implemented, 50 tests passing, all Phase 1A/1B/agent docs complete
**Next milestone:** Phase 2 — Raw document discovery and download

---

## Table of Contents

1. [Background and Context](#1-background-and-context)
2. [What Was Built](#2-what-was-built)
3. [Implemented Architecture](#3-implemented-architecture)
4. [Module Reference](#4-module-reference)
5. [Database Schema — 17 Tables](#5-database-schema--17-tables)
6. [CLI Commands](#6-cli-commands)
7. [Parsing System](#7-parsing-system)
8. [Validation and Quarantine](#8-validation-and-quarantine)
9. [VLM Integration](#9-vlm-integration)
10. [Testing](#10-testing)
11. [Known Gaps — Remaining Work](#11-known-gaps--remaining-work)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Phase-by-Phase Implementation Guide](#13-phase-by-phase-implementation-guide)
14. [Data Priority and Source Strategy](#14-data-priority-and-source-strategy)
15. [CLI Reference](#15-cli-reference)
16. [Setup and Installation](#16-setup-and-installation)
17. [Verification Commands](#17-verification-commands)
18. [Known Issues and Workarounds](#18-known-issues-and-workarounds)

---

## 1. Background and Context

### 1.1 Project Goal

Build an end-to-end financial data ingestion system for Indian mutual fund public disclosure data. The system accepts one or more task URLs (initially AMFI), discovers relevant data sources from those URLs and linked AMC/provider pages, extracts raw data, classifies datasets, parses structured records, validates them, and loads real rows into PostgreSQL.

**Success criterion:** PostgreSQL populated with real mutual fund data — not reports, not notebooks, not design docs.

### 1.2 Why This Approach

- **Provider-first:** AMC/provider websites are the primary source of investor documents. AMFI and SEBI are secondary reference indexes for discovery only.
- **Deterministic before agentic:** Use static scraping, HTML parsing, and network/API interception first. Use Playwright only when necessary. Use VLM only as a last resort.
- **Persistent provider knowledge:** Store strategy, selectors, and debug evidence per provider so future runs don't re-discover from scratch.
- **Staging-first:** All parsed data goes through staging tables before canonical loading. Invalid rows go to quarantine with retry support.
- **Provenance on every row:** Every canonical record carries its source URL and raw_artifact_id.

### 1.3 Data Priority Order

The system must be built in this data priority order (from `00_codex_entrypoint.md`):

1. **AMC/provider list** — who are the asset management companies?
2. **Scheme metadata / scheme master** — what schemes does each AMC offer?
3. **NAV history and latest NAV** — daily net asset values
4. **Portfolio disclosure holdings** — what stocks/bonds does each scheme hold?
5. **Factsheet metadata** — fund facts at a glance
6. **TER, SID, KIM, statutory disclosures, AUM/AAUM** — cost ratios, scheme documents, fund size

### 1.4 Design Source Documents

All implementation must follow:

| File | Role |
|---|---|
| `docs/design/task_url_agent_design_pack/00_codex_entrypoint.md` |schen Build target, success criterion, 12-step required behavior |
| `docs/design/task_url_agent_design_pack/07_postgresql_schema.md` | All 17 table definitions with SQL |
| `docs/design/task_url_agent_design_pack/08_extraction_and_parser_design.md` | Parser router and per-parser design |
| `docs/design/task_url_agent_design_pack/09_validation_quarantine_and_provenance.md` | Validation rules, quarantine, provenance |
| `docs/design/task_url_agent_design_pack/14_codex_build_plan.md` | 10-step implementation sequence |
| `docs/ai_context/CODEBASE_MAP.md` | Module ownership, public APIs, import guidance |
| `docs/design/task_url_agent_design_pack/implementation_report.md` | **The completed implementation reference** |

---

## 2. What Was Built

### 2.1 Summary

The Task-URL Driven Ingestion Agent (`mutual_fund_ingestion/agent/`) was implemented as a full Python package under `mutual_fund_ingestion/agent/`. Shared utilities were consolidated into `utils/`. The CLI was updated with `run-agent` and `init-db` subcommands.

**Result:** 50 passing tests, complete module structure, 3 parsers, 17 DB tables defined.

### 2.2 What Was Committed

```
mutual_fund_ingestion/__init__.py           # Package marker + re-exports
mutual_fund_ingestion/__main__.py            # python -m mutual_fund_ingestion
mutual_fund_ingestion/cli.py                 # + run-agent, init-db subcommands (lazy imports)
mutual_fund_ingestion/models.py               # Phase 1 domain dataclasses
mutual_fund_ingestion/http.py                 # Phase 1 HTTP session
mutual_fund_ingestion/extract.py              # Phase 1 HTML parsing
mutual_fund_ingestion/browser.py             # Phase 1 Playwright (Phase 1B)
mutual_fund_ingestion/profiler.py            # Phase 1B provider profiling
mutual_fund_ingestion/registry.py            # YAML registry loading
mutual_fund_ingestion/source_discovery.py   # AMFI/SEBI candidate discovery (Phase 1A)
mutual_fund_ingestion/source_registry.py    # Candidate merging (Phase 1A)
mutual_fund_ingestion/artifacts.py           # JSONL + snapshot persistence
mutual_fund_ingestion/reports.py             # HTML/CSV report generation

mutual_fund_ingestion/agent/__init__.py
mutual_fund_ingestion/agent/README.md
mutual_fund_ingestion/agent/config.py        # AgentConfig (15 CLI flags)
mutual_fund_ingestion/agent/models.py        # ParserResult, AgentResult, record types
mutual_fund_ingestion/agent/db.py           # 17 SQLAlchemy tables + create_tables()
mutual_fund_ingestion/agent/discovery.py    # DiscoveryEngine (URL queue, HTTP, classify)
mutual_fund_ingestion/agent/browser.py      # extract_with_browser (Playwright)
mutual_fund_ingestion/agent/extract.py      # ArtifactCollector (download, checksum, retention)
mutual_fund_ingestion/agent/parser/__init__.py  # ParserRouter dispatch by (dataset_type, file_type)
mutual_fund_ingestion/agent/parser/nav.py   # parse_nav_text(), parse_nav_csv()
mutual_fund_ingestion/agent/parser/amc.py   # parse_amc_html()
mutual_fund_ingestion/agent/parser/portfolio.py  # parse_portfolio_excel(), _parse_portfolio_csv()
mutual_fund_ingestion/agent/validate.py     # validate_nav/portfolio_record(), validate_and_filter_records()
mutual_fund_ingestion/agent/vlm.py          # VLMClient (ABC), NullVLMClient, OllamaVLMClient
mutual_fund_ingestion/agent/runner.py       # IngestionRunner (orchestration)

utils/__init__.py
utils/http.py                                # HttpSettings, build_session() (consolidated)
utils/url_utils.py                          # canonical_url, file_type_from_url, safe_name, slugify
utils/text_utils.py                         # normalize_amc_name

tests/test_mutual_fund_ingestion.py          # 29 Phase 1A/1B tests
tests/test_agent.py                         # 21 agent tests

notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb  # 18 cells, all agent components

requirements.txt                            # + psycopg2-binary
README.md                                   # + run-agent usage section
docs/ai_context/CODEBASE_MAP.md             # + agent/ and utils/ module ownership
```

### 2.3 What Was Fixed

| Issue | Fix |
|---|---|
| `safe_name` moved to `utils/url_utils.py` but Phase 1 code still imported from `mutual_fund_ingestion.extract` | Updated imports in `profiler.py`, `reports.py`, `test_mutual_fund_ingestion.py` |

---

## 3. Implemented Architecture

### 3.1 Module Structure

```
mutual_fund_ingestion/
├── cli.py                     # Layer 2: CLI entry point (run-agent, init-db)
├── agent/
│   ├── runner.py              # Layer 3: IngestionRunner — orchestrates discover → extract → parse → validate → load
│   ├── config.py              # Layer 5: AgentConfig from CLI args
│   ├── models.py              # Layer 5: ParserResult, AgentResult, record types
│   ├── discovery.py           # Layer 4: DiscoveryEngine — URL queue, HTTP fetch, link extraction, classification
│   ├── browser.py             # Layer 4: extract_with_browser — Playwright rendered HTML + screenshot + network
│   ├── extract.py             # Layer 4: ArtifactCollector — file download, SHA256, temp dir, retention
│   ├── parser/
│   │   ├── __init__.py        # Layer 4: ParserRouter — dispatches by (dataset_type, file_type)
│   │   ├── nav.py             # Layer 4: AMFI NAV text/CSV parser
│   │   ├── amc.py             # Layer 4: AMC provider list HTML parser
│   │   └── portfolio.py       # Layer 4: Excel/CSV portfolio disclosure parser
│   ├── validate.py            # Layer 4: NAV/portfolio validation, quarantine, retry
│   ├── vlm.py                 # Layer 4: VLMClient (ABC), NullVLMClient (default), OllamaVLMClient
│   └── db.py                  # Layer 5: 17 SQLAlchemy models + create_tables() + get_session_maker()
└── utils/
    ├── http.py                # Layer 5: HttpSettings + build_session()
    ├── url_utils.py           # Layer 5: canonical_url, file_type_from_url, safe_name, slugify
    └── text_utils.py          # Layer 5: normalize_amc_name
```

### 3.2 Data Flow

```
AgentConfig (CLI args)
  ↓
IngestionRunner.run()
  ↓
DiscoveryEngine — URL queue (deque), visited URLs (set)
  ↓ (static HTTP fetch)
Extract page HTML
  ↓
DiscoveryEngine.extract_links() → DiscoveredLink list
  ↓
DiscoveryEngine.score_relevance() — filter by domain policy, score by keywords
  ↓
DiscoveryEngine.classify_dataset_type() — map URL path + extension → (dataset_type, file_type)
  ↓
ArtifactCollector.collect() — for dataset candidates:
  ↓ (file download via HTTP or Playwright)
  ↓ (SHA256 checksum, temp file, sidecar metadata)
  ↓
ParserRouter.parse_file() — dispatch by (dataset_type, file_type)
  ↓
[parse_nav_text | parse_nav_csv | parse_amc_html | _parse_portfolio_csv | _parse_portfolio_xlsx]
  ↓
ParserResult(dataset_type, rows, parse_errors, metadata)
  ↓
validate_and_filter_records() — per-dataset validation rules
  ↓
valid_rows → staging → canonical | quarantined → quarantine_rows
  ↓
[DB insert via SQLAlchemy session — wired in runner.run()]
  ↓
AgentResult(run_id, status, pages_visited, links_discovered, files_downloaded,
            rows_inserted, rows_quarantined, retry_tasks, errors)
```

### 3.3 Layer Model

| Layer | Description | Files |
|---|---|---|
| Layer 2 — Public Interface | CLI entry point | `cli.py` |
| Layer 3 — Orchestration | Pipeline runner | `agent/runner.py` |
| Layer 4 — Core Logic | Discovery, extraction, parsing, validation, VLM | `agent/discovery.py`, `agent/browser.py`, `agent/extract.py`, `agent/parser/`, `agent/validate.py`, `agent/vlm.py` |
| Layer 5 — Schemas/Utilities | DB models, config, shared utils | `agent/db.py`, `agent/models.py`, `agent/config.py`, `utils/` |

---

## 4. Module Reference

### `mutual_fund_ingestion/agent/config.py`

`AgentConfig` dataclass — mirrors all CLI flags with sensible defaults.

| Field | Type | Default | Description |
|---|---|---|---|
| `task_urls` | `list[str]` | `[]` | Task URL seed list |
| `database_url` | `str` | required | PostgreSQL connection string |
| `max_pages` | `int` | `500` | Max pages to crawl |
| `max_depth` | `int` | `5` | Max crawl depth |
| `max_files` | `int` | `200` | Max files to download |
| `use_browser` | `bool` | `False` | Enable Playwright fallback |
| `headless` | `bool` | `True` | Run browser headless |
| `use_vlm` | `bool` | `False` | Enable VLM page analysis |
| `vlm_endpoint` | `str` | `"http://localhost:11434"` | Ollama endpoint |
| `vlm_model` | `str` | `"llama3.2"` | Ollama model name |
| `keep_raw_files` | `bool` | `False` | Retain raw files after successful parse |
| `keep_failed_raw_files` | `bool` | `True` | Retain raw files for failed parses |
| `max_raw_file_size_mb` | `float` | `100.0` | Max raw file size for retention |
| `temp_dir` | `Path` | `tempfile.gettempdir()` | Temp directory for artifacts |
| `dry_run` | `bool` | `False` | No DB writes |
| `log_level` | `str` | `"WARNING"` | Logging level |

### `mutual_fund_ingestion/agent/models.py`

```python
@dataclass
class ParserResult:
    dataset_type: str           # e.g. "nav_history", "portfolio_holdings"
    rows: list[dict]            # Parsed records
    parse_errors: list[str]    # Error messages
    metadata: dict[str, Any]    # Parser name, confidence, row count, etc.

@dataclass
class AgentResult:
    run_id: str
    status: str                 # "completed", "failed", "partial"
    pages_visited: int
    links_discovered: int
    files_downloaded: int
    rows_inserted: int
    rows_quarantined: int
    retry_tasks: int
    errors: list[dict]         # [{"url": str, "error": str, ...}]

# Runtime record types
@dataclass
class SourcePageRecord: ...
@dataclass
class DiscoveredLinkRecord: ...
@dataclass
class DatasetCandidateRecord: ...
@dataclass
class RawArtifactRecord: ...
```

### `mutual_fund_ingestion/agent/discovery.py`

```python
class DiscoveryEngine:
    def add_urls(urls: list[str], parent: str | None, depth: int) -> None
    def fetch(url: str) -> tuple[int | None, str | None]  # status_code, html
    def extract_links(html: str, source_url: str) -> list[dict]  # [{url, text, title}]
    def score_relevance(url: str, text: str, title: str) -> tuple[float, str | None]
    def classify_dataset_type(url: str, text: str) -> tuple[str, str]  # (dataset_type, file_type)
    def should_follow(url: str) -> bool  # domain policy

def classify_dataset_type(url: str, text: str) -> tuple[str, str]/.:
    # Classifies by URL path + extension
    # Returns (dataset_type, file_type) or ("unknown", "unknown")
    # NAV: /NAV.txt, /nav-history, .csv
    # Portfolio: /portfolio, .xlsx, .xls
    # Factsheet: /factsheet, .pdf
    # AMC list: /amc, /associate-companies
    # Scheme master: /scheme_master.csv, /schemes
```

### `mutual_fund_ingestion/agent/browser.py`

```python
@dataclass
class BrowserResult:
    html: str
    screenshot_path: Path | None
    links: list[dict]
    downloads: list[str]        # detected download URLs
    network_log: list[dict]
    error: str | None

class BrowserUnavailable(Exception): ...

def extract_with_browser(
    url: str,
    debug_dir: Path,
    headless: bool = True,
    timeout: float = 30.0,
    screenshot: bool = True,
    capture_network: bool = True,
) -> BrowserResult:
    # Uses Playwright. Installs chromium if needed.
    # Returns rendered HTML, screenshot, detected links/downloads.
    # Raises BrowserUnavailable if Playwright is not installed.
```

### `mutual_fund_ingestion/agent/extract.py`

```python
@dataclass
class ArtifactResult:
    local_path: Path
    checksum: str               # SHA256 hex
    content_type: str
    size_bytes: int
    error: str | None

class ArtifactCollector:
    def __init__(self, config: AgentConfig)
    def collect(self, url: str, dataset_candidate: dict) -> ArtifactResult
    def collect_from_content(self, content: bytes, url: str) -> ArtifactResult
    def cleanup(self) -> None   # Delete temp files per retention policy
```

### `mutual_fund_ingestion/agent/parser/__init__.py`

```python
PARSER_ROUTER: dict[tuple[str, str], str] = {
    ("nav_history", "text"):       "nav_text",
    ("nav_history", "csv"):         "nav_csv",
    ("amc_list", "html"):          "amc_html",
    ("amc_list", "csv"):           "amc_csv",
    ("portfolio_holdings", "xlsx"): "portfolio_xlsx",
    ("portfolio_holdings", "xls"):  "portfolio_xls",
    ("portfolio_holdings", "csv"): "portfolio_csv",
    ("scheme_master", "csv"):       "scheme_master_csv",
    ("scheme_master", "html"):      "scheme_master_html",
}

def parse_file(
    path: str | Path | None,
    dataset_type: str,
    file_type: str,
    content: str | None = None,
) -> ParserResult:
    # Routes to appropriate parser. path OR content required.
    # Returns ParserResult with rows, errors, metadata.

def route_parser(dataset_type: str, file_type: str) -> str | None:
    # Returns parser name from PARSER_ROUTER, or None.
```

### `mutual_fund_ingestion/agent/parser/nav.py`

```python
def parse_nav_text(content: str) -> ParserResult:
    # Parses AMFI plain-text NAV format:
    # MUTUAL FUND
    # AMC Name
    # Scheme Name
    # Date
    # NAV Value
    # Returns rows with: scheme_name, nav_date, nav_value, amc_name, source_url

def parse_nav_csv(content: str) -> ParserResult:
    # Parses AMFI CSV NAV format with header: Scheme Name, Date, NAV
    # Returns rows with: scheme_name, nav_date, nav_value, source_url
```

### `mutual_fund_ingestion/agent/parser/amc.py`

```python
def parse_amc_html(content: str) -> ParserResult:
    # Parses AMC provider list HTML pages.
    # Extracts: amc_name, website_url (from href), source_url
    # Uses BeautifulSoup to find <a> tags with relevant hrefs.
    # Returns rows with: amc_name, website_url, source_url
```

### `mutual_fund_ingestion/agent/parser/portfolio.py`

```python
def parse_portfolio_excel(path: str | Path) -> ParserResult:
    # Parses Excel (.xlsx, .xls) portfolio disclosure files.
    # Uses openpyxl for .xlsx, xlrd for .xls.
    # Column alias mapping: scheme_name ← ["Scheme Name", "Scheme", "Fund"], etc.
    # Returns rows with: scheme_name, industry, sector, market_value, percentage_to_nav, ...

def _parse_portfolio_csv(content: str) -> ParserResult:
    # Parses CSV portfolio files with the same column mapping.
    # Returns rows with: scheme_name, industry, sector, market_value, percentage_to_nav, ...
```

### `mutual_fund_ingestion/agent/validate.py`

```python
def validate_nav_record(record: dict) -> tuple[bool, str | None]:
    # Valid: scheme_name required, nav_value > 0, date parseable
    # Returns (True, None) or (False, error_message)

def validate_portfolio_record(record: dict) -> tuple[bool, str | None]:
    # Valid: scheme_name, industry required, percentage_to_nav in [0, 100]
    # Returns (True, None) or (False, error_message)

def validate_and_filter_records(
    records: list[dict],
    dataset_type: str,
) -> tuple[list[dict], list[dict]]:
    # Splits records into valid + quarantined.
    # Quarantined records get "_validation_error" field added.
    # Returns (valid_records, quarantined_records)
```

### `mutual_fund_ingestion/agent/vlm.py`

```python
class VLMClient(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def analyze_page(self, payload: PageAnalysisPayload) -> PageAnalysisDecision: ...

@dataclass
class PageAnalysisPayload:
    url: str
    text_snippet: str
    file_type: str
    dataset_type: str
    screenshot_path: Path | None = None

@dataclass
class PageAnalysisDecision:
    decision: str        # "relevant", "irrelevant", "unsure"
    reasoning: str
    suggested_dataset_type: str | None
    suggested_parser: str | None
    confidence: float

class NullVLMClient(VLMClient):
    # Always available. Always returns decision="unsure" with reasoning.
    # Safe default — never blocks the pipeline.

class OllamaVLMClient(VLMClient):
    # Requires local Ollama server at configured endpoint.
    # Sends PageAnalysisPayload to /api/generate.
    # Returns parsed PageAnalysisDecision.
    # Check is_available() first — returns False if server not responding.
```

### `mutual_fund_ingestion/agent/db.py`

17 SQLAlchemy declarative models. See Section 5 for all table definitions.

```python
def create_tables(engine: Engine) -> None:
    # Creates all 17 tables using Base.metadata.create_all(engine)

def get_session_maker(database_url: str) -> sessionmaker:
    # Creates SQLAlchemy engine + sessionmaker from DATABASE_URL env var or arg
```

### `mutual_fund_ingestion/agent/runner.py`

```python
class IngestionRunner:
    def __init__(self, config: AgentConfig)
    def run(self) -> AgentResult:/
        # Full pipeline:
        # 1. Add task URLs to discovery queue
        # 2. BFS crawl with depth limit and page limit
        # 3. For each page: fetch → extract links → score relevance → classify
        # 4. For dataset candidates: collect artifact (HTTP or Playwright)
        # 5. For each artifact: parse → validate → quarantine
        # 6. DB insert (when session is wired)
        # 7. Return AgentResult with run stats
```

---

## 5. Database Schema — 17 Tables

All tables use `UUID` primary keys, `TIMESTAMPTZ` for timestamps, and `JSONB` for flexible metadata. Full CREATE TABLE statements in `docs/design/task_url_agent_design_pack/all_specs/07_postgresql_schema.md`.

### Provenance Tables

| Table | Description |
|---|---|
| `ingestion_runs` | Run identity: id, started_at, finished_at, status, config_json, pages_seen, files_seen, rows_inserted, rows_rejected, error_summary |
| `task_urls` | Seed URLs per run: id, run_id, url, status, notes, created_at |
| `source_pages` | Pages crawled: id, run_id, url, canonical_url, parent_url, domain, title, status_code, content_type, page_relevance, html_snapshot_path, screenshot_path, metadata_json |
| `discovered_links` | Links found per page: id, run_id, source_page_id, url, anchor_text, link_type, dataset_type_hint, file_type_hint, should_follow, relevance_score, reason |
| `dataset_candidates` | Relevant datasets discovered: id, run_id, source_page_id, url, dataset_type, provider_hint, download_method, file_type, requires_browser, requires_form, requires_vlm, confidence, status |
| `raw_artifacts` | Downloaded files: id, run_id, dataset_candidate_id, source_url, artifact_type, file_type, content_type, checksum, size_bytes, local_path, retained, fetch_timestamp |

### Canonical Data Tables

| Table | Description |
|---|---|
| `amcs` | Asset management companies: id, name, normalized_name, amfi_code, website_url, source_url. UNIQUE(normalized_name) |
| `schemes` | Mutual fund schemes: id, amc_id, scheme_code, scheme_name, normalized_scheme_name, category, sub_category, scheme_type, benchmark. UNIQUE(scheme_code) |
| `nav_history` | Daily NAV values: id, scheme_id, scheme_code, nav_date, nav_value, repurchase_price, sale_price, source_url, raw_artifact_id. UNIQUE(scheme_code, nav_date) |
| `documents` | Downloaded disclosure documents: id, raw_artifact_id, document_type, amc_id, scheme_id, reporting_date, source_url, file_type, checksum |
| `instruments` | Securities (stocks/bonds): id, isin, name, normalized_name, instrument_type, issuer, sector |
| `portfolio_snapshots` | Portfolio disclosure snapshots: id, amc_id, scheme_id, reporting_date, document_id, source_url, parser_version, validation_status |
| `portfolio_holdings` |Holdings per snapshot: id, snapshot_id, instrument_id, security_name, isin, sector, asset_class, quantity, market_value, percentage_to_nav, rating |

### Pipeline Tables

| Table | Description |
|---|---|
| `staging_rows` | Pre-validation parsed rows: id, run_id, raw_artifact_id, dataset_type, row_number, raw_row_json, parsed_fields_json, parser_name |
| `validation_results` | Per-check validation results: id, run_id, entity_type, entity_id, check_name, severity, status, message |
| `quarantine_rows` | Invalid rows: id, run_id, raw_artifact_id, dataset_type, reason, raw_data_json, parser_error, retryable |
| `retry_queue` | Retry tasks: id, run_id, url, task_type, failure_reason, retry_count, next_retry_at, status |

### Initialize Database

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/mutual_funds"
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"
```

---

## 6. CLI Commands

### run-agent — Main Ingestion Command

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --task-url "https://www.hdfcfund.com/portfolio" \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds" \
  --max-pages 500 \
  --max-depth 5 \
  --max-files 200 \
  --use-browser \
  --headless \
  --use-vlm \
  --vlm-endpoint "http://localhost:11434" \
  --vlm-model "llama3.2" \
  --keep-raw-files \
  --keep-failed-raw-files \
  --dry-run \
  --log-level INFO
```

### init-db — Create Database Schema

```bash
python -m mutual_fund_ingestion init-db \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds"
```

### Phase 1 Commands (existing)

```bash
# Phase 1A: Source registry bootstrap
python -m mutual_fund_ingestion bootstrap-sources

# Phase 1B: Provider profiling
python -m mutual_fund_ingestion profile-providers --limit 3

# Full Phase 1
python -m mutual_fund_ingestion phase-1 --limit 3

# Dry run
python -m mutual_fund_ingestion bootstrap-sources --dry-run --no-reference-network
```

---

## 7. Parsing System

### 7.1 Parser Router

The router dispatches by `(dataset_type, file_type)` tuple:

```
(dataset_type, file_type) → parser_name → function

("nav_history", "text")     → "nav_text"     → parse_nav_text()
("nav_history", "csv")      → "nav_csv"      → parse_nav_csv()
("amc_list", "html")        → "amc_html"     → parse_amc_html()
("portfolio_holdings", "xlsx") → "portfolio_xlsx" → parse_portfolio_excel()
("portfolio_holdings", "csv")  → "portfolio_csv"  → _parse_portfolio_csv()
("scheme_master", "csv")    → "scheme_master_csv" → NOT YET IMPLEMENTED
("scheme_master", "html")   → "scheme_master_html" → NOT YET IMPLEMENTED
```

### 7.2 Parser Output

Every parser returns `ParserResult`:

```python
@dataclass
class ParserResult:
    dataset_type: str           # "nav_history", "portfolio_holdings", etc.
    rows: list[dict]           # Parsed records with standardized field names
    parse_errors: list[strRU     # Non-fatal error messages (e.g. unparseable row)
    metadata: dict[str, Any]   # {
                                #   "parser": "nav_text",
                                #   "row_count": 150,
                                #   "source_url": "...",
                                #   "file_type": "text",
                                # }

###  hdmi
## 7.3 NAV Parser Details

**Text format** (AMFI daily NAV):
```
MUTUAL FUND
HDFC Mutual Fund
HDFC Top 100 Fund
14-Jun-2025
31.456
```

Parses 4-line blocks: `[MUTUAL FUND marker, AMC name, Scheme name, Date, NAV]`

**CSV format**: `Scheme Name,Date,NAV` header with comma-separated rows.

### 7.4 Portfolio Parser Details

Uses column alias mapping to handle different AMC file formats:

| Standard field | Aliases |
|---|---|
| `scheme_name` | Scheme Name, Scheme, Fund, Mutual Fund Scheme |
| `industry` | Industry, Sector, Industry/Sector |
| `market_value` | Market Value, Marketvalue, Value, Market Cap |
| `percentage_to_nav` | % to NAV, Percentage to NAV, % NAV, Weight |

Supports `.xlsx` (openpyxl), `.xls` (xlrd), and `.csv` formats.

---

## 8. Validation and Quarantine

### 8.1 NAV Validation Rules

- `scheme_name` must be non-empty
- `nav_value` must be > 0
- `nav_date` must be parseable as a date

### 8.2 Portfolio Validation Rules

- `scheme_name` must be non-empty
- `industry` must be non-empty
- `percentage_to_nav` must be in range [0, 100]
- `market_value` must be >= 0 (if present)

### 8.3 Quarantine Output

Quarantined rows are returned with `_validation_error` field added:

```python
{
    "scheme_name": "HDFC Top 100 Fund",
    "nav_value": -5.0,
    "nav_date": "14-Jun-2025",
    "_validation_error": "nav_value must be > 0, got -5.0"
}
```

### 8.4 Retry Queue

Failed dataset candidates (network errors, parse errors) are added to `retry_queue`.
, with:
- `task_type`: "fetch", "parse", "browser"
- `failure_reason`: description
- `retry_count`: number of attempts
- `next_retry_at`: scheduled retry time
- `status`: "pending", "in_progress", "completed", "failed"

---

## 9. VLM Integration

### 9.1 Architecture

`VLMClient` is an abstract base class. Two implementations:

| Class | Description | When to use |
|---|---|---|
| `NullVLMClient` | No-op, always returns `decision="unsure"` | Default. Safe for production. |
| `OllamaVLMClient` | Calls local Ollama server | When local GPU/CPU can run Ollama |

### 9.2 When VLM Is Invoked

VLM is only invoked when `--use-vlm` is set AND the VLM client returns `is_available() == True`.

### 9.3 Ollama Setup

```bash
# Install Ollama
brew install ollama  # macOS
# or: curl -fsSL https://ollama.com/install.sh | sh  # Linux

# Pull model
ollama pull llama3.2

# Start server (runs on port 11434 by default)
ollama serve
 pgrep ollama || ollama serve &
```

---

## 10. Testing

### 10.1 Test Files

| File | Tests | Coverage |
|---|---|---|
| `tests/test_mutual_fund_ingestion.py` | 29 | Phase 1A/1B: registry, model validation, extraction, profiling, artifacts, reports, CLI |
| `tests/test_agent.py` | 21 | Agent: config defaults, parser routing, NAV text/CSV, AMC HTML, validation, CLI dry-run |

### 10.2 Run Tests

```bash
python -m pytest tests/ -v
# 50 tests, all passing
```

---

## 11. Known Gaps — Remaining Work

### 11.1 Missing Parsers

| Dataset Type | File Types | Status |
|---|---|---|
| `scheme_master` | csv, html | ❌ Not implemented |
| `factsheet` | html, pdf, csv | ❌ Not implemented |
| `sid` | pdf | ❌ Not implemented |
| `kim` | pdf | ❌ Not implemented |
| `ter` | pdf, html | ❌ Not implemented |
| `statutory_disclosure` | pdf, html | ❌ Not implemented |
| `aum_aaum` | xlsx, csv | ❌ Not implemented |

### 11.2 Missing Operational Commands

| Command | Purpose | Status |
|---|---|---|
| `retry-failed` | Re-process retry_queue entries | ❌ Not implemented |
| `inspect-run` | Show run details by run_id | ❌ Not implemented |
| `export-run-summary` | Export run stats as JSON/CSV | ❌ Not implemented |

### 11.3 Incomplete Integration

| Component | Status | Notes |
|---|---|---|
| `runner.run()` → DB insert | ⚠️ Partial | Stats tracked; session wiring not yet complete |
| Phase 1A/1B → `utils/` | ⚠️ Deferred | Backward compatible; will refactor |
| `scheme_master` parser | ❌ Missing | Needed for `schemes` table population |

---

## 12. Implementation Roadmap

```
Phase 1A  [✅ COMPLETE]  Source registry bootstrap from curated + AMFI + SEBI
Phase 1B  [✅ COMPLETE]  Provider profiling with strategy detection
Phase 1.5 [⏳ NEXT]       Strategy resolution — load profiles, try known strategy
Task-URL Agent [✅ CORE DONE]  Agent pipeline (discovery → extract → parse → validate)
Phase 2   [❌ NOT STARTED]  Raw document discovery and download
Phase 3   [❌ NOT STARTED]  Document classification
Phase 4   [⚠️ PARTIAL]     Parsing and staging
Phase 5+  [❌ NOT STARTED]  Validation, quarantine, canonical PostgreSQL, analytics
```

---

## 13. Phase-by-Phase Implementation Guide

### Phase 1A: Source Registry Bootstrap — ✅ COMPLETE

**What it does:** Bootstrap a provenance-aware source registry from `configs/amc_sources.yaml` + AMFI + SEBI.

**Modules:**
- `source_discovery.py` — discovers candidate URLs from AMFI/SEBI
- `source_registry.py` — merges candidates, deduplicates, writes JSONL + latest snapshot
- `registry.py` — loads and validates YAML registry
- `models.py` — `AMCSource`, `SourceRegistryEntry`, `SourceCandidate`

**Run:**
```bash
python -m mutual_fund_ingestion bootstrap-sources
python -m mutual_fund_ingestion bootstrap-sources --dry-run
```

---

### Phase 1B: Provider Profiling — ✅ COMPLETE

**What it does:** Profile each enabled AMC provider website and detect the best extraction strategy.

**Strategy detection order:**
1. `static_html` — links/API hints found in static HTML
2. `network_api` — API endpoints detected in HTML
3. `playwright` — requires JS rendering
4. `vlm_required` — needs VLM for classification
5. `manual_review` — not automatable
6. `failed_blocked` — site unreachable

**Run:**
```bash
python -m mutual_fund_ingestion profile-providers --limit 3
python -m mutual_fund_ingestion phase-1 --limit 3
```

---

### Phase 1.5: Strategy Resolution — ⏳ NEXT

**What it does:** Load provider profiles from Phase 1B, try the known extraction strategy first, re-profile if it fails.

**Logic:**
```python
for provider in load_latest_profiles():
    strategy = provider.detected_strategy
    try:
        result = execute_strategy(strategy, provider)
        if result.success:
            pass
        else:
            re_profile(provider)
    except UnexpectedChange:
        re_profile(provider)
```

---

### Task-URL Agent Core — ✅ COMPLETE

**Completed modules:** See Section 3.

**Next step:** Connect `parser_result.rows` to SQLAlchemy session for DB insert.

---

### Phase 2: Raw Document Discovery and Download — ❌ NOT STARTED

**What it does:** Follow links from AMFI → AMC disclosure pages → download raw files.

**Key steps:**
1. Load Phase 1A source registry (AMC disclosure page URLs)
2. For each AMC: fetch disclosure page, find file links (PDF, XLS, XLSX, CSV, ZIP)
3. Use Playwright for AMFI's JavaScript-driven disclosure selector
4. Download files with SHA256 checksum and sidecar metadata
5. Skip already-downloaded files (hash-based dedup)
6. Apply polite rate limiting (1 request/2s per domain)

---

### Phase 3: Document Classification — ❌ NOT STARTED

**What it does:** Classify downloaded files by document type.

**Document types:**
- `portfolio_disclosure` — Excel/CSV portfolio holdings
- `factsheet` — fund factsheet (PDF/HTML)
- `sid` — Scheme Information Document (PDF)
- `kim` — Key Information Memorandum (PDF)
- `ter` — Total Expense Ratio (PDF/HTML)
- `statutory_disclosure` — statutory documents (PDF)
- `nav_history` — NAV text/CSV files
- `amc_list` — AMC provider list pages

---

### Phase 4: Parsing and Staging — ⚠️ PARTIAL

**Status:** 3 parsers implemented (NAV text/CSV, AMC HTML, portfolio). 5+ parsers missing.

**Parser priority order:**
1. NAV parser ✅
2. AMC/provider list parser ✅
3. Excel/CSV portfolio parser ✅
4. `scheme_master` parser ❌ → needed for `schemes` table
5. Factsheet parser ❌
6. SID/KIM parser ❌
7. TER parser ❌

---

### Phase 5: Validation, Quarantine, Canonical Loading — ❌ NOT STARTED

**Validation per dataset type:**

| Dataset | Required fields | Range checks | Cross-record checks |
|---|---|---|---|
| `nav_history` | scheme_name, nav_date, nav_value | nav_value > 0 | scheme_code must match known scheme |
| `portfolio_holdings` | scheme_name, industry, percentage_to_nav | pct in [0, 100] | — |
| `amcs` | name | — | normalized_name unique |

---

### Phase 6+: Analytics and Agentic Querying — ❌ NOT STARTED

**Future phases for financial analytics:**

```python
# Example queries once tables are populated:
- query_holdings(scheme_name="HDFC Top 100 Fund")
- compute_consensus_stocks(top_n=20)
- compute_fund_overlap(fund_a, fund_b)
- compute_sector_exposure(scheme_name)
- compute_monthly_nav_delta(scheme_name)
```

---

## 14. Data Priority and Source Strategy

### 14.1 Known AMFI NAV Endpoints

```
https://www.amfiindia.com/sp-ups/NAV.txt               # Daily NAV text
https://www.amfiindia.com/home/NAVtxtfilelisting       # NAV file listing
https://www.amfiindia.com/nav-history                   # NAV history pages
```

### 14.2 Known AMC Portfolio Disclosure Patterns

| AMC | URL Pattern |
|---|---|
| HDFC | `https://www.hdfcfund.com/statutory-disclosure/portfolio-disclosure` |
| ICICI Prudential | `https://www.iciciprupam.com/disclosures` |
| SBI | `https://www.sbimf.com/disclosures` |

---

## 15. CLI Reference

### Full run-agent Command

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds" \
  --max-pages 500 \
  --max-depth 5 \
  --max-files 200 \
  --use-browser \
  --headless \
  --use-vlm \
  --vlm-endpoint "http://localhost:11434" \
  --vlm-model "llama3.2" \
  --keep-raw-files \
  --keep-failed-raw-files \
  --max-raw-file-size-mb 100.0 \
  --temp-dir /tmp/mf_agent \
  --dry-run \
  --log-level INFO
```

---

## 16. Setup and Installation

### 16.1 Requirements

```bash
# Core dependencies
pip install -r requirements.txt

# Agent additionally requires
pip install psycopg2-binary        # Already in requirements.txt

# Browser support (optional)
pip install playwright
playwright install chromium

# VLM support (optional)
# Install Ollama: https://ollama.com/
ollama pull llama3.2
ollama serve
```

### 16.2 requirements.txt

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
PyYAML>=6.0.0
pytest>=8.0.0
playwright>=1.40.0
openpyxl>=3.1.0
xlrd>=2.0.1
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
```

---

## 17. Verification Commands

### Run all tests
```bash
python -m pytest tests/ -v
# 50 tests passing
```

### Initialize database
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/mutual_funds"
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"
```

### Dry-run agent (no network writes)
```bash
python -m mutual_f铃声 asset  my  phone
```

### Dry-run agent (no network writes)
```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "postgresql://localhost/test" \
  --max-pages 5 \
  --dry-run \
  --log-level INFO
```

### Open inspection notebook
```bash
jupyter notebook notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb
```

---

## 18. Known Issues and Workarounds

### 18.1 AMFI site unreachable from sandbox network

**Symptom:** HTTP requests to `www.amfiindia.com` timeout.

**Workaround:** Run from an environment with internet access. The agent handles timeout gracefully.

### 18.2 Playwright browser not installed

**Symptom:** `BrowserUnavailable: No supported browser found`

**Workaround:**
```bash
playwright install chromium
```

### 18.3 SQLAlchemy import failure

**Symptom:** `ImportError: No module named 'sqlalchemy'`

**Workaround:**
```bash
pip install sqlalchemy psycopg2-binary
```

### 18.4 VLM unavailable in production

**Symptom:** `OllamaVLMClient.is_available()` returns `False`

**Workaround:** VLM is optional. The `NullVLMClient` is the default. Omit `--use-vlm` to run without VLM.

### 18.5 AMFI uses JavaScript-driven disclosure selectors

**Symptom:** Static HTML has no file links on AMFI disclosure pages.

**Workaround:** Use Playwright (`--use-browser`).

---

*Document version: 2.0 — 2026-06-15*
*Source specs: `docs/design/task_url_agent_design_pack/all_specs/`*
