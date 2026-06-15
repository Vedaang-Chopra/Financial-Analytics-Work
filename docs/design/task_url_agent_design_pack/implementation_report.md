# Task-URL Driven Mutual Fund Ingestion Agent — Implementation Document

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Module Reference](#3-module-reference)
4. [Database Schema](#4-database-schema)
5. [CLI Commands](#5-cli-commands)
6. [Data Flow](#6-data-flow)
7. [Configuration](#7-configuration)
8. [Parser System](#8-parser-system)
9. [Validation & Quarantine](#9-validation--quarantine)
10. [VLM Integration](#10-vlm-integration)
11. [Testing](#11-testing)
12. [Usage Examples](#12-usage-examples)
13. [Build Status](#13-build-status)

---

## 1. Overview

The Task-URL Driven Mutual Fund Ingestion Agent (`agent/`) is a Python package that accepts one or more task URLs, discovers relevant Indian mutual fund data sources from those URLs and linked pages, extracts raw data, classifies datasets, parses structured records, validates them, and loads real rows into PostgreSQL.

**Primary goal:** PostgreSQL populated with useful mutual fund data, not phase reports or notebooks.

**Success criterion:** Real rows written into PostgreSQL tables via `python -m mutual_fund_ingestion run-agent`.

**Data priority order:**
1. AMC/provider list
2. Scheme metadata / scheme master
3. NAV history and latest NAV
4. Portfolio disclosure holdings
5. Factsheet metadata
6. TER, SID, KIM, statutory disclosures, AUM/AAUM

---

## 2. Architecture

### 2.1 Module Structure

```
mutual_fund_ingestion/
├── agent/                    # NEW: End-to-end ingestion agent (Layer 2-4)
│   ├── __init__.py
│   ├── db.py               # SQLAlchemy models (17 tables)
│   ├── models.py           # Runtime dataclasses (ParserResult, etc.)
│   ├── config.py           # AgentConfig from CLI args
│   ├── discovery.py        # URL queue, link extraction, relevance scoring
│   ├── browser.py          # Playwright extraction strategy
│   ├── extract.py          # Artifact collector, file download, checksum
│   ├── validate.py         # NAV/portfolio validation, quarantine, retry
│   ├── vlm.py              # Pluggable VLM client (null + Ollama)
│   ├── runner.py            # IngestionRunner orchestration
│   └── parser/             # Parser router + individual parsers
│       ├── __init__.py     # ParserRouter dispatch by (dataset_type, file_type)
│       ├── nav.py          # AMFI NAV text/CSV parser
│       ├── amc.py          # AMC provider list HTML parser
│       └── portfolio.py    # Excel portfolio disclosure parser
├── cli.py                   # Updated: run-agent + init-db subcommands
├── utils/                   # Shared utilities (consolidated from duplicate code)
│   ├── http.py             # HttpSettings + build_session
│   ├── url_utils.py        # canonical_url, file_type_from_url, safe_name, slugify
│   └── text_utils.py       # normalize_amc_name
tests/
├── test_agent.py           # 21 tests for agent module
└── test_mutual_fund_ingestion.py  # 29 existing Phase 1 tests
```

### 2.2 Layer Model

| Layer | Description | Files |
|---|---|---|
| Layer 2 — Public Interface | CLI entry point | `cli.py` |
| Layer 3 — Orchestration | Pipeline runner | `agent/runner.py` |
| Layer 4 — Core Logic | Discovery, extraction, parsing, validation | `agent/discovery.py`, `agent/browser.py`, `agent/extract.py`, `agent/parser/`, `agent/validate.py`, `agent/vlm.py` |
| Layer 5 — Schemas/Utilities | DB models, config, shared utils | `agent/db.py`, `agent/models.py`, `agent/config.py`, `utils/` |

### 2.3 Key Design Decisions

1. **Staging-first:** All parsed data goes through staging tables before canonical loading
2. **Strategy order enforced:** static HTTP → HTML parsing → Playwright → VLM → quarantine
3. **Raw file retention policy:** Delete after successful parse by default; keep failed files up to configurable size threshold
4. **VLM is pluggable and disabled by default** — only activates when `--use-vlm true`
5. **SQLAlchemy lazy imports** in CLI — agent imports only load when `run-agent` or `init-db` commands are invoked
6. **Dataset type routing** — parsers dispatched by `(dataset_type, file_type)` tuple

---

## 3. Module Reference

### 3.1 `utils/http.py`

```python
class HttpSettings:
    timeout_seconds: float = 30
    retries: int = 2
    backoff_factor: float = 1
    user_agent: str = DEFAULT_USER_AGENT

def build_session(settings: HttpSettings | None = None) -> requests.Session
```

- User-Agent: `"Financial-Analytics-Work-Agent/1.0"`
- Retries on 429, 500, 502, 503, 504 with exponential backoff
- Consolidates duplicate `HttpSettings` + `build_session` from `mutual_fund_ingestion/http.py` and `amfi_disclosure/http.py`

### 3.2 `utils/url_utils.py`

```python
def canonical_url(value: str) -> str
def file_type_from_url(value: str) -> str | None  # pdf, xls, xlsx, csv, zip
def safe_name(value: str) -> str  # "360 ONE Mutual Fund" → "360_one_mutual_fund"
def slugify(value: str) -> str     # "My Report.xlsx" → "my-report-xlsx"
```

### 3.3 `utils/text_utils.py`

```python
def normalize_amc_name(value: str) -> str
```

- Removes common suffixes: "Mutual Fund", "MF", "Asset Management Company", "AMC"
- Used for deduplication and UNIQUE constraints in `amcs` table

### 3.4 `agent/config.py`

```python
@dataclass(frozen=True)
class AgentConfig:
    task_urls: list[str]
    database_url: str
    max_pages: int = 500
    max_depth: int = 5
    max_files: int = 200
    max_runtime_minutes: int = 60
    max_file_size_mb: float = 50
    use_browser: bool = True
    headless: bool = True
    use_vlm: bool = False
    vlm_endpoint: str = "http://localhost:11434"
    vlm_model: str | None = None
    vlm_confidence_threshold: float = 0.7
    keep_raw_files: bool = False
    keep_failed_raw_files: bool = True
    max_retained_file_size_mb: float = 50
    raw_dir: Path = Path("data/raw/mutual_funds/runtime")
    temp_dir: Path = Path("data/tmp/mutual_funds/runtime")
    log_level: str = "INFO"
    fail_fast: bool = False
    dry_run: bool = False
    dataset_type_priority: list[str] = [...]
```

### 3.5 `agent/models.py`

```python
@dataclass(frozen=True)
class AgentResult:
    run_id: str
    status: str  # "completed", "failed"
    pages_visited: int
    links_discovered: int
    files_downloaded: int
    intervals_staged: int
    rows_inserted: int
    rows_quarantined: int
    retry_tasks: int
    error_summary: dict[str, Any]

@dataclass(frozen=True)
class ParserResult:
    dataset_type: str          # e.g. "nav_history", "portfolio_disclosure"
    parser_name: str          # e.g. "nav_text_v1"
    parser_version: str       # e.g. "1.0"
    confidence: float         # 0.0 to 1.0
    records: list[dict[str, Any]]  # parsed rows
    warnings: list[str]
    errors: list[str]
    metadata: dict[str, Any]
```

### 3.6 `agent/discovery.py`

```python
class DiscoveryEngine:
    def __init__(self, session: requests.Session, settings: HttpSettings)
    def add_urls(self, urls: list[str], parent: str | None = None, depth: int = 0) -> None
    def fetch(self, url: str) -> tuple[int, str | None]  # (status_code, html)
    def extract_links(self, html: str, source_url: str) -> list[dict[str, str]]
    def score_relevance(self, url: str, text: str, title: str) -> tuple[float, str | None]
    def classify_dataset(self, url: str, text: str) -> str | None
    def get_file_type(self, url: str) -> str | None
    def get_domain(self, url: str) -> str
    def is_off_domain(self, url: str, task_domain: str) -> bool
```

**Dataset type hints:**
```python
DATASET_TYPE_HINTS = {
    "portfolio_disclosure": ["portfolio", "holding", "monthly portfolio"],
    "factsheet": ["factsheet", "fact sheet"],
    "nav_history": ["nav", "net asset value", "historical nav"],
    "scheme_master": ["scheme", "scheme code", "scheme name"],
    "amc_provider_list": ["amc", "mutual fund", "fund house", "members"],
    "ter": ["total expense ratio", "ter"],
    "sid": ["scheme information document", "sid"],
    "kim": ["key information memorandum", "kim"],
    "statutory_disclosure": ["statutory", "disclosure"],
    "aum_aaum": ["aum", "aaum"],
}
```

### 3.7 `agent/browser.py`

```python
class BrowserUnavailable(RuntimeError):
    """Raised when Playwright is not installed."""

@dataclass(frozen=True)
class BrowserResult:
    html: str
    screenshot_path: str | None
    links: list[dict[str, str]]
    downloads: list[dict[str, Any]]  # url, content_type, file_type
    network_calls: list[dict[str, Any]]  # url, status, content_type

def extract_with_browser(
    url: str,
    debug_dir: Path,
    timeout_seconds: float = 30.0,
    headless: bool = True,
) -> BrowserResult
```

### 3.8 `agent/extract.py`

```python
class ArtifactCollector:
    def download(self, url: str, run_id: str) -> dict[str, Any]:
        """
        Downloads file to temp dir, computes SHA256 checksum.
        Returns: {url, file_type, content_type, checksum, size_bytes, local_path, retained, error?}
        """
```

### 3.9 `agent/parser/nav.py`

```python
def parse_nav_text(content: bytes | str, metadata: dict[str, Any]) -> ParserResult
def parse_nav_csv(content: bytes | str, metadata: dict[str, Any]) -> ParserResult
```

- Handles tab/comma/pipe-separated input
- Date formats: `dd-MMM-yyyy`, `yyyy-MM-dd`
- NAV value: strips commas and spaces before float conversion
- Produces records with: `scheme_code`, `nav_date`, `nav_value`, `source_url`

### 3.10 `agent/parser/amc.py`

```python
def parse_amc_html(content: bytes | str, metadata: dict[str, Any]) -> ParserResult
```

- Extracts `<a>` tags from HTML
- Filters for "mutual fund" in text
- Produces records with: `name`, `website_url`, `source_url`

### 3.11 `agent/parser/portfolio.py`

```python
COLUMN_ALIASES = {
    "security_name": ["name of instrument", "security", "company", "name", "instrument", "scrip"],
    "isin": ["isin", "isin code"],
    "quantity": ["quantity", "no. of shares", "units"],
    "market_value": ["market value", "value", "market value (rs. in lakhs)"],
    "percentage_to_nav": ["% to nav", "% net assets", "percentage"],
    "sector": ["industry", "sector", "rating/industry"],
    "rating": ["rating", "credit rating"],
    "maturity_date": ["maturity", "maturity date"],
    "coupon": ["coupon", "coupon rate"],
    "asset_class": ["asset class", "type"],
}
```

- Handles multi-sheet Excel workbooks
- Heuristic column mapping via aliases
- Date parsing: `dd-MMM-yyyy`, `MMM yyyy`, `yyyy-MM-dd`, `dd/MM/yyyy`
- Produces records with: `security_name`, `isin`, `sector`, `percentage_to_nav`, `market_value`, `sheet_name`, `row_number`

### 3.12 `agent/validate.py`

```python
QUARANTINE_REASONS = [
    "unsupported_file_type", "unsupported_dataset_type", "parse_error",
    "missing_required_field", "invalid_date", "invalid_numeric_value",
    "low_parser_confidence", "blocked_or_unreachable", "browser_timeout",
    "vlm_unparseable_response", "download_failed", "file_too_large",
    "pdf_scanned_or_image_based", "unknown_schema",
]

def validate_nav_record(record: dict) -> list[str]
def validate_portfolio_record(record: dict) -> list[str]
def validate_and_filter_records(parser_result, run_id) -> tuple[valid, quarantined]

def write_quarantine_row(run_id, reason, raw_data, parser_error, retryable) -> dict
def write_validation_result(run_id, entity_type, entity_id, check_name, severity, status, message) -> dict
def write_retry_task(run_id, url, task_type, failure_reason, retryable) -> dict
```

### 3.13 `agent/vlm.py`

```python
class VLMClient(ABC):
    @abstractmethod
    def analyze_page(self, payload: PageAnalysisPayload) -> PageAnalysisDecision | None

class NullVLMClient(VLMClient):
    """Default: returns None for all pages."""

class OllamaVLMClient(VLMClient):
    """Calls local Ollama-compatible endpoint (e.g. http://localhost:11434)."""
```

**Payload format:**
```python
PageAnalysisPayload(
    objective="Find mutual fund portfolio disclosure, factsheet, NAV, or scheme data downloads.",
    current_url="...",
    page_title="...",
    visible_text_excerpt="...",
    links=[{"url": "...", "text": "..."}],
    buttons=[],
    forms=[],
    screenshot_path=None,
)
```

**Decision format:**
```json
{
  "page_relevance": "high|medium|low|irrelevant",
  "dataset_hints": ["portfolio_disclosure", "factsheet"],
  "recommended_action": "click|select|download|skip",
  "target_text": "Portfolio Disclosure",
  "form_values": {},
  "avoid_targets": ["Careers", "Contact Us"],
  "reason": "The screenshot shows a monthly portfolio disclosure download section.",
  "confidence": 0.82
}
```

### 3.14 `agent/runner.py`

```python
class IngestionRunner:
    def __init__(self, config: AgentConfig)
    def run(self) -> dict[str, Any]
```

**Pipeline stages:**
1. Add task URLs to discovery queue
2. While queue not empty and `pages_visited < max_pages`:
   a. Pop URL from queue
   b. Skip if already visited
   c. Increment `pages_visited`
   d. Fetch with static HTTP
   e. Extract links and score relevance
   f. Add relevant links to queue
   g. If `--use-browser` and status >= 400, try Playwright fallback
3. Return result dict with all metrics

---

## 4. Database Schema

All 17 tables are defined in `mutual_fund_ingestion/agent/db.py` using SQLAlchemy ORM. Run `python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"` to create them.

### 4.1 Table Map

| Table | Purpose | Key Columns |
|---|---|---|
| `ingestion_runs` | Run metadata | id, started_at, finished_at, status, config_json, pages_seen, files_seen, rows_inserted, rows_rejected, error_summary |
| `task_urls` | Seed URLs | run_id, url, status, notes |
| `source_pages` | Crawled pages | run_id, url, canonical_url, parent_url, domain, title, status_code, page_relevance, html_snapshot_path, screenshot_path |
| `discovered_links` | Extracted links | run_id, source_page_id, url, anchor_text, link_type, dataset_type_hint, file_type_hint, should_follow, relevance_score |
| `dataset_candidates` | High-value URLs | run_id, source_page_id, url, dataset_type, file_type, requires_browser, requires_form, requires_vlm, confidence, status |
| `raw_artifacts` | Downloaded files | run_id, dataset_candidate_id, source_url, artifact_type, file_type, checksum, size_bytes, local_path, retained |
| `amcs` | Canonical AMC list | id, name, normalized_name (UNIQUE), amfi_code, website_url, source_url |
| `schemes` | Canonical scheme list | id, amc_id, scheme_code (UNIQUE), scheme_name, normalized_scheme_name, category, sub_category |
| `nav_history` | NAV time series | id, scheme_id, scheme_code, nav_date (UNIQUE composite), nav_value, repurchase_price, sale_price, source_url |
| `documents` | Document metadata | id, raw_artifact_id, document_type, amc_id, scheme_id, reporting_date, source_url, file_type, checksum |
| `instruments` | Security master | id, isin, name, normalized_name, instrument_type, issuer, sector |
| `portfolio_snapshots` | Portfolio snapshots | id, amc_id, scheme_id, reporting_date, document_id, source_url, validation_status |
| `portfolio_holdings` | Individual holdings | id, snapshot_id, instrument_id, security_name, isin, sector, quantity, market_value, percentage_to_nav, coupon, maturity_date, rating |
| `staging_rows` | Pre-validation rows | run_id, raw_artifact_id, dataset_type, raw_row_json, parsed_fields_json, parser_name, parser_confidence |
| `validation_results` | Validation checks | run_id, entity_type, entity_id, check_name, severity, status, message |
| `quarantine_rows` | Failed rows | run_id, raw_artifact_id, dataset_type, reason, raw_data_json, parser_error, retryable |
| `retry_queue` | Retry tasks | run_id, url, task_type, failure_reason, retry_count, next_retry_at, status |

### 4.2 Indexes

```python
Index("ix_source_pages_run_id", "run_id")
Index("ix_source_pages_domain", "domain")
Index("ix_discovered_links_run_id", "run_id")
Index("ix_dataset_candidates_dataset_type", "dataset_type")
Index("ix_raw_artifacts_checksum", "checksum")
Index("ix_amcs_normalized_name", "normalized_name")
Index("ix_schemes_scheme_code", "scheme_code")
Index("ix_schemes_normalized_sname", "normalized_scheme_name")
Index("ix_nav_history_scheme_code_nav_date", "scheme_code", "nav_date")
Index("ix_portfolio_snapshots_scheme_id_reporting_date", "scheme_id", "reporting_date")
Index("ix_portfolio_holdings_isin", "isin")
Index("ix_portfolio_holdings_security_name", "security_name")
Index("ix_retry_queue_status", "status")
```

---

## 5. CLI Commands

### 5.1 `run-agent`

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --task-url "https://example.com/disclosures" \
  --database-url "$DATABASE_URL" \
  --max-pages 500 \
  --max-depth 5 \
  --max-files 200 \
  --use-browser \
  --headless \
  --use-vlm \
  --vlm-endpoint "http://localhost:11434" \
  --vlm-model "llava" \
  --keep-raw-files \
  --keep-failed-raw-files \
  --dry-run \
  --log-level INFO
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `--task-url` | (required) | Task URL to process. Repeat for multiple. |
| `--task-url-file` | — | File with task URLs (one per line) |
| `--database-url` | (required) | PostgreSQL connection URL |
| `--max-pages` | 500 | Maximum pages to crawl |
| `--max-depth` | 5 | Maximum crawl depth |
| `--max-files` | 200 | Maximum files to download |
| `--max-runtime-minutes` | 60 | Maximum run duration |
| `--max-file-size-mb` | 50 | Skip files larger than this |
| `--use-browser` | False | Enable Playwright browser fallback |
| `--headless` | True | Run browser in headless mode |
| `--use-vlm` | False | Enable VLM-guided page analysis |
| `--vlm-endpoint` | `http://localhost:11434` | Ollama/VLM endpoint |
| `--vlm-model` | None | VLM model name |
| `--keep-raw-files` | False | Retain raw files after parse |
| `--keep-failed-raw-files` | True | Retain failed parse files |
| `--dry-run` | False | No database writes |

### 5.2 `init-db`

```bash
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"
```

Creates all 17 tables in the PostgreSQL database.

---

## 6. Data Flow

```
task_urls (CLI input)
  → IngestionRunner.run()
    → DiscoveryEngine.add_urls()
      → URL queue (deduped by canonical URL)
    → DiscoveryEngine.fetch()          [static HTTP]
      → DiscoveryEngine.extract_links()
        → DiscoveryEngine.score_relevance()   [keyword scoring]
        → DiscoveryEngine.classify_dataset()  [DATASET_TYPE_HINTS]
    → BrowserUnavailable → extract_with_browser()  [Playwright]
      → render HTML, screenshot, network capture
    → ArtifactCollector.download()    [files + SHA256 checksum]
      → temp_dir/run_id/
    → ParserRouter.route_parser()     [by dataset_type, file_type]
      → parse_nav_text() / parse_nav_csv()   → nav_history
      → parse_amc_html()             → amcs
      → parse_portfolio_excel()        → portfolio_holdings
    → validate_and_filter_records()
      → validate_nav_record() / validate_portfolio_record()
      → write_quarantine_row() for invalid records
      → write_retry_task() for retryable failures
    → write_validation_result()
    → [Staging first, then canonical upsert]
    → Result dict with metrics

Output: JSON with run_id, status, pages_visited, links_discovered, rows_inserted, rows_quarantined, retry_tasks
```

---

## 7. Configuration

Configuration is loaded from CLI arguments. No separate YAML config file is required for the agent itself.

**Dataset type priority** (used for crawl scheduling):
```python
[
    "amc_provider_list",
    "scheme_master",
    "nav_history",
    "portfolio_disclosure",
    "factsheet",
]
```

**Domain policy:**
- Always allow task URL domain
- Allow off-domain links if relevant (score > 0.5)
- Track domain authority: `amfi`, `amc_provider`, `registrar`, `regulator`, `exchange`, `unknown`

---

## 8. Parser System

### 8.1 Parser Router

```python
PARSER_ROUTER = {
    ("nav_history", "text"): "nav_text",
    ("nav_history", "csv"): "nav_csv",
    ("nav_history", "html"): "nav_html",
    ("nav_reference", "text"): "nav_text",
    ("amc_provider_list", "html"): "amc_html",
    ("portfolio_disclosure", "xlsx"): "portfolio_excel",
    ("portfolio_disclosure", "xls"): "portfolio_excel",
    ("portfolio_disclosure", "csv"): "portfolio_csv",
}
```

### 8.2 Parser Result Contract

Every parser returns:
```python
ParserResult(
    dataset_type="...",       # e.g. "nav_history"
    parser_name="nav_text_v1",  # versioned parser name
    parser_version="1.0",
    confidence=0.85,
    records=[...],             # list of dicts with parsed fields
    warnings=[...],           # non-fatal issues
    errors=[...],              # parse failures
    metadata={...}             # source_url, sheet_name, etc.
)
```

### 8.3 Column Alias Mapping (Portfolio Parser)

The portfolio parser uses heuristic column mapping with common aliases:

| Target Column | Common Source Column Names |
|---|---|
| `security_name` | Name of Instrument, Security, Company, Name, Instrument, Scrip |
| `isin` | ISIN, ISIN Code, ISIN No |
| `quantity` | Quantity, No. of Shares, Units, Face Value, Nos |
| `market_value` | Market Value, Value, Market Value (Rs. in Lakhs), Fair Value |
| `percentage_to_nav` | % to NAV, % Net Assets, Percentage, % of Net Assets |
| `sector` | Industry, Sector, Rating/Industry |
| `rating` | Rating, Credit Rating |
| `maturity_date` | Maturity, Maturity Date |
| `coupon` | Coupon, Coupon Rate |
| `asset_class` | Asset Class, Type |

---

## 9. Validation & Quarantine

### 9.1 NAV Validation Rules

| Check | Pass Condition | Fail Reason |
|---|---|---|
| scheme_code present | `scheme_code` is non-empty | `missing_scheme_code` |
| NAV value present | `nav_value` is non-empty | `missing_nav_value` |
| NAV value numeric | `float(nav_value)` succeeds | `nav_value_not_numeric` |
| NAV value positive | `float(nav_value) > 0` | `nav_value_not_positive` |
| NAV date present | `nav_date` is non-empty | `missing_nav_date` |
| Source URL present | `source_url` is non-empty | `missing_source_url` |

### 9.2 Portfolio Validation Rules

| Check | Pass Condition | Fail Reason |
|---|---|---|
| Security name present | `security_name` is non-empty | `missing_security_name` |
| Percentage in range | `0 <= percentage_to_nav <= 100` | `percentage_out_of_range` |
| Market value numeric | `float(market_value)` succeeds if present | `market_value_not_numeric` |

### 9.3 Quarantine Reasons

Structured reasons stored in `quarantine_rows.reason`:
- `unsupported_file_type` — file type not supported
- `unsupported_dataset_type` — no parser for dataset type
- `parse_error` — parser threw an exception
- `missing_required_field` — required field absent
- `invalid_date` — unparseable date
- `invalid_numeric_value` — non-numeric value in numeric field
- `low_parser_confidence` — confidence < 0.5
- `blocked_or_unreachable` — HTTP 403/404/timeout
- `browser_timeout` — Playwright timed out
- `vlm_unparseable_response` — VLM returned invalid JSON
- `download_failed` — file download failed
- `file_too_large` — exceeds `max_file_size_mb`
- `pdf_scanned_or_image_based` — PDF has no extractable text
- `unknown_schema` — file format not recognized

---

## 10. VLM Integration

**Off by default.** Enable with `--use-vlm true`.

**Supported backends:**

| Backend | Activation | Endpoint |
|---|---|---|
| `NullVLMClient` | Default (no flag) | N/A |
| `OllamaVLMClient` | `--use-vlm` | `--vlm-endpoint` |

**OllamaVLMClient** calls `{endpoint}/api/generate` with a structured prompt and expects JSON response:
```json
{
  "page_relevance": "high",
  "dataset_hints": ["portfolio_disclosure"],
  "recommended_action": "click",
  "target_text": "Portfolio Disclosure",
  "avoid_targets": ["Careers"],
  "reason": "Found monthly portfolio download section",
  "confidence": 0.82
}
```

---

## 11. Testing

Run all tests:
```bash
python -m pytest tests/ -v
```

**Test suite summary:**

| Test File | Tests | Coverage |
|---|---|---|
| `tests/test_agent.py` | 21 | Config defaults, parser routing, NAV parsing, AMC parsing, validation, quarantine, CLI flags |
| `tests/test_mutual_fund_ingestion.py` | 29 | Registry loading, model validation, source discovery, profiling, artifacts, reports, CLI |

**Total: 50 tests, all passing.**

### Key test cases:

| Test | What it verifies |
|---|---|
| `test_nav_text_parser_with_valid_data` | Parses tab-separated NAV with scheme code, date, value |
| `test_nav_text_parser_with_bad_lines` | Skips unparseable lines, collects errors |
| `test_nav_csv_parser_with_valid_data` | Parses CSV with pandas |
| `test_amc_html_parser_extracts_links` | Extracts AMC names from HTML anchor tags |
| `test_validate_and_filter_records_routes_to_nav_validator` | Valid NAV → valid list, invalid → quarantine |
| `test_parse_file_routes_to_nav_text_parser` | Router dispatches nav_history+text → nav_text parser |
| `test_parse_file_routes_to_amc_html_parser` | Router dispatches amc_provider_list+html → amc_html |
| `test_run_agent_requires_task_url` | CLI accepts --task-url flag |
| `test_run_agent_accepts_multiple_task_urls` | CLI accepts multiple --task-url arguments |
| `test_run_agent_respects_all_flags` | All CLI flags parse correctly |

---

## 12. Usage Examples

### 12.1 Initialize database schema

```bash
python -m mutual_fund_ingestion init-db \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds"
```

### 12.2 Dry-run discovery (no DB writes)

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds" \
  --max-pages 5 \
  --max-depth 1 \
  --dry-run
```

### 12.3 Live ingestion with browser

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds" \
  --max-pages 100 \
  --max-depth 3 \
  --use-browser \
  --headless \
  --keep-raw-files
```

### 12.4 Live ingestion with VLM guidance

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/" \
  --database-url "postgresql://user:pass@localhost:5432/mutual_funds" \
  --max-pages 50 \
  --use-browser \
  --use-vlm \
  --vlm-endpoint "http://localhost:11434" \
  --vlm-model "llava"
```

### 12.5 From Python code

```python
from mutual_fund_ingestion.agent.config import AgentConfig
from mutual_fund_ingestion.agent.runner import IngestionRunner

config = AgentConfig(
    task_urls=["https://www.amfiindia.com/"],
    database_url="postgresql://user:pass@localhost:5432/mutual_funds",
    max_pages=10,
    max_depth=1,
    use_browser=True,
    dry_run=True,
)

runner = IngestionRunner(config)
result = runner.run()
print(result)
```

---

## 13. Build Status

### Completed ✓
- PostgreSQL schema (17 tables with indexes)
- CLI with `run-agent` and `init-db` subcommands
- Discovery engine with URL queue, link extraction, relevance scoring
- Playwright browser extraction (optional)
- Artifact collector with checksum and temp file management
- NAV text and CSV parser → `nav_history` rows
- AMC list HTML parser → `amcs` rows
- Excel portfolio parser with column alias mapping → `portfolio_holdings` rows
- Parser router dispatching by `(dataset_type, file_type)`
- Validation rules for NAV and portfolio rows
- Quarantine writer for invalid records
- Retry queue writer for retryable failures
- Pluggable VLM client (null + Ollama backend)
- 50 tests passing (21 new + 29 existing)
- Existing Phase 1 functionality preserved

### Remaining Work

1. **Parser coverage:** Add parsers for `scheme_master`, `factsheet`, `sid`, `kim`, `ter`
2. **Real PostgreSQL insert:** Connect runner output to `get_session_maker()` and actually upsert records
3. **Raw file management:** Clean up temp files at run end per retention policy
4. **Operational commands:** Implement `retry-failed`, `inspect-run`, `export-run-summary`
5. **Refactor Phase 1A/1B:** Update `mutual_fund_ingestion/http.py` to import from `utils/http.py` (backward compat)
6. **Archive legacy code:** Move `amfi_disclosure/http.py` and `Code Base/` to `unused_codebase/`
7. **CODEBASE_MAP.md:** Update with new `agent/` and `utils/` module ownership
8. **README.md:** Add `run-agent` usage section

---

## Appendix A: File Listing

```
utils/
  __init__.py
  http.py              HttpSettings, build_session
  url_utils.py          canonical_url, file_type_from_url, safe_name, slugify
  text_utils.py         normalize_amc_name

mutual_fund_ingestion/agent/
  __init__.py
  db.py                17 SQLAlchemy models + create_tables() + get_session_maker()
  models.py             AgentResult, ParserResult, runtime dataclasses
  config.py            AgentConfig from CLI args
  discovery.py         DiscoveryEngine with URL queue, scoring, classification
  browser.py           extract_with_browser with Playwright
  extract.py           ArtifactCollector with download and checksum
  validate.py          validate_nav_record, validate_portfolio_record, quarantine, retry
  vlm.py               VLMClient (ABC), NullVLMClient, OllamaVLMClient
  runner.py            IngestionRunner orchestrating the pipeline
  parser/
    __init__.py        ParserRouter dispatching by (dataset_type, file_type)
    nav.py             parse_nav_text, parse_nav_csv
    amc.py             parse_amc_html
    portfolio.py        parse_portfolio_excel with column alias mapping

tests/
  test_agent.py        21 tests for agent module
```

## Appendix B: Dataset Type → Parser Mapping

| dataset_type | file_type | Parser |
|---|---|---|
| `nav_history` | text | `nav_text_v1` |
| `nav_history` | csv | `nav_csv_v1` |
| `nav_reference` | text | `nav_text_v1` |
| `amc_provider_list` | html | `amc_html_v1` |
| `portfolio_disclosure` | xlsx | `portfolio_excel_v1` |
| `portfolio_disclosure` | xls | `portfolio_excel_v1` |
| `portfolio_disclosure` | csv | `portfolio_excel_v1` |
| `scheme_master` | csv | *(not yet implemented)* |
| `factsheet` | pdf | *(not yet implemented)* |
| `sid` | pdf | *(not yet implemented)* |
| `ter` | pdf | *(not yet implemented)* |
| *any other* | *any* | `unknown` (logs warning) |