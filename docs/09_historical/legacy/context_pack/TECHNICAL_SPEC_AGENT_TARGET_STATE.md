# Technical Spec: Agent Target State

_Concise reference for what the system must do when complete._

---

## 1. User-Facing Contract

**Input:** One or more task URLs (e.g., `https://www.amfiindia.com/nav-history`).

**Output:** Rows in a PostgreSQL database covering:
- AMC/provider list
- Scheme metadata
- NAV history
- Portfolio holdings
- Document metadata (factsheets, SID, KIM, TER, AUM)

**The user does not manually provide AMC URLs, extraction strategies, or parser configurations.** The agent discovers all of this from the seed URL.

---

## 2. Runtime Architecture

```
CLI (python -m mutual_fund_ingestion run-agent)
  └─ IngestionRunner (mutual_fund_ingestion/agent/runner.py)
       ├─ DiscoveryEngine     — BFS crawl, relevance scoring
       ├─ BrowserAgent        — Playwright fallback
       ├─ NetworkCapture      — embedded API endpoint detection
       ├─ VLMClient           — last-resort page classification
       ├─ ArtifactCollector   — download, checksum, retain
       ├─ ParserRouter        — dispatch to dataset-specific parser
       ├─ Validator           — per-dataset validation rules
       ├─ StagingWriter       — staging_rows + validation_results
       ├─ QuarantineWriter    — quarantine_rows + retry_queue
       └─ CanonicalUpserter   — amcs, schemes, nav_history, portfolio_*, documents
```

All state is persisted in PostgreSQL via SQLAlchemy ORM (17 tables in `mutual_fund_ingestion/agent/db.py`).

---

## 3. Main CLI Commands

```bash
# Initialize database schema
python -m mutual_fund_ingestion init-db --database-url <url>

# Run the ingestion agent
python -m mutual_fund_ingestion run-agent \
  --task-url <url> \
  --database-url <url> \
  [--use-browser] [--headless] \
  [--use-vlm] [--vlm-endpoint <url>] [--vlm-model <name>] \
  [--keep-raw-files] [--raw-dir <path>] \
  [--max-pages N] [--max-depth N] [--max-files N] \
  [--log-level INFO|DEBUG] [--dry-run] [--fail-fast]

# Inspect a run
python -m mutual_fund_ingestion inspect-run \
  --database-url <url> --run-id <uuid>

# Retry failed tasks
python -m mutual_fund_ingestion retry-failed \
  --database-url <url> --run-id <uuid>
```

Phase 1A/1B commands (`bootstrap-sources`, `profile-providers`, `phase-1`) remain available for provider profiling.

---

## 4. Data Flow

```
task_urls (seed)
  → DiscoveryEngine.fetch(url) → HTTP GET
  → INSERT source_pages
  → extract_links(html) → list of {url, text, title}
  → score_relevance() → (score, dataset_type_hint)
  → INSERT discovered_links (all links, with scores)
  → classify_dataset() → dataset_type
  → INSERT dataset_candidates (high-confidence links only)
  → [if requires_browser] extract_with_browser() → BrowserResult
  → [if use_vlm and low confidence] vlm.analyze_page() → PageAnalysisDecision
  → ArtifactCollector.download(url) → {checksum, size, path, ...}
  → INSERT raw_artifacts
  → parse_file(dataset_type, file_type, content) → ParserResult
  → INSERT staging_rows (every record)
  → validate_and_filter_records() → (valid, invalid)
  → INSERT validation_results
  → INSERT quarantine_rows (invalid records)
  → INSERT retry_queue (retryable failures)
  → _upsert_canonical() → INSERT/UPDATE amcs, schemes, nav_history, portfolio_*, documents
  → UPDATE ingestion_runs (status, counts)
```

---

## 5. Database Tables

### Operational tables (created and written by every run)
| Table | Purpose |
|---|---|
| `ingestion_runs` | One row per agent run; tracks status and counters |
| `task_urls` | Seed URLs for the run |
| `source_pages` | Every page fetched (HTML or non-HTML) |
| `discovered_links` | Every link extracted from every page |
| `dataset_candidates` | High-relevance links identified for download |
| `raw_artifacts` | Every file downloaded; checksum + local path |
| `staging_rows` | Every parsed record before validation |
| `validation_results` | Per-record validation check results |
| `quarantine_rows` | Records that failed validation |
| `retry_queue` | Failed downloads/parses that can be retried |

### Canonical data tables (upserted; survive across runs)
| Table | Purpose |
|---|---|
| `amcs` | Deduplicated AMC/provider list |
| `schemes` | Scheme codes linked to AMC |
| `nav_history` | NAV time series per scheme |
| `portfolio_snapshots` | One row per scheme per reporting date |
| `portfolio_holdings` | Individual security holdings |
| `instruments` | Security master (ISIN, sector, issuer) |
| `documents` | Factsheet, SID, KIM, TER, AUM metadata |

---

## 6. Provenance Requirements

Every canonical row must carry:
- `source_url`: the URL the data was fetched from
- `raw_artifact_id`: foreign key to `raw_artifacts`

Every staging and quarantine row must carry:
- `run_id`: the ingestion run
- `raw_artifact_id`: the downloaded file

These requirements are non-negotiable per `AGENTS.md`.

---

## 7. Static Scraping Responsibilities

`DiscoveryEngine` (in `mutual_fund_ingestion/agent/discovery.py`) is responsible for:
- HTTP GET with retry/backoff (via `utils/http.py`)
- HTML link extraction via `LinkExtractor` (regex-based anchor parser)
- Relevance scoring using `RELEVANCE_KEYWORDS` (high/low keyword sets)
- Dataset type hint assignment using `DATASET_TYPE_HINTS`
- BFS queue management (deque, depth tracking, visited set)
- Domain filtering (stay on task domain unless cross-domain links are whitelisted)

Static scraping is **always tried first** before Playwright or VLM.

---

## 8. Playwright Responsibilities

`extract_with_browser` (in `mutual_fund_ingestion/agent/browser.py`) is responsible for:
- Launching headless Chromium via `playwright.sync_api`
- Waiting for `domcontentloaded` + 1500ms settle time
- Extracting all anchor links from the rendered DOM
- Capturing network response URLs (for embedded file downloads)
- Taking a full-page screenshot for debug artifacts
- Returning `BrowserResult` with: html, links, downloads, network_calls, screenshot_path

Playwright is only invoked when:
1. `use_browser=True` in `AgentConfig`
2. The static fetch returned no useful links (empty or JS-rendered)

---

## 9. Network/API Capture Responsibilities

During Playwright execution, `network_calls` captures all HTTP responses. The runner inspects these for file-extension patterns (`.txt`, `.csv`, `.xlsx`, `.pdf`) and promotes matching URLs to `DatasetCandidate` records with `download_method="api"`.

Direct AMFI API endpoints (e.g., `https://api.amfiindia.com/NavALL`) must be detected as `nav_history` dataset candidates regardless of whether they appear as anchor links.

---

## 10. VLM Responsibilities

`VLMClient.analyze_page(payload)` is called when:
1. `use_vlm=True` in `AgentConfig`
2. A fetched page has relevance score below `vlm_confidence_threshold` (default 0.7)
3. The page is not already classified as a high-confidence dataset candidate

`PageAnalysisDecision` returned by VLM contains: `is_relevant`, `dataset_type`, `confidence`, `reasoning`.

The default backend is `NullVLMClient` (returns None, effectively disabling VLM).
The Ollama backend is `OllamaVLMClient` (calls local LLM at `vlm_endpoint`).

VLM is **never called** unless explicitly enabled.

---

## 11. Parser Router Responsibilities

`route_parser(dataset_type, file_type)` in `mutual_fund_ingestion/agent/parser/__init__.py` maps:

| dataset_type | file_type | parser |
|---|---|---|
| nav_history | text | nav_text |
| nav_history | csv | nav_csv |
| nav_history | html | nav_html |
| amc_provider_list | html | amc_html |
| portfolio_disclosure | xlsx | portfolio_excel |
| portfolio_disclosure | xls | portfolio_excel |
| portfolio_disclosure | csv | portfolio_csv |
| scheme_master | csv | scheme_master_csv |
| scheme_master | html | scheme_master_html |
| factsheet | html | metadata_html |
| factsheet | pdf | metadata_pdf |
| sid | pdf | metadata_pdf |
| kim | pdf | metadata_pdf |
| ter | csv | ter_csv |
| aum_aaum | csv | aum_csv |

Unknown combinations return `"unknown"` and produce a quarantine row.

---

## 12. Validation and Quarantine Responsibilities

`validate_and_filter_records(parser_result, run_id)` runs per-dataset validation rules:

| dataset_type | Required fields | Value rules |
|---|---|---|
| nav_history | scheme_code, nav_date, nav_value | nav_value > 0; nav_date parseable |
| portfolio_disclosure | security_name | percentage_to_nav in [0, 100] if present |
| scheme_master | scheme_code, scheme_name | — |
| amc_provider_list | name | — |

Invalid records → `quarantine_rows` with `reason` and `retryable` flag.
Valid records → `staging_rows` → canonical upsert.

---

## 13. Retry Queue Responsibilities

`retry_queue` holds:
- URL that failed
- `task_type`: download | parse | validate | network
- `failure_reason`: human-readable string
- `retry_count`: number of attempts
- `status`: pending | in_progress | complete | failed
- `retryable`: bool

The `retry-failed` CLI command resets `status=pending` on all retry_queue rows for a run so the next `run-agent` invocation will re-attempt them.

---

## 14. Logging Requirements

Every CLI run must emit structured log lines with timestamps, level, and logger name.

Format: `%(asctime)s %(levelname)-8s %(name)s: %(message)s`

Required log events:
- Run start: run_id, task_urls, config summary
- Page fetch: URL, status_code
- Links found: count per page
- Dataset candidates found: count + types per page
- Browser fallback: URL, reason
- VLM invoked: URL, result
- File downloaded: URL, bytes, checksum prefix
- Parser selected: parser_name, dataset_type
- Records parsed: count
- Records valid/quarantined: counts
- Canonical rows upserted: table name, count
- Run complete: all counters
- Run failed: exception + URL

---

## 15. Raw File Retention Policy

| Condition | Action |
|---|---|
| `keep_raw_files=False`, download succeeds, parse succeeds | Delete temp file after parse |
| `keep_raw_files=True`, any outcome | Move to `raw_dir/<run_id>/<safe_filename>` |
| `keep_failed_raw_files=True`, parse fails | Move to `raw_dir/<run_id>/failed/<safe_filename>` |
| File size exceeds `max_file_size_mb` | Skip download; write quarantine row |

`raw_artifacts.local_path` is set to the permanent path when retained, or `None` when deleted.

---

## 16. Out of Scope (for now)

- Real-time streaming or event-driven ingestion
- Multi-worker parallel crawling (single-threaded BFS only)
- Cloud storage for raw files (local filesystem only)
- Schema migrations (init-db is create-or-replace; no Alembic)
- User authentication or session-based access (public URLs only)
- Phase 1.5 strategy resolution for manual-review providers
- Analytics queries over canonical data (Phase 9)
- Dashboard or reporting UI
- SEBI EDGAR filing ingestion (out of scope for now)
