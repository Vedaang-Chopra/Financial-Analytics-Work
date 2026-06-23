# Current Codebase Status and Refactor Plan

_Generated: 2026-06-17. Based on full codebase audit, 85/85 tests passing, live CLI verification._

---

## 1. Executive Summary

This project is an agentic mutual fund data ingestion system for Indian capital markets. It ingests data from provider/AMC websites, AMFI, and other sources, then parses, validates, and stores data in PostgreSQL.

**Overall status**: The system is substantially further along than the existing PLAN.md suggests. Phase 1A/1B is production-complete. The Task-URL Agent has a working orchestration loop with full DB persistence, a functional parser framework (NAV, AMC, Scheme Master, Portfolio), browser automation, artifact download with checksums, validation/quarantine, and both `inspect-run` and `retry-failed` CLI commands. 85 tests pass.

**Key gaps remaining before end-to-end agent runs work reliably:**

1. VLM is instantiated but `analyze_page()` is never called — all candidates silently skip VLM analysis.
2. `portfolio.py` column mapping is broken for real Excel files (`header=None` produces integer column indices, but aliases expect string headers from row 0).
3. `retry-failed` CLI crashes when `--run-id` not provided (tries `uuid.UUID(None)`).
4. Raw file retention: ArtifactCollector marks `retained=True` in the result dict but never moves files to a permanent `raw_dir`.
5. NAV HTML parser, SID/KIM/TER/factsheet parsers are not implemented.
6. Root-level `*.db` test artifacts are not in `.gitignore`.

---

## 2. Target System From Specs

Source: `docs/design/task_url_agent_design_pack/`, `AGENTS.md`, `CHATGPT_PROJECT_MEMORY.md`.

**What it should do:**

1. Accept one or more task URLs (initially AMFI disclosure portal)
2. Crawl and discover relevant data source pages
3. Classify discovered URLs as dataset candidates (NAV, portfolio, factsheet, etc.)
4. Download raw files with checksums and retention policy
5. Route each file to the correct parser
6. Stage parsed rows and validate them
7. Quarantine invalid rows with reason codes
8. Upsert valid rows into canonical PostgreSQL tables
9. Track full provenance (source_url, raw_artifact_id) on every canonical row
10. Surface quarantine and retry queues for recovery
11. Support Playwright browser fallback for JS-rendered pages
12. Support local VLM as last-resort classifier for opaque pages

**Strategy order (non-negotiable per AGENTS.md):**
`static_html → network_api → playwright → vlm_required → manual_review`

**Target canonical tables:** `amcs`, `schemes`, `nav_history`, `portfolio_holdings`, `portfolio_snapshots`, `instruments`, `documents` (17 tables total including operational tables).

---

## 3. Repository Inventory

### Classification Key

File type: `production_core | production_support | test | fixture | notebook | documentation | generated_artifact | legacy_or_experimental | unknown_needs_review`
Layer: `cli | orchestration | discovery | browser_automation | vlm_integration | download_extraction | classification | parser | validation | database | provenance | retry_quarantine | utils`

### Root Level

| Path | Type | Layer | Notes |
|---|---|---|---|
| `mutual_fund_ingestion/` | production_core | all | Main package |
| `utils/` | production_support | utils | Shared HTTP, URL, text utilities |
| `amfi_disclosure/` | legacy_or_experimental | — | Standalone prototype, isolated |
| `tests/` | test | — | 74 tests in suite |
| `test_amfi_disclosure.py` | test | — | 11 tests for amfi_disclosure module |
| `fixtures/` | fixture | — | Root HTML fixtures |
| `configs/amc_sources.yaml` | production_support | utils | 53 AMC entries + AMFI + SEBI |
| `data/` | generated_artifact | — | Phase 1 outputs, gitignored (partially) |
| `notebooks/` | notebook | — | Inspection notebooks only |
| `docs/` | documentation | — | Design specs, CODEBASE_MAP, index |
| `plans/` | documentation | — | Implementation plans |
| `requirements.txt` | production_support | — | Dependencies |
| `AGENTS.md` | documentation | — | Mandatory governance rules |
| `CHATGPT_PROJECT_MEMORY.md` | documentation | — | Continuity context for AI agents |
| `PLAN.md` | documentation | — | Prior audit + 6 tasks (partially done) |
| `README.md` | documentation | — | User-facing CLI guide |
| `test.db`, `test2.db`, `test3.db`, `final_test.db` | generated_artifact | — | SQLite test DBs — NOT in .gitignore |
| `test_mock.db` | generated_artifact | — | 0 bytes, unused — NOT in .gitignore |

### utils/

| File | Type | Layer | Notes |
|---|---|---|---|
| `utils/http.py` | production_support | utils | HttpSettings + build_session with retry/backoff |
| `utils/url_utils.py` | production_support | utils | canonical_url, file_type_from_url, safe_name, slugify |
| `utils/text_utils.py` | production_support | utils | normalize_amc_name |

### mutual_fund_ingestion/ (Phase 1A/1B — frozen)

| File | Type | Layer | Notes |
|---|---|---|---|
| `__init__.py` | production_core | cli | Re-exports public API |
| `__main__.py` | production_core | cli | Entry point → cli.main() |
| `cli.py` | production_core | cli | 438 LOC, 8 subcommands including agent wiring |
| `models.py` | production_core | utils | 6 frozen dataclasses (Phase 1 domain objects) |
| `registry.py` | production_core | utils | YAML registry loader and validator |
| `http.py` | production_support | utils | 4-line delegate to utils/http.py |
| `extract.py` | production_core | classification | EvidenceParser — HTML link/form/script/API extraction (Phase 1) |
| `browser.py` | production_core | browser_automation | Playwright inspection for Phase 1 profiling |
| `profiler.py` | production_core | discovery | Provider profiling with strategy detection |
| `source_discovery.py` | production_core | discovery | AMFI/SEBI candidate discovery |
| `source_registry.py` | production_core | provenance | Candidate merge, dedup, atomic YAML write |
| `artifacts.py` | production_core | provenance | JSONL append history + latest snapshot |
| `reports.py` | production_core | utils | HTML/CSV report generation |

### mutual_fund_ingestion/agent/ (Task-URL Agent)

| File | Type | Layer | Notes |
|---|---|---|---|
| `__init__.py` | production_core | — | Empty package marker |
| `config.py` | production_core | utils | AgentConfig dataclass (all CLI flags) |
| `models.py` | production_core | utils | ParserResult, AgentResult, record types |
| `db.py` | production_core | database | 17 SQLAlchemy table models, get_session_maker |
| `runner.py` | production_core | orchestration | 750 LOC — IngestionRunner with full DB pipeline |
| `discovery.py` | production_core | discovery | DiscoveryEngine, LinkExtractor, relevance scoring |
| `browser.py` | production_core | browser_automation | extract_with_browser() — Playwright + network capture |
| `extract.py` | production_core | download_extraction | ArtifactCollector — download, checksum, temp file |
| `validate.py` | production_core | validation | NAV + portfolio validators, quarantine writer |
| `vlm.py` | production_support | vlm_integration | NullVLMClient + OllamaVLMClient (not invoked in runner) |
| `parser/__init__.py` | production_core | parser | route_parser(), parse_file() router |
| `parser/nav.py` | production_core | parser | parse_nav_text(), parse_nav_csv() |
| `parser/amc.py` | production_core | parser | parse_amc_html() |
| `parser/portfolio.py` | production_core | parser | parse_portfolio_excel() — has column mapping bug |
| `parser/scheme_master.py` | production_core | parser | parse_scheme_master_csv(), parse_scheme_master_html() |

### amfi_disclosure/ (Legacy prototype)

| File | Type | Layer | Notes |
|---|---|---|---|
| `models.py` | legacy_or_experimental | utils | DisclosureLink dataclass |
| `discovery.py` | legacy_or_experimental | discovery | Crawls AMFI disclosure portal |
| `downloader.py` | legacy_or_experimental | download_extraction | HTTP download with caching |
| `browser.py` | legacy_or_experimental | browser_automation | Playwright wrapper |
| `http.py` | legacy_or_experimental | utils | Retry session |
| `cli.py` | legacy_or_experimental | cli | discover, download, run subcommands |

---

## 4. Current Implementation Map

### Data flow through agent pipeline

```
CLI (cli.py)
  └─ IngestionRunner.__init__()            # Config, session, discovery engine, VLM client
       └─ IngestionRunner.run()
            ├─ INSERT ingestion_runs       # ✅ DB write
            ├─ INSERT task_urls            # ✅ DB write
            ├─ BFS crawl loop
            │   ├─ DiscoveryEngine.fetch() # ✅ HTTP GET
            │   ├─ INSERT source_pages     # ✅ DB write
            │   ├─ extract_links()         # ✅ regex link extraction
            │   ├─ score_relevance()       # ✅ keyword scoring
            │   ├─ INSERT discovered_links # ✅ DB write
            │   ├─ classify_dataset()      # ✅ dataset type hint
            │   ├─ INSERT dataset_candidates # ✅ DB write
            │   └─ [browser fallback]      # ✅ Playwright (if use_browser)
            ├─ _download_and_process_artifact()
            │   ├─ ArtifactCollector.download() # ✅ streaming download + SHA256
            │   ├─ INSERT raw_artifacts    # ✅ DB write
            │   ├─ route_parser()          # ✅ dispatch by (dataset_type, file_type)
            │   ├─ parse_file()            # ✅ calls parser, returns ParserResult
            │   ├─ INSERT staging_rows     # ✅ DB write
            │   ├─ validate_and_filter_records() # ✅ validation
            │   ├─ INSERT quarantine_rows  # ✅ DB write for invalid
            │   └─ _upsert_canonical()     # ✅ upserts to amcs/schemes/nav_history/portfolio
            ├─ COMMIT                      # ✅ end of run
            └─ UPDATE ingestion_runs.status = "complete"
```

### VLM flow (broken gap)

```
runner.__init__()
  └─ self.vlm = NullVLMClient() or OllamaVLMClient()  # ✅ instantiated
                                                         # ❌ analyze_page() never called in main loop
                                                         # ❌ requires_vlm=False hardcoded on all candidates
```

---

## 5. Capability Status Matrix

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | CLI entry point | **complete** | 8 subcommands, all wired |
| 2 | Task URL ingestion | **complete** | run-agent with --task-url / --task-url-file |
| 3 | Source/page discovery | **complete** | BFS crawl, relevance scoring, dataset hint classification |
| 4 | Static scraping | **complete** | HTTP GET + HTML link extraction |
| 5 | Chromium/Playwright browsing | **complete** | Playwright integration with network capture and screenshot |
| 6 | Network/API capture | **partial** | Browser captures network calls; no direct API endpoint targeting from runner |
| 7 | VLM integration | **partial** | Client exists + wired to config; analyze_page() never called in main loop |
| 8 | Dataset candidate classification | **complete** | Keyword-based dataset_type hints on all discovered links |
| 9 | Raw file download | **complete** | Streaming download, SHA256 checksum, content-type check |
| 10 | Raw file retention policy | **partial** | `retained` flag passed to DB, but files not moved to permanent raw_dir |
| 11 | Parser routing | **complete** | route_parser() dispatches on (dataset_type, file_type) |
| 12 | NAV parser (text/CSV) | **complete** | parse_nav_text(), parse_nav_csv() implemented and tested |
| 13 | NAV parser (HTML) | **missing** | Router maps to "nav_html" but no parse_nav_html() function |
| 14 | AMC/provider parser | **complete** | parse_amc_html() — HTML link extraction for AMC list |
| 15 | Scheme master parser | **complete** | parse_scheme_master_csv(), parse_scheme_master_html() with column alias mapping |
| 16 | Portfolio disclosure parser | **partial** | parse_portfolio_excel() exists but column mapping broken for real files (header=None + integer column indices vs string aliases) |
| 17 | Factsheet parser | **missing** | Not in router, no implementation |
| 18 | SID/KIM/TER/statutory parser | **missing** | Not in router, no implementation |
| 19 | AUM/AAUM parser | **missing** | Not in router, no implementation |
| 20 | Staging table load | **complete** | INSERT staging_rows for every parsed file |
| 21 | Validation rules | **partial** | NAV and portfolio validated; scheme_master, AMC, factsheet etc. not validated |
| 22 | Quarantine rows | **complete** | write_quarantine_row() used in runner for invalid records |
| 23 | Retry queue | **partial** | RetryQueue table written; retry-failed CLI resets status but relies on re-running agent |
| 24 | Canonical PostgreSQL loading | **complete** | _upsert_nav_history,_upsert_amcs,_upsert_schemes,_upsert_portfolio all implemented |
| 25 | Provenance tracking | **complete** | raw_artifact_id and source_url on every canonical row |
| 26 | Tests | **complete** | 85/85 pass — unit + integration + DB |
| 27 | Logging/debuggability | **partial** | LOGGER used in most modules; no structured format, no timestamps in CLI output, VLM never logged |
| 28 | Notebooks | **complete** | 4 notebooks for Phase 1A, 1B, and agent inspection |
| 29 | Docs/design alignment | **partial** | Most specs match implementation; CODEBASE_MAP and plans/task_url_ingestion_agent.md overstate completion; retry_failed bug not documented |

---

## 6. What Is Actually Working

All of the following have been verified by test execution and code inspection:

- **Phase 1A/1B pipeline**: source registry bootstrap, candidate merging, provider profiling with static HTML and optional Playwright, strategy detection, report generation. 38 tests cover this.
- **Agent DB schema**: 17 tables created correctly by `init-db`. Verified by `test_init_db_creates_all_tables`.
- **Run creation**: IngestionRun and TaskURL records written at the start of every run.
- **Page crawl with DB persistence**: SourcePage, DiscoveredLink, DatasetCandidate written during BFS loop.
- **Playwright browser fallback**: `extract_with_browser()` returns HTML, links, screenshots, network captures.
- **Artifact download**: ArtifactCollector streams file, computes SHA256, writes to temp dir, returns size/checksum/path.
- **Parser routing**: route_parser() correctly dispatches 10 dataset_type/file_type combinations.
- **NAV text parser**: Handles TAB-delimited AMFI NAV all schemes file format. Tested.
- **NAV CSV parser**: Handles CSV NAV format. Tested.
- **AMC HTML parser**: Extracts AMC name + URL from HTML. Tested.
- **Scheme master CSV parser**: Flexible column alias mapping. Tested with both standard and alternative column names.
- **Canonical upserts**: _upsert_nav_history,_upsert_amcs,_upsert_schemes,_upsert_portfolio all write to canonical tables using SQLAlchemy with upsert semantics.
- **Validation**: validate_nav_record(), validate_portfolio_record() tested.
- **Quarantine**: QuarantineRow written for invalid records. Tested.
- **Staging rows**: StagingRow written for every parsed artifact. Tested.
- **inspect-run CLI**: Fully implemented — shows all 9 table sections for a run.
- **retry-failed CLI**: Works when --run-id is provided. Bug when --run-id omitted (see §7).
- **amfi_disclosure module**: Standalone portfolio disclosure crawler. All 11 tests pass.
- **CLI**: All 8 subcommands registered and invoke correctly.

---

## 7. What Is Partial or Broken

### BROKEN — Will crash or produce wrong results

**B-1: `retry-failed` without `--run-id` crashes**

- `cli.py:_retry_failed()` line ~350: `run_id = uuid.UUID(args.run_id)`
- `args.run_id` is `None` when `--run-id` not provided (CLI marks it optional)
- `uuid.UUID(None)` raises `TypeError`
- Fix: add `if not args.run_id` guard, either fail with message or process all pending retries

**B-2: `portfolio.py` column mapping broken for real Excel files**

- `parse_portfolio_excel()` calls `pd.read_excel(..., header=None)` so columns are integers (0, 1, 2...)
- `_map_columns(df)` then maps `str(0)` → `"0"`, `str(1)` → `"1"` etc.
- None of these match the column aliases ("security_name", "percentage_to_nav" etc.)
- Result: no columns are correctly mapped; all security_names come from `df.columns[0]` which is `0`
- Fix: detect header row (first non-empty row), re-read Excel with `header=<row_idx>`, or manually set df.columns from row 0

### PARTIAL — Works in limited scenarios, silently fails otherwise

**P-1: VLM not invoked**

- `runner.py` instantiates `self.vlm` correctly based on `use_vlm` config flag
- `self.vlm.analyze_page()` is never called anywhere in the BFS loop
- `requires_vlm=False` is hardcoded on all DatasetCandidate records
- Impact: `--use-vlm` flag does nothing at runtime

**P-2: Raw file retention incomplete**

- `ArtifactCollector.download()` returns `"retained": self.keep_raw_files` in result dict
- `runner.py` line 360 stores this in `raw_artifacts.retained` column
- Files are never actually moved from temp dir to a permanent `raw_dir`
- When temp dir is cleaned up, retained files are lost
- Fix: in `_download_and_process_artifact()`, if `artifact_result["retained"]`, move/copy file to `config.raw_dir / run_id / safe_name`

**P-3: Network/API capture not used as discovery source**

- `extract_with_browser()` returns `downloads` (network calls with file extensions)
- These are used to create DatasetCandidates from browser links
- But the design spec requires treating embedded API endpoints (JSON data URLs) as first-class dataset candidates before Playwright
- Runner currently only uses browser network captures as an addendum, not as a separate strategy step

**P-4: Validation coverage is incomplete**

- `validate_and_filter_records()` routes to NAV or portfolio validators
- No validators for: scheme_master, amc_provider_list, factsheet, SID/KIM/TER, AUM/AAUM
- These parse successfully but produce unvalidated staging rows

**P-5: `inspect-run` and `retry-failed` use `--database-url` (PostgreSQL) but test DBs are SQLite**

- Tests use SQLite but production requires PostgreSQL
- No in-memory or file-based PostgreSQL alternative for local debugging without a PG server
- Impact: cannot easily test CLI commands against local data without PG

**P-6: Logging is inconsistent**

- Most agent modules use `LOGGER = logging.getLogger(__name__)` correctly
- `runner.py` has good LOGGER calls throughout the main loop
- But: no log formatter is configured by CLI (no timestamps, no level labels in output)
- `cli.py` sets `logging.basicConfig(level=...)` but doesn't set format string
- Logs from library code (SQLAlchemy, requests) may flood output at DEBUG level

---

## 8. What Is Missing

| Feature | Spec Reference | Priority |
|---|---|---|
| NAV HTML parser (`parse_nav_html`) | parser spec §08 | Medium — AMFI provides HTML NAV pages |
| Factsheet parser | spec §08 | Low — complex PDF/HTML |
| SID/KIM/TER parser | spec §08 | Low — regulatory documents |
| AUM/AAUM parser | spec §08 | Low |
| Portfolio CSV parser (separate from Excel) | spec §08 | Medium — CSV variants exist |
| VLM invocation in main loop | spec §05 | Medium — last-resort classification |
| Permanent raw file move to raw_dir | spec §10 | High — retention policy not enforced |
| Structured logging (JSON or key=value) | AGENTS.md §16 | Medium |
| Phase 2 (raw document download from Phase 1 profiles) | phase_2/ design pack | Not started |
| Phase 3+ (analytics, recovery) | future phases | Not started |

---

## 9. Duplicate / Legacy / Conflicting Code

### Intentional duplication (same name, different purpose — acceptable)

| Location A | Location B | Assessment |
|---|---|---|
| `mutual_fund_ingestion/extract.py` (EvidenceParser — HTML parser for Phase 1) | `mutual_fund_ingestion/agent/extract.py` (ArtifactCollector — file downloader) | Different classes, different purposes. Names could be improved but not a true conflict. |
| `mutual_fund_ingestion/browser.py` (Phase 1 profiler browser) | `mutual_fund_ingestion/agent/browser.py` (agent artifact browser) | Same underlying Playwright library, different roles. Acceptable. |
| `mutual_fund_ingestion/http.py` (4-line delegate) | `utils/http.py` (real implementation) | Intentional. Delegate pattern preserves Phase 1 backward compat. |

### Legacy code (unused but harmless)

| File | Issue |
|---|---|
| `amfi_disclosure/` | Standalone prototype, fully working, but not called by any agent pipeline code. Not referenced from `mutual_fund_ingestion/`. Safe to keep as archived prototype or document as "Phase 0 proof-of-concept". |
| `requirements.txt`: `pika` | RabbitMQ client. Not imported anywhere in the codebase. Likely from an early design iteration with a message queue. Should be removed. |

### Plans that conflict with current state

| Document | Conflict |
|---|---|
| `PLAN.md` Section 1.5 | States "runner.run() does NOT insert to PostgreSQL" — this is **wrong** as of current code. Runner does write to DB. |
| `plans/task_url_ingestion_agent.md` | Claims "50 passing tests (29 Phase 1 + 21 agent)" — actual count is 85 tests (38 Phase 1 + 36 agent + 11 amfi_disclosure). The document is stale. |
| `PLAN.md` Task 1 (EvidenceParser → LinkExtractor) | This was done — `agent/discovery.py` now uses `LinkExtractor` class. Task can be marked complete. |
| `PLAN.md` Task 2 (Wire runner.run() to DB) | Also done — runner writes to all major tables. Task can be marked complete. |

---

## 10. Documentation Status

| Document | Authoritative? | Current? | Action |
|---|---|---|---|
| `AGENTS.md` | ✅ Yes — mandatory governance | ✅ Yes | Keep. Read before every change. |
| `CHATGPT_PROJECT_MEMORY.md` | ✅ Yes — AI agent continuity | ⚠️ Partially stale (test counts, runner gap) | Update section on "Current Status" after this audit. |
| `docs/ai_context/CODEBASE_MAP.md` | ✅ Yes — module ownership | ⚠️ Incomplete (amfi_disclosure classification, missing portfolio.py bug) | Update after next refactor task. |
| `docs/design/task_url_agent_design_pack/` | ✅ Yes — design specs | ✅ Yes | Keep. These are the authoritative behavioral specs. |
| `docs/design/phase_1/` | ✅ Yes — Phase 1 specs | ✅ Yes | Keep frozen. Phase 1 is complete. |
| `docs/design/phase_2/` | ✅ Yes — Phase 2 specs | ✅ Yes (designed, not implemented) | Keep. This is the next major work item. |
| `docs/design/mutual_fund_project_memory_pack/` | ✅ Yes — project continuity | ⚠️ May be stale | Read before starting Phase 2. Update if contradicted by current state. |
| `docs/README_DOCS_INDEX.md` | ✅ Yes — navigation | ✅ Yes | Keep. Update when new docs are added. |
| `PLAN.md` | ⚠️ Partially stale | ❌ Several items are now done | Mark completed tasks, add note that runner.py does write to DB. |
| `plans/task_url_ingestion_agent.md` | ⚠️ Partially stale | ❌ Test counts wrong, some gaps not listed | Update to reflect actual state after this audit. |
| `plans/task_url_ingestion_detailed_implementation_plan.md` | ✅ Mostly accurate | ✅ Yes | Keep as historical build plan. |
| `README.md` | ✅ Yes — user guide | ✅ Yes | Keep current. Update test count. |

**Recommendation: do not delete any docs.** They form a valuable historical record and continuity chain. Update stale entries in-place.

---

## 11. System Rules / Skills Compliance Review

Evaluating against `AGENTS.md`.

| Rule | Status | Notes |
|---|---|---|
| 5-layer architecture | ✅ Followed | CLI → Orchestration → Core → Utils/Schema clearly separated |
| No giant pipeline functions | ⚠️ Partial | `runner.run()` is 200+ LOC with inline logic; should delegate more to helpers |
| Public functions have type hints + docstrings | ⚠️ Partial | Most functions have type hints; docstrings present on some, missing on others |
| No hardcoded values | ⚠️ Partial | `requires_vlm=False` hardcoded; some magic strings in relevance keywords |
| No silent exceptions | ⚠️ Partial | `try/except Exception as exc: errors.append(...)` swallows exceptions in parsers without re-raising |
| Provider-first principle | ✅ Followed | Phase 1 profiles providers; agent can be pointed at any provider URL |
| Strategy order (static → playwright → VLM) | ⚠️ Partial | Static and Playwright done; VLM wired but not invoked |
| Raw file preservation | ⚠️ Partial | Files downloaded but not permanently retained |
| Staging before canonical | ✅ Followed | All records go through staging_rows before canonical upserts |
| Provenance on every canonical row | ✅ Followed | raw_artifact_id and source_url on all upserts |
| Retry/quarantine | ✅ Followed | QuarantineRow and RetryQueue written |
| Tests required per phase | ✅ Followed | 85 tests covering all major paths |
| Notebooks for inspection only | ✅ Followed | All 4 notebooks are inspection/analysis only |
| Update CODEBASE_MAP with every change | ⚠️ Partial | CODEBASE_MAP exists but not fully up to date |
| No new code duplication | ✅ Followed | No unnecessary duplication found |
| Import only from **init**.py / interfaces | ⚠️ Partial | Some tests import internal module paths directly |
| Self-check 17-point checklist | ❌ Not visible | No evidence checklist was run before last commit |

---

## 12. Logging and Debuggability Review

**Current state:**

- Most agent modules define `LOGGER = logging.getLogger(__name__)` — correct pattern.
- `runner.py` logs: run start/end, page fetch (INFO), warnings for download failures, parser misses, Playwright unavailability.
- `cli.py` calls `logging.basicConfig(level=args.log_level)` — no format string set, so output has no timestamps or log levels in most terminals.
- No structured JSON logging anywhere.
- No CLI-visible progress counter (e.g., "Processed 12/50 pages").

**What's missing per spec (`AGENTS.md` §16 equivalent):**

| Log Event | Current | Required |
|---|---|---|
| Run start/end with run_id | ✅ | ✅ |
| Task URL queued | ✅ (via task_url write log) | ✅ |
| Page fetched (URL, status code) | ✅ LOGGER.info | ✅ |
| Links discovered (count) | ❌ Not logged | Should log |
| Dataset candidates found (count + types) | ❌ Not logged | Should log |
| Browser fallback used | ✅ LOGGER.warning if unavailable | ✅ |
| VLM invoked | ❌ Never invoked | N/A until fixed |
| File downloaded (URL, size, checksum) | ⚠️ Only on failure | Should log on success too |
| Parser selected | ⚠️ Only on miss | Should log on success |
| Rows parsed (count) | ❌ Not logged | Should log |
| Rows validated (pass/fail count) | ❌ Not logged | Should log |
| Rows inserted | ✅ In run completion log | ✅ |
| Rows quarantined | ✅ In run completion log | ✅ |
| Retry task created | ❌ Not logged | Should log |
| Failures with URL and reason | ✅ LOGGER.warning | ✅ |

**Refactor needed:**

1. Add log format with timestamps: `logging.basicConfig(level=..., format="%(asctime)s %(levelname)s %(name)s: %(message)s")`
2. Add `LOGGER.info("Discovered %d links, %d candidates from %s", ...)` after link extraction
3. Add `LOGGER.info("Downloaded %s (%d bytes, sha256=%s)", url, size, checksum[:8])` on success
4. Add `LOGGER.info("Parser %s returned %d records from %s", parser_name, len(records), url)` after parsing
5. Add `LOGGER.info("Quarantined %d records from %s: %s", count, url, reason)` after quarantine writes

---

## 13. Database and Generated Artifact Review

### Root-level SQLite databases

| File | Size | Purpose | Disposition |
|---|---|---|---|
| `test.db` | 212 KB | SQLite from integration tests (created by test suite via tempfile.mktemp) | Generated artifact — add `*.db` to `.gitignore` |
| `test2.db` | 212 KB | Same | Same |
| `test3.db` | 212 KB | Same | Same |
| `final_test.db` | 212 KB | Same | Same |
| `test_mock.db` | 0 bytes | Appears unused | Same |

These are generated by `tests/test_agent_db.py` which uses `tempfile.mktemp(suffix=".db")` but the files are left at root rather than in `/tmp`. The temp path generator creates them at a system temp path but at least one test appears to have left them in the project root.

**Action**: Add `*.db` to `.gitignore`. Investigate whether the test creates them in the project root or if these were manually created during development — either way, gitignore is the right fix.

### .gitignore gaps

Current `.gitignore` covers: `.env`, `venv/`, `__pycache__/`, `.ipynb_checkpoints/`, specific `data/` subdirs, specific report files.

**Missing patterns to add:**

```
*.db
*.db-journal
*.db-wal
*.db-shm
data/tmp/
*.playwright-trace
.playwright/
playwright-report/
raw_downloads/
```

### data/ directory

Generated by Phase 1 runs. Already partially gitignored (raw profiles, reports). No changes needed to policy.

---

## 14. Refactor Strategy

Prioritized by: impact on correctness → impact on completeness → code quality.

### Priority 1: Fix broken behaviors (do before any new feature work)

1. Fix `portfolio.py` column mapping (re-read Excel with header row detection)
2. Fix `retry-failed` crash when `--run-id` not provided
3. Add `*.db` to `.gitignore`
4. Fix logging format (add timestamps and level labels)

### Priority 2: Complete partial features (core pipeline)

1. Implement raw file retention (move files to raw_dir when keep_raw_files=True)
2. Wire VLM invocation in runner main loop (call analyze_page() for candidates that trigger requires_vlm)
3. Add NAV HTML parser
4. Add portfolio CSV parser (separate from Excel; same column mapping fix applies)

### Priority 3: Extend validator coverage

1. Add scheme_master validation rules (required: scheme_code, scheme_name, amc_name)
2. Add AMC validation rules (required: name; normalized_name must be unique)

### Priority 4: Code quality and compliance

1. Update CODEBASE_MAP.md to reflect current state
2. Update plans/task_url_ingestion_agent.md with accurate status
3. Update CHATGPT_PROJECT_MEMORY.md current status section
4. Add log events for links discovered, candidates found, parser selected, rows parsed
5. Remove `pika` from requirements.txt
6. Mark PLAN.md tasks 1 and 2 as complete

### Priority 5: Next phase (not yet started)

1. Phase 2: Raw document download from Phase 1 provider profiles (see `docs/design/phase_2/`)
2. Add remaining parsers: SID/KIM/TER, factsheet, AUM/AAUM (when Phase 2 downloads them)

---

## 15. Very Small Step-by-Step Task Plan

Each task is independently testable. Do them in order.

---

### TASK-001 — Add `*.db` to `.gitignore`

**Goal:** Remove SQLite test databases from git tracking.

**Files touched:**

- `.gitignore`

**Implementation:**
Add these lines to `.gitignore`:

```
*.db
*.db-journal
*.db-wal
*.db-shm
data/tmp/
```

**Test:**

```bash
git status  # should no longer show test.db, test2.db etc.
python -m pytest tests/ test_amfi_disclosure.py -v  # all 85 pass
```

**Expected output:** test*.db files disappear from `git status` untracked list.

**Rollback risk:** None.

**Dependencies:** None.

---

### TASK-002 — Fix logging format in CLI

**Goal:** All log output should include timestamps and log level.

**Files touched:**

- `mutual_fund_ingestion/cli.py`

**Implementation:**
Find the `logging.basicConfig(level=...)` call and change to:

```python
logging.basicConfig(
    level=getattr(logging, args.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

**Test:**

```bash
python -m mutual_fund_ingestion run-agent --task-url https://example.com \
    --database-url sqlite:///test_logging.db --log-level DEBUG --dry-run 2>&1 | head -5
```

**Expected output:** Lines like `2026-06-17 00:10:01 INFO     mutual_fund_ingestion.agent.runner: Starting ingestion run ...`

**Rollback risk:** None — purely cosmetic.

**Dependencies:** None.

---

### TASK-003 — Fix `retry-failed` crash when `--run-id` not provided

**Goal:** `retry-failed` should either require `--run-id` explicitly or handle the case gracefully.

**Files touched:**

- `mutual_fund_ingestion/cli.py` (`_retry_failed` function, ~line 341)

**Implementation:**
Add guard at start of `_retry_failed`:

```python
if not args.run_id:
    print("--run-id is required for retry-failed")
    return 1
```

(Or alternatively change CLI to `required=True` for `--run-id`.)

**Test:**

```bash
python -m mutual_fund_ingestion retry-failed --database-url sqlite:///test_retry.db
# should print error message and exit 1, not crash with TypeError
```

**Expected output:** `--run-id is required for retry-failed` with exit code 1.

**Rollback risk:** None.

**Dependencies:** None.

---

### TASK-004 — Fix portfolio parser column mapping

**Goal:** `parse_portfolio_excel()` correctly maps columns from real AMFI portfolio Excel files.

**Files touched:**

- `mutual_fund_ingestion/agent/parser/portfolio.py`

**Implementation:**
Replace the current `pd.read_excel(..., header=None)` approach with header row detection:

```python
# Strategy: read without header, find the row where most COLUMN_ALIASES match,
# use that as the header row
raw = pd.read_excel(BytesIO(content), sheet_name=sheet_name, header=None)
# Find header row: first row where > 2 cells match known aliases
header_row = 0
for i, row in raw.iterrows():
    normalized = [_normalize_col(str(v)) for v in row.values if str(v).strip()]
    known = sum(1 for v in normalized if v in {a for aliases in COLUMN_ALIASES.values() for a in aliases})
    if known >= 2:
        header_row = i
        break
df = pd.read_excel(BytesIO(content), sheet_name=sheet_name, header=header_row)
```

**Test:**
Write a unit test that creates an Excel file with real AMFI column names ("Name of Instrument", "% to NAV", "Market Value") and verifies `parse_portfolio_excel()` returns records with `security_name` and `percentage_to_nav` populated.

```bash
python -m pytest tests/test_agent.py -k portfolio -v
python -m pytest tests/test_agent_db.py::ParserUpsertTests::test_portfolio_parser_creates_holdings -v
```

**Expected output:** Both tests pass. New test verifies real-column-name parsing.

**Rollback risk:** Low — existing tests cover the "nice" case; real files were broken before.

**Dependencies:** None.

---

### TASK-005 — Add discovery count log events to runner

**Goal:** Make crawl progress visible without needing to query the DB.

**Files touched:**

- `mutual_fund_ingestion/agent/runner.py`

**Implementation:**
In `run()` after link extraction loop, add:

```python
LOGGER.info("Page %s: %d links extracted, %d candidates identified", url, len(links), candidates_from_page)
```

After artifact download:

```python
LOGGER.info("Downloaded %s: %d bytes sha256=%s...", url, artifact_result["size_bytes"], artifact_result["checksum"][:12])
```

After parsing:

```python
LOGGER.info("Parser %s: %d records from %s", parser_result.parser_name, len(parser_result.records), url)
```

**Test:**

```bash
python -m mutual_fund_ingestion run-agent \
    --task-url https://www.amfiindia.com/nav-history \
    --database-url sqlite:///smoke_test.db \
    --max-pages 2 --log-level INFO 2>&1 | grep -E "Page |Downloaded|Parser"
```

**Expected output:** Visible progress lines as crawl runs.

**Rollback risk:** None — log additions only.

**Dependencies:** TASK-002 (log format).

---

### TASK-006 — Implement raw file retention (move to raw_dir)

**Goal:** When `--keep-raw-files` is set, downloaded files are permanently preserved in `raw_dir`.

**Files touched:**

- `mutual_fund_ingestion/agent/runner.py` (`_download_and_process_artifact`)

**Implementation:**
After `raw_artifact` DB record is flushed (after line ~363), add:

```python
if artifact_result.get("retained") and self.config.raw_dir:
    import shutil
    raw_dir = Path(self.config.raw_dir) / self.run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / Path(artifact_result["local_path"]).name
    shutil.copy2(artifact_result["local_path"], dest)
    raw_artifact.local_path = str(dest)
    LOGGER.info("Retained raw file: %s", dest)
```

**Test:**

```bash
python -c "
import tempfile, os
from pathlib import Path
from mutual_fund_ingestion.agent.config import AgentConfig
# verify raw_dir attribute exists on AgentConfig
print(hasattr(AgentConfig, 'raw_dir'))
"
# Then write a unit test using FakeSession that verifies shutil.copy2 is called
```

**Expected output:** After a dry run with `--keep-raw-files --raw-dir ./test_raw`, files appear in `./test_raw/<run_id>/`.

**Rollback risk:** Low.

**Dependencies:** TASK-002.

---

### TASK-007 — Add NAV HTML parser

**Goal:** Handle AMFI-style HTML NAV pages (parser router already routes to `nav_html` but no function exists).

**Files touched:**

- `mutual_fund_ingestion/agent/parser/nav.py` (add `parse_nav_html`)
- `mutual_fund_ingestion/agent/parser/__init__.py` (add elif branch for `nav_html`)

**Implementation:**

```python
def parse_nav_html(content: bytes | str, metadata: dict) -> ParserResult:
    """Parse NAV data from HTML tables (e.g., AMFI NAV history page)."""
    # Use lxml/html to find tables with NAV-like columns
    # Look for scheme_code, scheme_name, nav_value, nav_date columns
    ...
```

**Test:**
Add fixture `tests/fixtures/nav_page.html` with a minimal table and write test:

```bash
python -m pytest tests/test_agent.py -k nav_html -v
```

**Expected output:** Test passes; parser returns records with scheme_code and nav_value.

**Rollback risk:** Low — no existing code changed.

**Dependencies:** None.

---

### TASK-008 — Wire VLM invocation in runner

**Goal:** When a page classification is low-confidence and `use_vlm=True`, call `self.vlm.analyze_page()`.

**Files touched:**

- `mutual_fund_ingestion/agent/runner.py` (BFS loop, after relevance scoring)

**Implementation:**
After relevance scoring for a page, if score < threshold and `self.config.use_vlm`:

```python
if relevance_score < 0.5 and self.config.use_vlm:
    payload = PageAnalysisPayload(url=url, html=html, screenshot_path=None, links=links)
    decision = self.vlm.analyze_page(payload)
    if decision and decision.is_relevant:
        relevance_score = decision.confidence
        dataset_type_hint = decision.dataset_type
        LOGGER.info("VLM classified %s as %s (confidence=%.2f)", url, dataset_type_hint, decision.confidence)
```

Also mark resulting DatasetCandidates with `requires_vlm=True`.

**Test:**
Add a test that patches `OllamaVLMClient.analyze_page` and verifies it's called when `use_vlm=True` and a page has low relevance score.

```bash
python -m pytest tests/test_agent_db.py -k vlm -v
```

**Expected output:** Test passes; VLM call is made for low-confidence pages.

**Rollback risk:** Low — NullVLMClient (default) is unchanged.

**Dependencies:** TASK-005 (logging).

---

### TASK-009 — Add scheme_master and AMC validation rules

**Goal:** validate_and_filter_records() should validate scheme_master and AMC records, not just NAV and portfolio.

**Files touched:**

- `mutual_fund_ingestion/agent/validate.py`
- `mutual_fund_ingestion/agent/runner.py` (route to new validators)

**Implementation:**

```python
def validate_scheme_master_record(record: dict) -> list[str]:
    errors = []
    if not record.get("scheme_code"):
        errors.append("missing scheme_code")
    if not record.get("scheme_name"):
        errors.append("missing scheme_name")
    return errors

def validate_amc_record(record: dict) -> list[str]:
    errors = []
    if not record.get("name"):
        errors.append("missing name")
    return errors
```

Update `validate_and_filter_records` to route these dataset types.

**Test:**

```bash
python -m pytest tests/test_agent.py -k validation -v
```

Add new test cases for scheme_master and AMC validation.

**Expected output:** All validation tests pass including new cases.

**Rollback risk:** None.

**Dependencies:** None.

---

### TASK-010 — Update stale documentation

**Goal:** Bring PLAN.md, plans/task_url_ingestion_agent.md, and CHATGPT_PROJECT_MEMORY.md into sync with actual state.

**Files touched:**

- `PLAN.md` — mark Tasks 1 and 2 complete; correct "runner does not write to DB" statement
- `plans/task_url_ingestion_agent.md` — update test count to 85, update gap list
- `CHATGPT_PROJECT_MEMORY.md` — update Current Status section

**Test:**

```bash
grep -n "50 passing\|21 agent\|does NOT insert" PLAN.md plans/task_url_ingestion_agent.md CHATGPT_PROJECT_MEMORY.md
# Should return no matches after update
```

**Expected output:** No stale claims in key docs.

**Rollback risk:** None — documentation only.

**Dependencies:** All of the above tasks (complete the fixes before documenting them).

---

### TASK-011 — Remove `pika` from requirements.txt

**Goal:** Remove unused RabbitMQ dependency.

**Files touched:**

- `requirements.txt`

**Implementation:**
Delete the `pika` line.

**Test:**

```bash
grep -r "import pika\|from pika" .  # should return nothing
python -m pytest tests/ test_amfi_disclosure.py -v  # all 85 pass
```

**Expected output:** No import errors; 85 tests pass.

**Rollback risk:** None.

**Dependencies:** None.

---

## 16. Tests and Verification Commands

### Run full test suite

```bash
python -m pytest tests/ test_amfi_disclosure.py -v
# Expected: 85 passed in ~4s
```

### Run only agent tests

```bash
python -m pytest tests/test_agent.py tests/test_agent_db.py -v
# Expected: 66 passed
```

### Verify CLI works

```bash
python -m mutual_fund_ingestion --help
python -m mutual_fund_ingestion run-agent --help
python -m mutual_fund_ingestion init-db --help
python -m mutual_fund_ingestion inspect-run --help
python -m mutual_fund_ingestion retry-failed --help
```

### Initialize a local SQLite schema for smoke testing

```bash
python -m mutual_fund_ingestion init-db --database-url sqlite:///smoke.db
# Expected: prints table names and exits 0
```

### Smoke crawl (no real network needed if dry-run)

```bash
python -m mutual_fund_ingestion run-agent \
    --task-url https://www.amfiindia.com/nav-history \
    --database-url sqlite:///smoke.db \
    --max-pages 3 --max-files 1 --log-level INFO
# Expected: creates ingestion_run, task_url, source_pages records
```

### Verify inspect-run works

```bash
# Get a run_id from the smoke run, then:
python -m mutual_fund_ingestion inspect-run \
    --database-url sqlite:///smoke.db \
    --run-id <run-id-from-smoke>
```

---

## 17. Recommended Immediate Next Task

**Start with TASK-004 (fix portfolio parser column mapping).**

Reason: It is the most impactful correctness bug. The portfolio parser is the core value-generating path for the system (portfolio holdings are the primary analytics target per `CHATGPT_PROJECT_MEMORY.md`). It currently silently produces no records for real AMFI Excel files while appearing to run successfully. The fix is contained to one function in one file with zero risk of breaking other tests.

After TASK-004, run:

```bash
python -m pytest tests/test_agent.py tests/test_agent_db.py -v
```

Then proceed with TASK-001 (gitignore), TASK-002 (logging format), TASK-003 (retry-failed crash), and TASK-005 (log events).

The entire Priority 1 + Priority 2 backlog (TASK-001 through TASK-008) should be completable in a single focused session before Phase 2 work begins.

## 18. Completion Notes — 2026-06-22

**Tasks completed through this session: 88-110 (23 tasks across Epics A-T)**

### Test Results

- **125 tests pass** (was 85 before this session)
- 2 smoke tests skip gracefully when network unavailable

### Key Fixes Delivered

1. **File URL dataset_type classification** — `runner.py` now calls `classify_dataset()` for file URLs instead of returning generic "relevant"
2. **NAV .txt file parsing** — Added ("nav_history","txt") route to PARSER_ROUTER
3. **nav_history ON CONFLICT** — Added unique index for SQLite-compatible upsert
4. **RELEVANCE_KEYWORDS** — Removed "Download" from high keywords to prevent false relevance matches

### New Test Coverage

- R003/R004: Fixture-based end-to-end tests (seed page + NAV file upsert)
- DatabaseSchemaTests: nav_history composite index, amc normalized_name unique
- DiscoveryEngineTests: portfolio xlsx classification
- test_smoke.py: 3 smoke tests (AMFI reachability, NAV discovery, raw file retention)
- ArtifactCollectorTests: file size limit enforcement

### Remaining Known Issues

- VLM `analyze_page()` never called in BFS loop (K004/K005 wired but threshold not reached in practice)
- Some pre-existing type checker warnings in metadata.py (false positives)

### Next Session Starting Point

Task 111+ of 140. Review `docs/session_state.md` for full context.
