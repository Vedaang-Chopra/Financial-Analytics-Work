# Task-URL Driven Mutual Fund Ingestion Agent — Implementation Plan

## Context

The project has a mature Phase 1A/1B codebase under `mutual_fund_ingestion/` (provider profiling, source registry, discovery, browser), a standalone AMFI crawler under `amfi_disclosure/`, legacy database code in `Code Base/Dataset_Collection_Module/`, and a curated source registry in `configs/amc_sources.yaml`. No end-to-end ingestion pipeline exists yet.

The goal is to build a runnable CLI `run-agent` that accepts task URLs, discovers data sources, extracts raw data, parses it, validates it, and inserts real records into PostgreSQL. This requires: (1) building new `mutual_fund_ingestion/agent/` module, (2) refactoring duplicate/shared code across modules into `utils/`, and (3) archiving legacy code that conflicts.

## Pre-Implementation Audit Summary

### Design Specs Read
All 14 files under `docs/design/task_url_agent_design_pack/all_specs/` and `docs/design/task_url_ingestion_agent/` were read — they are identical. Key specs:
- `00_codex_entrypoint.md` — 12-step pipeline, CLI shape, success criteria
- `01_product_goal_and_scope.md` — source framing, 6 dataset domains, success criteria
- `02_end_to_end_architecture.md` — 9-component pipeline
- `03_agent_runtime_and_orchestration.md` — queue-driven runtime, relevance scoring, domain policy
- `04_discovery_and_browser_agent.md` — static + Playwright discovery, safe interaction rules, network capture
- `05_vlm_integration.md` — VLMClient interface, Ollama-compatible, null backend default
- `06_data_sources_and_dataset_types.md` — 15 dataset types, detection keywords, priority list
- `07_postgresql_schema.md` — 17 tables (discovery + canonical + failure), indexes
- `08_extraction_and_parser_design.md` — parser router, 6 parsers, staging-first, result contract
- `09_validation_quarantine_and_provenance.md` — NAV/portfolio/document validation, quarantine reasons, retry queue
- `10_storage_raw_file_policy.md` — temp dir, checksum, delete-after-parse, deduplication
- `11_cli_config_and_operations.md` — CLI flags, YAML config, operational commands
- `12_reuse_existing_phase_1a_1b.md` — reuse rule, provider profile adaptation, notebook policy
- `13_testing_acceptance_criteria.md` — unit/browser/VLM/DB tests, smoke test, 11 acceptance criteria
- `14_codex_build_plan.md` — 10-step build sequence, build vertically first

### Existing Codebase Audit

**`mutual_fund_ingestion/` (Phase 1A/1B) — REUSE:**
- `http.py` — `HttpSettings`, `build_session` — reused by agent directly
- `extract.py` — `file_type_from_url`, `document_type_hint`, `safe_name`, `canonical_url`, `EvidenceParser`, `extract_page_evidence` — reused by agent
- `browser.py` — `render_reference_html`, `inspect_with_browser`, `BrowserUnavailable`, `BrowserEvidence`, network augmentation — adapted for agent
- `models.py` — dataclass patterns (frozen, `__post_init__`, `to_dict`, `from_dict`) — pattern-reused in agent
- `source_discovery.py` — `discover_amfi_candidates`, `discover_sebi_candidates` — relevant for reference discovery
- `registry.py` — `load_registry`, `load_sources` — useful for loading existing source registry

**`amfi_disclosure/` — INSPECT ONLY, DO NOT IMPORT:**
- `discovery.py` — `extract_page_links`, `Discoverer`, date extraction (`extract_month_or_date`), AMC name inference (`infer_amc_name`), `deduplicate_links`, `select_latest_per_amc`, `LinkParser` — patterns to adapt, not import
- `downloader.py` — `Downloader`, `DownloadResult`, `build_download_name`, `slugify` — patterns to adapt for `agent/extract.py`
- `browser.py` — `discover_with_browser` — pattern to adapt for `agent/browser.py`
- `http.py` — nearly identical to `mutual_fund_ingestion/http.py` — consolidate into shared utility
- `models.py` — `DisclosureLink` — different model than agent needs

**`Code Base/Dataset_Collection_Module/` — ARCHIVE (deprecated):**
- `database_module/schema_definition/define_schema.py` — old single-table schema (`mutual_fund_nav_value`) — REPLACE with new normalized schema
- `database_module/daily_nav_price_data/daily_nav_data.py` — RabbitMQ consumer + DB writer — pattern for real-time ingestion (deprecate after new system works)
- Legacy notebooks — fixture sources only, not for import

**`configs/amc_sources.yaml` — READ ONLY:**
- 53+ AMC entries with seed URLs, expected document types, confidence, discovered_from
- Existing Phase 1A source registry — agent can load and extend this

**`notebooks/` — REFERENCE:**
- Review notebooks for Phase 1A/1B output format — agent should produce compatible artifacts

### Refactoring: Duplicate Code to Consolidate

Three sets of duplicate code must be consolidated into `utils/` before agent work:

| Duplicate | Locations | Action |
|---|---|---|
| `HttpSettings` + `build_session` | `mutual_fund_ingestion/http.py`, `amfi_disclosure/http.py` | Move to `utils/http.py`; update imports in both modules |
| `canonical_url` + `file_type_from_url` | `mutual_fund_ingestion/extract.py`, `amfi_disclosure/discovery.py`, `mutual_fund_ingestion/browser.py` | Move to `utils/url_utils.py`; update imports |
| `safe_name` | `mutual_fund_ingestion/extract.py`, `amfi_disclosure/downloader.py` | Move to `utils/text_utils.py`; update imports |

This consolidation follows AGENTS.md §7 (no duplicated schemas/utils) and makes the agent code clean.

## Approach

### Refactoring First
Extract shared utilities into `utils/` module, update existing imports, archive legacy code.

### New Module
Build the end-to-end pipeline in `mutual_fund_ingestion/agent/`.

**Layer 2 (Public Interface):** add `run-agent` and operational commands to `cli.py`
**Layer 3 (Orchestration):** `agent/runner.py` — ingestion run manager
**Layer 4 (Core Logic):**
- `agent/discovery.py` — URL queue, static fetch, link extraction, relevance scoring, domain policy
- `agent/browser.py` — Playwright wrapper for rendered pages and network capture
- `agent/extract.py` — artifact collector, downloader, checksum, temp file policy
- `agent/parser/` — parser router + NAV/AMC list/Excel portfolio parsers
- `agent/validate.py` — validation rules, quarantine writer, retry queue writer
- `agent/vlm.py` — optional VLM client (pluggable, null by default)
**Layer 5 (Schemas / Utilities):** `agent/db.py`, `agent/models.py`, `agent/config.py`

## Files to Modify

- `requirements.txt` — add `psycopg2-binary`
- `mutual_fund_ingestion/http.py` → `utils/http.py` (consolidate duplicate)
- `mutual_fund_ingestion/extract.py` — update imports to use `utils/`
- `mutual_fund_ingestion/browser.py` — update imports to use `utils/`
- `amfi_disclosure/http.py` → `unused_codebase/` (after consolidation)
- `amfi_disclosure/downloader.py` — update imports to use `utils/`
- `mutual_fund_ingestion/__init__.py` — re-export new public API
- `mutual_fund_ingestion/cli.py` — add `run-agent` and operational subcommands
- `docs/ai_context/CODEBASE_MAP.md` — add new module ownership, archive old entries
- `README.md` — update with `run-agent` usage

## Files to Create

### New utilities (shared across all modules)
- `utils/__init__.py`
- `utils/http.py` — `HttpSettings`, `build_session` (consolidated from both modules)
- `utils/url_utils.py` — `canonical_url`, `file_type_from_url`, `safe_name` (consolidated)
- `utils/text_utils.py` — additional text helpers

### Agent module
- `mutual_fund_ingestion/agent/__init__.py`
- `mutual_fund_ingestion/agent/db.py` — SQLAlchemy models for all 17 tables + `create_tables()`
- `mutual_fund_ingestion/agent/models.py` — ingestion runtime dataclasses (`ParserResult`, `RunResult`, etc.)
- `mutual_fund_ingestion/agent/config.py` — `AgentConfig` from CLI args / YAML config
- `mutual_fund_ingestion/agent/discovery.py` — URL queue, HTTP fetch, link extraction, relevance scoring, domain policy, dataset candidate detection
- `mutual_fund_ingestion/agent/browser.py` — Playwright extraction strategy, network capture, download detection
- `mutual_fund_ingestion/agent/extract.py` — file download, checksum, temp file management, deduplication
- `mutual_fund_ingestion/agent/parser/__init__.py` — parser router by (dataset_type, file_type)
- `mutual_fund_ingestion/agent/parser/nav.py` — AMFI NAV text/CSV parser → `nav_history` rows
- `mutual_fund_ingestion/agent/parser/amc.py` — AMC list HTML parser → `amcs` rows
- `mutual_fund_ingestion/agent/parser/portfolio.py` — Excel portfolio parser → `portfolio_holdings` rows
- `mutual_fund_ingestion/agent/validate.py` — NAV/portfolio validation, quarantine writer, retry queue writer
- `mutual_fund_ingestion/agent/vlm.py` — `VLMClient` interface, null backend, Ollama HTTP backend
- `mutual_fund_ingestion/agent/runner.py` — orchestration: discover → extract → parse → validate → load

### Tests and Docs
- `tests/test_agent.py` — schema, discovery, parser routing, NAV/AMC/portfolio parsing, validation, quarantine, retry, dry-run

## Steps

### Phase R: Refactor — Consolidate Duplicate Utilities
1. [ ] Create `utils/__init__.py`, `utils/http.py` (consolidate `HttpSettings` + `build_session` from both modules)
2. [ ] Create `utils/url_utils.py` (consolidate `canonical_url`, `file_type_from_url` from 3 locations)
3. [ ] Create `utils/text_utils.py` (`safe_name`, `slugify` from multiple locations)
4. [ ] Update `mutual_fund_ingestion/http.py` → import from `utils/http.py` and re-export (backward compat)
5. [ ] Update `mutual_fund_ingestion/extract.py` → import from `utils/url_utils.py`, `utils/text_utils.py`
6. [ ] Update `mutual_fund_ingestion/browser.py` → import from `utils/`
7. [ ] Update `amfi_disclosure/http.py` → import from `utils/http.py`
8. [ ] Update `amfi_disclosure/downloader.py` → import from `utils/`
9. [ ] Move `amfi_disclosure/http.py` → `unused_codebase/` (consolidated, no longer needed as separate)
10. [ ] Archive legacy `Code Base/Dataset_Collection_Module/database_module/` to `unused_codebase/` with deprecation note

### Phase A: Database Layer
11. [ ] Add `psycopg2-binary` to `requirements.txt`
12. [ ] Create `agent/db.py` with SQLAlchemy models for all 17 tables matching schema spec (ingestion_runs, task_urls, source_pages, discovered_links, dataset_candidates, raw_artifacts, amcs, schemes, nav_history, documents, instruments, portfolio_snapshots, portfolio_holdings, staging_rows, validation_results, quarantine_rows, retry_queue) + `create_tables()` function + index creation + DB session helper
13. [ ] Create `agent/models.py` with `IngestionConfig`, `ParserResult`, `SourcePageRecord`, `DiscoveredLinkRecord`, `DatasetCandidateRecord`, `RawArtifactRecord` dataclasses

### Phase B: Configuration
14. [ ] Create `agent/config.py` with `AgentConfig` dataclass loading from CLI args + optional YAML file

### Phase C: Discovery + Extraction Core
15. [ ] Create `agent/discovery.py` with `URLQueue`, `DiscoveryEngine` — static HTTP fetch, HTML parsing, link extraction, relevance scoring using keywords from design spec, dataset type detection, domain policy (allow/block), dataset candidate classification
16. [ ] Create `agent/browser.py` with `BrowserExtractor` — Playwright navigation, screenshot, rendered HTML, network capture, button/form detection, download interception
17. [ ] Create `agent/extract.py` with `ArtifactCollector` — file download with retry, checksum (SHA256), MIME type detection, temp dir management, deduplication by checksum, raw file retention policy per config

### Phase D: Parsing
18. [ ] Create `agent/parser/nav.py` for AMFI NAV text/CSV parsing — scheme code → `nav_history`
19. [ ] Create `agent/parser/amc.py` for AMC list HTML table parsing — → `amcs`
20. [ ] Create `agent/parser/portfolio.py` for Excel portfolio parsing using pandas/openpyxl — → `portfolio_holdings`
21. [ ] Create `agent/parser/__init__.py` with `ParserRouter` dispatching by (dataset_type, file_type) and returning `ParserResult`

### Phase E: Validation + VLM
22. [ ] Create `agent/validate.py` with `validate_nav_rows`, `validate_portfolio_rows`, `write_quarantine`, `write_retry`, `write_validation_result` — staging-first, quarantine for failures, retry for recoverable failures
23. [ ] Create `agent/vlm.py` with `VLMClient` base class, `NullVLMClient`, `OllamaVLMClient` — page analysis payload/response format per design spec

### Phase F: Orchestration + CLI
24. [ ] Create `agent/runner.py` with `IngestionRunner` — orchestrates all stages, manages DB transaction, collects metrics, finalizes run status
25. [ ] Update `mutual_fund_ingestion/cli.py` with `run-agent`, `init-db`, `retry-failed`, `inspect-run` subcommands

### Phase T: Tests + Docs
26. [ ] Create `tests/test_agent.py` — schema creation, URL normalization, relevance scoring, dataset type classification, parser routing, NAV parse from fixture, Excel portfolio parse from fixture, AMC parse, validation, quarantine insert, retry queue, dry-run end-to-end
27. [ ] Update `docs/ai_context/CODEBASE_MAP.md` — add `agent/` module, `utils/` module, archive entries
28. [ ] Update `README.md` — add `run-agent` usage section
29. [ ] Run `python -m pytest tests/test_agent.py -v` — fix all failures
30. [ ] Run smoke test: `python -m mutual_fund_ingestion run-agent --task-url "<AMFI URL>" --dry-run --max-pages 5`

## Reuse Reference Map

| New Component | Reuses From | Adapt/Import |
|---|---|---|
| `agent/db.py` | design spec `07_postgresql_schema.md` | Implement from spec |
| `agent/config.py` | design spec `11_cli_config_and_operations.md` | Implement from spec |
| `agent/discovery.py` | `mutual_fund_ingestion/http.py` | Import `HttpSettings`, `build_session` |
| `agent/discovery.py` | `utils/url_utils.py` | Import `canonical_url`, `file_type_from_url` |
| `agent/discovery.py` | `mutual_fund_ingestion/source_discovery.py` | Adapt `discover_amfi_candidates` pattern |
| `agent/browser.py` | `mutual_fund_ingestion/browser.py` | Adapt `inspect_with_browser`, network capture |
| `agent/browser.py` | `amfi_disclosure/browser.py` | Adapt Playwright patterns, download interception |
| `agent/extract.py` | `mutual_fund_ingestion/http.py` | Import HTTP session |
| `agent/extract.py` | `amfi_disclosure/downloader.py` | Adapt `Downloader`, checksum, slugify patterns |
| `agent/extract.py` | `utils/text_utils.py` | Import `slugify` |
| `agent/parser/nav.py` | `amfi_disclosure/discovery.py` | Adapt date extraction patterns |
| `agent/parser/amc.py` | None | New implementation |
| `agent/parser/portfolio.py` | `Code Base/Dataset_Collection_Module/database_module/` | Adapt column mapping patterns, ignore old schema |
| `agent/validate.py` | design spec `09_validation_quarantine_and_provenance.md` | Implement from spec |
| `agent/vlm.py` | design spec `05_vlm_integration.md` | Implement from spec |
| `agent/runner.py` | design spec `02_end_to_end_architecture.md`, `03_agent_runtime_and_orchestration.md` | Implement from spec |
| `cli.py` | design spec `11_cli_config_and_operations.md` | Implement from spec |

## Verification

- `python -m pytest tests/test_agent.py -v` — all tests pass
- `python -m mutual_fund_ingestion run-agent --task-url "<AMFI URL>" --dry-run --max-pages 5` — run created, pages discovered, candidates stored
- `python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"` — schema created
- Portfolio parser fixture test using `Dataset/Monthly Reports October 2024/icici/ICICI Prudential Balanced Advantage Fund.xlsx`