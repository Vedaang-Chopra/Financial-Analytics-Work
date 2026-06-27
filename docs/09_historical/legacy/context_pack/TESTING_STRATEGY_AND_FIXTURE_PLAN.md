# Testing Strategy and Fixture Plan

---

## 1. Unit Test Strategy

**Location:** `tests/test_agent.py`, `tests/test_mutual_fund_ingestion.py`

**Principle:** Each function is tested in isolation with inline fixture data or minimal fixture files.

**Rules:**
- No real network calls in unit tests
- No real database in unit tests (use in-memory constructs or return-value inspection)
- No Playwright in unit tests (mock or skip)
- All parsers must be testable with a bytes/str input and a dict output
- All validators must be testable with a dict input and a list of errors output
- Test both the happy path and at least one error path per function

**Coverage targets:**
- Every `parse_*` function: at least one valid fixture test + one malformed input test
- Every `validate_*` function: one passing record + one failing record per required field
- Every `route_parser` combination in `PARSER_ROUTER`: one routing test
- `DiscoveryEngine.extract_links`: valid HTML + HTML with no links
- `DiscoveryEngine.score_relevance`: high-relevance + low-relevance + irrelevant

---

## 2. Integration Test Strategy

**Location:** `tests/test_agent_db.py`

**Principle:** Tests run the full pipeline against an in-process SQLite database. No mocking of DB calls.

**Rules:**
- Use `tempfile.mkstemp(suffix=".db")` and clean up in teardown
- Use SQLite URL: `sqlite:///path/to/tempfile.db`
- Create tables with `Base.metadata.create_all(engine)` before each test class
- Verify rows exist with `session.execute(select(...)).scalars().all()`
- Test one pipeline segment per test (e.g., download → raw_artifact, or parse → staging_row)

**Coverage targets:**
- `test_init_db_creates_all_tables`: all 17 tables present after init
- `test_run_agent_creates_ingestion_run`: IngestionRun row written
- `test_run_agent_creates_source_pages`: SourcePage rows written during crawl
- `test_run_agent_creates_discovered_links`: DiscoveredLink rows written
- `test_run_agent_creates_task_urls`: TaskURL rows written
- `test_run_agent_creates_retry_queue_on_fetch_failure`: RetryQueue row written on 0-status fetch
- `test_nav_parser_upserts_to_nav_history`: NAV parse → nav_history row
- `test_amc_parser_upserts_to_amcs`: AMC parse → amcs row
- `test_scheme_master_parser_upserts_to_schemes`: scheme_master parse → schemes row
- `test_portfolio_parser_creates_holdings`: portfolio parse → snapshot + holdings rows
- `test_validation_creates_validation_results`: ValidationResult rows written
- `test_quarantine_for_invalid_records`: QuarantineRow written for invalid record
- `test_staging_rows_created`: StagingRow written for every parse result

---

## 3. Fixture Website Strategy

A local in-process HTTP server (using `http.server.HTTPServer` or `pytest-httpserver`) serves static fixture HTML and data files during end-to-end tests.

The fixture website simulates the following link graph:

```
GET /amfi-seed                → amfi_seed_page.html
  → links to /amc-list        → amc_provider_list.html
      → links to /amc/example → amc_disclosure_page.html
          → links to /files/nav.txt         (nav_history, text)
          → links to /files/scheme.csv      (scheme_master, csv)
          → links to /files/portfolio.xlsx  (portfolio_disclosure, xlsx)
          → links to /files/factsheet.html  (factsheet, html)
          → links to /files/ter.csv         (ter, csv)
```

Fixture files are in `tests/fixtures/` (HTML pages) and `tests/fixtures/data/` (data files).

End-to-end tests use `IngestionRunner` with `database_url=sqlite:///tmp/e2e_test.db` and `task_url=http://localhost:<port>/amfi-seed`.

---

## 4. PostgreSQL vs SQLite Test Strategy

| Test type | DB | Rationale |
|---|---|---|
| Unit tests | No DB | Isolated function testing |
| Integration tests | SQLite (in-memory or temp file) | Fast, no server required |
| End-to-end fixture tests | SQLite temp file | Reproducible, CI-safe |
| Smoke tests (live AMFI) | SQLite temp file | No prod DB risk |
| Production | PostgreSQL | Required for UUID, JSONB, constraints |

**SQLite compatibility notes:**
- UUID columns use `UUID(as_uuid=True)` — SQLite stores as TEXT, works for testing
- `func.now()` works in both
- `ON CONFLICT DO UPDATE` (upsert) syntax: use `sqlalchemy.dialects.postgresql.insert` for PG; fall back to `session.merge()` in tests
- All 17 tables are SQLite-compatible for testing

---

## 5. Browser/Playwright Test Strategy

**Principle:** Do not run Playwright in CI unless explicitly marked.

**Approach:**
- `extract_with_browser()` is tested by patching `playwright.sync_api.sync_playwright` with a fake context
- The fake context returns controlled HTML, links, and network_calls
- Real Playwright tests are marked `@pytest.mark.browser` and skipped by default
- To run: `python -m pytest -m browser tests/`

**What to test with fake Playwright:**
- BrowserResult returned with correct html, links, downloads
- BrowserUnavailable exception raised when import fails
- Screenshot path set correctly in BrowserResult
- Network downloads extracted from network_calls

---

## 6. Fake VLM Test Strategy

**Principle:** VLM tests use `NullVLMClient` or a `MockVLMClient` that returns a controlled `PageAnalysisDecision`.

```python
class MockVLMClient(VLMClient):
    def __init__(self, decision):
        self._decision = decision
    def analyze_page(self, payload):
        return self._decision
```

**What to test:**
- VLM is called when `use_vlm=True` and page score < threshold
- VLM is NOT called when `use_vlm=False`
- VLM returning `is_relevant=False` does NOT add a DatasetCandidate
- VLM returning `is_relevant=True` with `dataset_type="nav_history"` DOES add a DatasetCandidate
- `NullVLMClient.analyze_page()` always returns None
- `OllamaVLMClient._build_prompt()` returns a non-empty string
- `OllamaVLMClient._parse_response()` handles valid JSON correctly
- `OllamaVLMClient._parse_response()` returns None on malformed JSON

---

## 7. Parser Fixture Strategy

Each parser has a corresponding fixture file in `tests/fixtures/data/`.

| Parser | Fixture file | Format |
|---|---|---|
| nav_text | `tests/fixtures/data/nav_all_schemes.txt` | Pipe-delimited, AMFI format |
| nav_csv | `tests/fixtures/data/nav_data.csv` | CSV with header row |
| nav_html | `tests/fixtures/data/nav_page.html` | HTML table |
| amc_html | `tests/fixtures/data/amfi_member_list.html` | Links with AMC names |
| scheme_master_csv | `tests/fixtures/data/scheme_master.csv` | AMFI scheme master CSV |
| scheme_master_html | `tests/fixtures/data/scheme_master.html` | HTML table of schemes |
| portfolio_excel | `tests/fixtures/data/portfolio_sample.xlsx` | Excel with real AMFI columns |
| portfolio_csv | `tests/fixtures/data/portfolio_sample.csv` | CSV version |
| metadata_html | `tests/fixtures/data/factsheet_metadata.html` | Factsheet HTML page |
| ter_csv | `tests/fixtures/data/ter_data.csv` | TER disclosure CSV |
| aum_csv | `tests/fixtures/data/aum_data.csv` | AUM/AAUM CSV |

**Fixture file requirements:**
- Use realistic but synthetic data (real format, fake values)
- Include at least 3 valid rows + 1 invalid row per file
- Invalid rows should trigger known quarantine reasons (missing field, bad value)

---

## 8. End-to-End Fixture Run Strategy

**Test class:** `tests/test_e2e_fixture.py` (to be created in Epic R)

**Setup:**
1. Start local HTTP server serving `tests/fixtures/` directory
2. Create temp SQLite DB
3. Run `IngestionRunner` with `task_url=http://localhost:<port>/amfi-seed`
4. Verify rows in all target tables

**Assertions after fixture run:**

| Table | Expected rows | Key assertion |
|---|---|---|
| `ingestion_runs` | 1 | status = "complete" |
| `task_urls` | 1 | url matches seed URL |
| `source_pages` | ≥ 4 | covers seed + AMC pages |
| `discovered_links` | ≥ 10 | includes data file links |
| `dataset_candidates` | ≥ 5 | NAV, portfolio, scheme_master all found |
| `raw_artifacts` | ≥ 3 | nav, portfolio, scheme files downloaded |
| `staging_rows` | ≥ 10 | rows from all parsers |
| `validation_results` | ≥ 3 | at least one pass per parser |
| `quarantine_rows` | ≥ 1 | at least one invalid row quarantined |
| `amcs` | ≥ 1 | example AMC upserted |
| `schemes` | ≥ 1 | example scheme upserted |
| `nav_history` | ≥ 3 | NAV rows from fixture |
| `portfolio_snapshots` | ≥ 1 | one snapshot created |
| `portfolio_holdings` | ≥ 3 | holdings from portfolio fixture |
| `documents` | ≥ 1 | factsheet document record |

**Test is marked `@pytest.mark.e2e`** and excluded from default `pytest` run.
Run with: `python -m pytest -m e2e tests/`

---

## 9. Bounded Live AMFI Smoke Test Strategy

**Purpose:** Verify the system can actually reach AMFI and return usable data from the real URL.

**Test file:** `tests/test_smoke.py` (to be created in Epic S)

**Markers:** `@pytest.mark.smoke` — excluded from default run.
Run with: `python -m pytest -m smoke tests/ --log-cli-level=INFO`

**Smoke tests:**

| Test | URL | Limits | Assertion |
|---|---|---|---|
| `test_smoke_amfi_seed_page_reachable` | amfiindia.com | max_pages=1, max_files=0 | source_pages has ≥ 1 row |
| `test_smoke_amfi_discovers_nav_link` | amfiindia.com/nav-history | max_pages=3, max_files=0 | discovered_links includes nav_history type hint |
| `test_smoke_amfi_nav_download_and_parse` | amfiindia.com/nav-history | max_pages=3, max_files=1 | nav_history has ≥ 1 row |

**Rules for smoke tests:**
- Use SQLite temp DB (never real PostgreSQL in smoke)
- Set `max_pages=3` and `max_files=1` to limit impact
- Skip gracefully if network unavailable: `pytest.importorskip` or `requests.get` pre-check
- Never run smoke tests in CI automatically

---

## 10. Fixture Files to Create (Cumulative Roadmap)

Files that do not yet exist and must be created as part of Epic N–R tasks:

```
tests/fixtures/data/
├── nav_all_schemes.txt       # TASK-N001
├── nav_data.csv              # TASK-N003
├── nav_page.html             # TASK-N006
├── scheme_master.csv         # TASK-O004
├── scheme_master.html        # TASK-O006
├── portfolio_sample.xlsx     # TASK-P002
├── portfolio_sample.csv      # TASK-P006
├── factsheet_metadata.html   # TASK-Q004
├── ter_data.csv              # TASK-Q007 (future)
└── aum_data.csv              # TASK-Q007 (future)

tests/fixtures/
├── amfi_seed_page.html       # TASK-R001
├── amc_provider_list.html    # TASK-R002
└── amc_disclosure_page.html  # TASK-R003
```

Existing fixtures (do not modify):
```
fixtures/
├── amfi_portfolio.html
└── amc_portfolio.html

tests/fixtures/
├── amfi_members.html
├── amfi_member_detail.html
└── provider_static.html
```

---

## 11. Test Execution Commands

```bash
# All tests (default, no smoke/e2e/browser)
python -m pytest tests/ test_amfi_disclosure.py -v

# Unit tests only
python -m pytest tests/test_agent.py tests/test_mutual_fund_ingestion.py -v

# DB integration tests only
python -m pytest tests/test_agent_db.py -v

# End-to-end fixture tests
python -m pytest -m e2e tests/ -v

# Browser tests (requires Playwright installed)
python -m pytest -m browser tests/ -v

# Smoke tests (live network, use sparingly)
python -m pytest -m smoke tests/ --log-cli-level=INFO -v

# All non-live tests
python -m pytest tests/ test_amfi_disclosure.py -m "not smoke and not e2e and not browser" -v
```
