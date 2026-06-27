# Completed Work Log

_Historical record of completed work. Preserve; do not delete._

---

## Phase 1A — Source Registry Bootstrap
**Completed**: By Jun 17, 2026

- Implemented `mutual_fund_ingestion/profiling/source_discovery.py` — AMFI/SEBI candidate discovery
- Implemented `mutual_fund_ingestion/profiling/source_registry.py` — candidate merge, dedup, YAML write
- Implemented `mutual_fund_ingestion/profiling/registry.py` — YAML registry loader
- CLI: `bootstrap-sources` with `--dry-run`, `--no-reference-network`, `--limit`
- Artifacts: `data/raw/mutual_funds/source_registry/` (JSONL + latest JSON)
- Reports: `data/reports/mutual_funds/source_registry_report.html`
- 38 Phase 1A/1B tests pass

**Frozen**: Do not modify Phase 1A modules.

---

## Phase 1B — Provider Website Profiling
**Completed**: By Jun 17, 2026

- Implemented `mutual_fund_ingestion/profiling/profiler.py` — static HTML + optional Playwright
- Implemented `mutual_fund_ingestion/profiling/extract.py` — EvidenceParser, link/API extraction
- Implemented `mutual_fund_ingestion/profiling/browser.py` — Playwright inspection, debug artifacts
- Implemented `mutual_fund_ingestion/profiling/artifacts.py` — JSONL history + latest snapshot
- Implemented `mutual_fund_ingestion/profiling/reports.py` — HTML/CSV report generation
- CLI: `profile-providers` with `--limit`, `--amc`, `--force`, `--use-playwright`
- Artifacts: `data/raw/mutual_funds/provider_profiles/` (JSONL + latest JSON)
- Reports: `data/reports/mutual_funds/provider_profile_report.html`, `provider_profile_summary.csv`
- Debug: `data/debug/mutual_funds/provider_profiles/<safe_amc_name>/`
- Review notebooks: `01_phase_1_provider_profiling_review.ipynb`, `01a_...`, `01b_...`

**Frozen**: Do not modify Phase 1B modules.

---

## Task-URL Agent Core
**Implemented**: By Jun 17, 2026

- `agent/runner.py` — IngestionRunner orchestrating full BFS → download → parse → validate → upsert
- `agent/discovery.py` — DiscoveryEngine with relevance scoring and dataset classification
- `agent/browser.py` — Playwright fallback with network capture
- `agent/extract.py` — ArtifactCollector: streaming download, SHA256
- `agent/db.py` — 17 SQLAlchemy table models, `create_tables()`
- `agent/config.py` — AgentConfig
- `agent/models.py` — runtime dataclasses
- CLI: `init-db`, `run-agent`, `inspect-run`, `retry-failed`
- 36 agent unit tests, 22 DB integration tests

---

## Epic A — Repository Hygiene
**Completed**: Jun 21, 2026

- TASK-A001: Added `*.db`, `*.db-journal`, `*.db-wal`, `*.db-shm` to `.gitignore`
- TASK-A002: Removed `pika` from `requirements.txt`
- TASK-A004: Added `financial_env/` to `.gitignore`

---

## Epic B — Bug Fixes (Subset)
**Completed**: Jun 21, 2026

- TASK-D001: Fixed `retry-failed` crash when `--run-id` not provided
- TASK-D002: Fixed CLI logging format — added timestamps and log level labels
- TASK-P001: Fixed `portfolio.py` column mapping — header row detection for real AMFI Excel files

---

## Epic E — Logging and Observability
**Completed**: Jun 22, 2026 (per CHATGPT_PROJECT_MEMORY update)

- TASK-E001–E007: Added log events for link discovery count, download success, parser selection, parsed record count, validation results, retry queue writes, run completion summary

---

## Epic F — PostgreSQL Schema Tests (Partial)
**Completed**: Jun 22, 2026

- TASK-F002: Added nav_history composite index test
- TASK-F003: Verified amcs.normalized_name unique constraint
- db.py: Added unique index on nav_history for SQLite-compatible ON CONFLICT upsert

---

## Epic K — VLM Wiring
**Completed**: Jun 22, 2026

- TASK-K004: Wired `self.vlm.analyze_page()` in runner BFS loop (lines 179–195)
- Triggered when `use_vlm=True` AND relevance score < `vlm_confidence_threshold`

---

## Epic L — Raw Artifact Retention
**Completed**: Jun 22, 2026

- TASK-L001: Implemented file move from temp dir to `raw_dir/<run_id>/` in runner
- Verified by `test_smoke_keep_raw_files_creates_file_in_raw_dir` passing

---

## Parser Additions
**Completed**: Jun 21–22, 2026

- TASK-N003: Implemented `parse_nav_html()` in `agent/parser/nav.py`
- TASK-P004: Implemented `parse_portfolio_csv()` in `agent/parser/portfolio.py`
- Parser router updated for: `nav_history_txt`, `nav_html`, `portfolio_csv`
- discovery.py: Removed 'Download' from RELEVANCE_KEYWORDS[high] (false positive fix)
- runner.py: Added `classify_dataset()` for file URLs

---

## Epic R — End-to-End Fixture Tests
**Completed**: Jun 22, 2026

- TASK-R001: Created `tests/fixtures/amfi_seed_page.html`
- TASK-R002: Created `tests/fixtures/amc_disclosure_page.html`
- TASK-R003: `test_fixture_seed_page_writes_source_pages` — passes
- TASK-R004: `test_fixture_nav_file_upserted_to_nav_history` — passes

---

## Epic S — Smoke Tests
**Completed**: Jun 22, 2026

- TASK-S001: `test_smoke_amfi_seed_page_reachable` — passes
- TASK-S002: `test_smoke_amfi_discovers_nav_candidate` — passes
- Additional: `test_smoke_keep_raw_files_creates_file_in_raw_dir` — passes

---

## amfi_disclosure — Legacy Prototype
**Status**: Complete as a standalone prototype. Not extended further.

- Standalone AMFI portfolio disclosure crawler
- CLI: `python -m amfi_disclosure run`
- 11 tests pass
- Not coupled to agent pipeline

---

## utils/ — Shared Utilities Consolidation
**Completed**: By Jun 17, 2026

- `utils/http.py` — consolidated HTTP session (profiling/http.py delegates here)
- `utils/url_utils.py` — canonical_url, file_type_from_url, safe_name, slugify
- `utils/text_utils.py` — normalize_amc_name
