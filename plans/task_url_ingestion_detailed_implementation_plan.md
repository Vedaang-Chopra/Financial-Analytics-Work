# Task-URL Driven Mutual Fund Ingestion Agent — Detailed Implementation Plan

## 1. Objective

Build an end-to-end task-URL driven mutual fund ingestion agent under `mutual_fund_ingestion/agent/` that:

1. Accepts one or more task URLs from the CLI.
2. Discovers relevant data sources and dataset candidates by crawling those URLs and linked provider pages.
3. Extracts raw artifacts using the correct strategy: static HTTP → network API → Playwright → VLM → manual review.
4. Parses artifacts into structured records (NAV history, portfolio snapshots, scheme metadata, factsheets).
5. Validates parsed rows and loads clean records into canonical PostgreSQL tables.
6. Quarantines failed rows with failure reasons.
7. Produces machine-readable artifacts, human-readable reports, and a companion review notebook.

The plan respects the existing Phase 1A/1B codebase, reuses or refactors shared utilities, and does not duplicate provider-profiling logic.

---

## 2. Scope Boundary

### In Scope

- `mutual_fund_ingestion/agent/` package with layered modules.
- PostgreSQL schema for ingestion runs, pages, links, candidates, artifacts, documents, schemes, AMCs, NAV history, portfolio snapshots, validation results, quarantine rows, and retry queue.
- CLI subcommands: `init-db`, `run-agent`.
- Parser router with NAV (CSV), AMC/scheme (JSON/HTML), and portfolio (XLSX/CSV) parsers.
- Validation and quarantine layer.
- Pluggable local VLM client (Ollama default, null fallback).
- Unit tests under `tests/test_agent.py`.
- Companion notebook under `notebooks/mutual_fund_ingestion/`.
- Module README, `CODEBASE_MAP.md` update, root `README.md` update, and implementation report.

### Out of Scope

- Full live crawl of all 53 AMCs by default.
- Production-grade PDF portfolio parser (stub + routing only).
- RabbitMQ or distributed queue runtime in this phase.
- Continuous scheduling or daemon mode.
- Advanced duplicate-resolution policy for conflicting NAV rows.

---

## 3. Layer Plan

| Layer | File(s) | Responsibility |
|---|---|---|
| Layer 1 — Notebook | `notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb` | Inspect config, parser router, validation, dry-run flow, report paths. No production logic. |
| Layer 2 — Public Interface | `mutual_fund_ingestion/cli.py` | Subcommands `init-db`, `run-agent`. Argument parsing only. |
| Layer 3 — Orchestration | `mutual_fund_ingestion/agent/runner.py` | `IngestionRunner.run()` stage order and queue-like loop. |
| Layer 4 — Core Logic | `mutual_fund_ingestion/agent/discovery.py`, `extract.py`, `browser.py`, `parser/*.py`, `validate.py`, `vlm.py` | Actual fetch, parse, validate, VLM fallback. |
| Layer 5 — Schemas / Utilities | `mutual_fund_ingestion/agent/db.py`, `models.py`, `config.py`; `utils/http.py`, `url_utils.py`, `text_utils.py` | SQLAlchemy models, dataclasses, shared primitives. |

---

## 4. Reuse and Consolidation Map

| Existing Code | Action | New Location |
|---|---|---|
| `mutual_fund_ingestion/http.py` `HttpSettings`, `build_session` | Refactor to shared utility | `utils/http.py` |
| `amfi_disclosure/http.py` duplicate `HttpSettings`, `build_session` | Refactor to shared utility | `utils/http.py` |
| `mutual_fund_ingestion/extract.py` `canonical_url`, `file_type_from_url` | Refactor to shared utility | `utils/url_utils.py` |
| `mutual_fund_ingestion/extract.py` `safe_name` | Refactor to shared utility | `utils/url_utils.py` |
| `mutual_fund_ingestion/source_registry.py` `normalize_amc_name` | Refactor to shared utility | `utils/text_utils.py` |
| `mutual_fund_ingestion/profiler.py`, `reports.py`, `browser.py`, `extract.py` | Update imports to use `utils/` | In place |
| Phase 1A `SourceRegistryEntry`, `AMCSource` | Reuse as seed sources when a task URL points to the registry | `mutual_fund_ingestion/models.py` |
| Phase 1B `ProviderProfile` | Reuse to pre-select extraction strategy for known providers | `mutual_fund_ingestion/artifacts.py` |

---

## 5. Module-By-Module Build Order

### Phase A — Shared Utilities and Database Foundation

1. Create `utils/` package.
   - `utils/http.py`: `HttpSettings`, `build_session()`, retry policy, respectful user-agent.
   - `utils/url_utils.py`: `canonical_url()`, `file_type_from_url()`, `safe_name()`, `slugify()`.
   - `utils/text_utils.py`: `normalize_amc_name()`.
2. Update `mutual_fund_ingestion/profiler.py`, `reports.py`, `browser.py`, `extract.py` to import from `utils/`.
3. Create `mutual_fund_ingestion/agent/db.py` SQLAlchemy declarative base and models:
   - `IngestionRun`, `TaskUrl`, `SourcePage`, `DiscoveredLink`, `SourceEntity`, `DatasetCandidate`, `RawArtifact`, `Document`, `AMC`, `Scheme`, `SchemeAlias`, `NAVHistory`, `PortfolioSnapshot`, `ValidationResult`, `QuarantineRow`, `RetryQueueItem`.
4. Add `create_database_schema()` and `get_session_maker()` helpers.

### Phase B — Agent Configuration and Runtime Models

1. Create `mutual_fund_ingestion/agent/config.py`.
   - `AgentConfig` dataclass from CLI args.
   - `is_allowed_domain()`, `is_relevant_path()`, `should_follow_link()` helpers.
2. Create `mutual_fund_ingestion/agent/models.py`.
   - `PageEvidence`, `DatasetCandidateClass`, `ParsedRecord`, `ParserResult`, `ValidationError` dataclasses.

### Phase C — Discovery, Browser, and Extraction

1. Create `mutual_fund_ingestion/agent/discovery.py`.
   - `DiscoveryEngine.fetch_static(url)`.
   - `extract_links(html, base_url)` and `score_link(href, text)`.
2. Create `mutual_fund_ingestion/agent/browser.py`.
   - `extract_with_browser(url, config)` using Playwright with fallback to `BrowserUnavailable`.
   - `capture_screenshot`, `har_file` debug artifacts.
3. Create `mutual_fund_ingestion/agent/extract.py`.
   - `ArtifactCollector`: classify candidate, download to temp directory, compute checksum, build `RawArtifact` metadata.

### Phase D — Parser Router and Parsers

1. Create `mutual_fund_ingestion/agent/parser/__init__.py`.
   - `PARSER_ROUTER` mapping `(dataset_type, file_type)` → parser function.
   - `parse_file(raw_artifact, metadata)` dispatcher.
2. Create `mutual_fund_ingestion/agent/parser/nav.py`.
   - CSV NAV parser for AMFI-style NAV files.
3. Create `mutual_fund_ingestion/agent/parser/amc.py`.
   - JSON/HTML AMC and scheme metadata parser.
4. Create `mutual_fund_ingestion/agent/parser/portfolio.py`.
   - XLSX/CSV portfolio snapshot parser (lightweight, columns: scheme_code, isin, instrument, sector, quantity, market_value, nav_percentage).
5. Add PDF portfolio parser route returning empty result with `vlm_required` reason.

### Phase E — Validation, Quarantine, and VLM

1. Create `mutual_fund_ingestion/agent/validate.py`.
   - `validate_and_filter_records(records, table_name)`.
   - Required-field checks per table; split into clean rows and quarantine rows.
2. Create `mutual_fund_ingestion/agent/vlm.py`.
   - `BaseVLMClient` protocol.
   - `NullVLMClient` for `--use-vlm false`.
   - `OllamaVLMClient` for local Ollama endpoint.

### Phase F — Runner and CLI Wiring

1. Create `mutual_fund_ingestion/agent/runner.py`.
   - `IngestionRunner.run(task_urls)` orchestration:
     1. Create `IngestionRun` row.
     2. Insert task URLs.
     3. Loop while URL queue not empty and budget not exceeded.
     4. Fetch page, extract links, enqueue relevant links.
     5. Classify dataset candidates, download artifacts.
     6. Route artifacts to parser → validate → canonical upsert.
     7. Save debug artifacts and metrics.
2. Update `mutual_fund_ingestion/cli.py`.
   - Add `init-db` subcommand.
   - Add `run-agent` subcommand with all budget/flag args.
   - Lazily import SQLAlchemy to avoid breaking CLI when DB deps are absent.

### Phase G — Tests and Notebook

1. Create `tests/test_agent.py`.
   - Tests for config, URL scoring, parser router, NAV parser, validation, quarantine, CLI, runner dry-run.
2. Create `notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb`.
   - Import config, parser router, validation.
   - Run dry-run cells and display metrics as DataFrames.
   - Point to design spec and implementation report.

### Phase H — Documentation

1. Create `mutual_fund_ingestion/agent/README.md`.
2. Update `docs/ai_context/CODEBASE_MAP.md`.
3. Update root `README.md` with `run-agent` usage.
4. Create `docs/design/task_url_agent_design_pack/implementation_report.md`.
5. Create `docs/README_DOCS_INDEX.md` indexing all docs.
6. Create this detailed implementation plan at `plans/task_url_ingestion_detailed_implementation_plan.md`.

---

## 6. CLI Specification

```bash
# Initialize database schema
python -m mutual_fund_ingestion init-db \
  --database-url "$DATABASE_URL"

# Run the agent
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/"
  --task-url "https://www.amfiindia.com/aboutamfi?tab=members" \
  --database-url "$DATABASE_URL" \
  --use-browser true \
  --use-vlm false \
  --vlm-endpoint "http://localhost:11434" \
  --max-pages 500 \
  --max-depth 5 \
  --max-files 200 \
  --keep-raw-files false \
  --dry-run false
```

Arguments:

| Argument | Default | Description |
|---|---|---|
| `--task-url` | required (or `--task-url-file`) | Seed task URL; repeatable. |
| `--task-url-file` | `None` | Text file with one URL per line. |
| `--database-url` | `$DATABASE_URL` | PostgreSQL connection string. |
| `--use-browser` | `true` | Whether to use Playwright when static extraction fails. |
| `--use-vlm` | `false` | Whether to call a local VLM for ambiguous pages. |
| `--vlm-endpoint` | `http://localhost:11434` | Ollama-compatible VLM endpoint. |
| `--max-pages` | `500` | Max pages to fetch. |
| `--max-depth` | `5` | Max crawl depth from any task URL. |
| `--max-files` | `200` | Max raw files to download. |
| `--keep-raw-files` | `false` | Persist raw files after parsing. |
| `--dry-run` | `false` | Discover and parse but do not write to PostgreSQL. |

---

## 7. Acceptance Criteria

- [ ] `python -m mutual_fund_ingestion init-db --database-url ...` creates all tables without error.
- [ ] `python -m mutual_fund_ingestion run-agent --task-url ... --dry-run true` completes and prints metrics.
- [ ] `pytest tests/test_agent.py` passes.
- [ ] Existing `pytest tests/test_mutual_fund_ingestion.py` still passes.
- [ ] Notebook imports production code and runs dry-run cells.
- [ ] All new public functions have type hints and docstrings.
- [ ] No production logic in notebook cells.
- [ ] No hardcoded credentials or paths.
- [ ] `CODEBASE_MAP.md` and `README.md` updated.

---

## 8. Risk Register

| Risk | Mitigation |
|---|---|
| SQLAlchemy not installed in all environments | Lazily import DB modules; CLI `init-db`/`run-agent` fail gracefully with instructions. |
| Playwright not installed | Browser strategy raises `BrowserUnavailable` and falls back gracefully. |
| Live AMFI timeouts during smoke test | Tests use fixtures; smoke test uses small timeout and is optional. |
| Duplicate utilities cause import loops | Centralize in `utils/`; avoid cross-imports between agent and Phase 1 modules. |
| Legacy `Code Base/` imports break | Do not import from legacy code; archive after explicit review. |

---

## 9. Follow-Up Work

1. Refactor existing Phase 1 modules to fully depend on `utils/` (Phase R in original plan).
2. Archive legacy `Code Base/Dataset_Collection_Module/` to `unused_codebase/`.
3. Deprecate duplicate `amfi_disclosure/http.py` in favor of `utils/http.py`.
4. Add production PDF portfolio parser and factsheet parser.
5. Add RabbitMQ-backed async runtime when scale requires it.
6. Build reconciliation logic for conflicting NAV rows.
7. Add screenshot-based VLM navigator that returns structured action plans.
