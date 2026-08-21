# CODEBASE_MAP.md

Module ownership map for the mutual fund ingestion system.
Referenced by `AGENTS.md` §1 and §3. Update whenever module structure changes.

---

## Module Ownership

| Module | Layer | Responsibility | Public API |
|---|---|---|---|
| `mutual_fund_ingestion/__init__.py` | 2 | Public API surface — re-exports core classes and functions from profiling/ | `__all__` list |
| `mutual_fund_ingestion/cli.py` | 2 | CLI entry point — argument parsing, command dispatch, run identity, agent subcommands | `main()`, `build_parser()` |
| `mutual_fund_ingestion/profiling/__init__.py` | — | Phase 1A/1B profiling subpackage marker | — |
| `mutual_fund_ingestion/profiling/registry.py` | 5 | YAML registry loading — loads and validates `configs/amc_sources.yaml` | `load_registry()`, `load_sources()`, `DEFAULT_REGISTRY` |
| `mutual_fund_ingestion/profiling/models.py` | 5 | Schema classes — frozen dataclasses for all domain objects | `AMCSource`, `SourceRegistryEntry`, `SourceCandidate`, `ProviderProfile`, `CandidateLink`, `SourcePage` |
| `mutual_fund_ingestion/profiling/profiler.py` | 4 | Core profiling logic — static HTML + optional Playwright inspection, strategy detection | `ProfileContext`, `ProfileOptions`, `profile_source()`, `profile_sources()` |
| `mutual_fund_ingestion/profiling/extract.py` | 5 | HTML parsing — `EvidenceParser`, link/file/API extraction, document type hints | `EvidenceParser`, `extract_page_evidence()`, `safe_name()`, `canonical_url()`, `file_type_from_url()` |
| `mutual_fund_ingestion/profiling/http.py` | 5 | HTTP session — requests Session with retry/backoff and descriptive user-agent | `HttpSettings`, `build_session()`, `DEFAULT_USER_AGENT` |
| `mutual_fund_ingestion/profiling/browser.py` | 4 | Optional Playwright inspection — deterministic JS rendering, network capture, debug artifacts | `render_reference_html()`, `inspect_with_browser()`, `BrowserUnavailable`, `BrowserEvidence` |
| `mutual_fund_ingestion/profiling/artifacts.py` | 3 | Artifact paths, persistence — JSONL history append, latest snapshot write | `ArtifactPaths`, `load_latest_profiles()`, `write_profile_artifacts()` |
| `mutual_fund_ingestion/profiling/reports.py` | 3 | HTML/CSV report generation — metrics calculation, table rendering | `calculate_metrics()`, `generate_profile_reports()` |
| `mutual_fund_ingestion/profiling/source_discovery.py` | 4 | AMFI/SEBI candidate discovery — follows member pages, extracts provider URLs | `discover_amfi_candidates()`, `discover_sebi_candidates()` |
| `mutual_fund_ingestion/profiling/source_registry.py` | 3 | Candidate merging, YAML write — provenance ranking, domain deduplication, atomic writes | `merge_source_candidates()`, `write_source_registry_artifacts()`, `normalize_amc_name()` |
| `mutual_fund_ingestion/amfi_disclosure/` | — | AMFI portfolio disclosure crawler — isolated prototype, not imported by agent pipeline. **Status: ARCHIVED LEGACY PROTOTYPE — see Epic C. Do not extend.** | `Discoverer`, `Downloader`, `DisclosureLink` |
| `mutual_fund_ingestion/agent/__init__.py` | — | Agent package marker | — |
| `mutual_fund_ingestion/agent/runner.py` | 3 | Ingestion run orchestration — coordinates discover → extract → parse → validate → load | `IngestionRunner` |
| `mutual_fund_ingestion/agent/discovery.py` | 4 | URL queue, static HTTP fetch, link extraction, relevance scoring, dataset classification | `DiscoveryEngine` |
| `mutual_fund_ingestion/agent/browser.py` | 4 | Playwright extraction — rendered HTML, screenshots, network capture | `extract_with_browser()`, `BrowserUnavailable`, `BrowserResult` |
| `mutual_fund_ingestion/agent/extract.py` | 4 | Artifact download, SHA256 checksum, temp file management, retention policy | `ArtifactCollector` |
| `mutual_fund_ingestion/agent/parser/__init__.py` | 4 | Parser router — dispatches by (dataset_type, file_type) | `ParserRouter`, `route_parser()`, `parse_file()` |
| `mutual_fund_ingestion/agent/parser/nav.py` | 4 | AMFI NAV text/CSV/HTML parser → `nav_history` rows | `parse_nav_text()`, `parse_nav_csv()`, `parse_nav_html()` |
| `mutual_fund_ingestion/agent/parser/metadata.py` | 4 | Factsheet/SID/KIM/TER/AUM metadata parsers → document records | `parse_metadata_html()`, `parse_metadata_pdf()`, `parse_tabular_csv()` |
| `mutual_fund_ingestion/agent/parser/scheme_master.py` | 4 | Scheme master CSV/HTML parser → `schemes` rows | `parse_scheme_master_csv()`, `parse_scheme_master_html()` |
| `mutual_fund_ingestion/agent/parser/amc.py` | 4 | AMC provider list HTML parser → `amcs` rows | `parse_amc_html()` |
| `mutual_fund_ingestion/agent/parser/portfolio.py` | 4 | Excel/CSV portfolio disclosure parser → `portfolio_holdings` rows. **FIXED: header row detection works for real AMFI Excel files.** | `parse_portfolio_excel()`, `parse_portfolio_csv()` |
| `mutual_fund_ingestion/agent/validate.py` | 4 | NAV/portfolio/scheme_master/amc validation, quarantine writer, retry queue | `validate_nav_record()`, `validate_portfolio_record()`, `validate_scheme_master_record()`, `validate_amc_record()`, `validate_and_filter_records()` |
| `mutual_fund_ingestion/agent/vlm.py` | 4 | Pluggable VLM client — null backend (default) + Ollama backend. **analyze_page() IS called in runner.py (lines 179–195) when use_vlm=True. TASK-K004 complete.** | `VLMClient`, `NullVLMClient`, `OllamaVLMClient`, `PageAnalysisPayload`, `PageAnalysisDecision` |
| `mutual_fund_ingestion/agent/db.py` | 5 | SQLAlchemy models for all 23 tables + schema creation | 23 table classes, `create_tables()`, `get_session_maker()` |
| `mutual_fund_ingestion/agent/models.py` | 5 | Runtime dataclasses — `AgentResult`, `ParserResult`, record types | `AgentResult`, `ParserResult`, `SourcePageRecord`, `DiscoveredLinkRecord`, `DatasetCandidateRecord`, `RawArtifactRecord` |
| `mutual_fund_ingestion/agent/config.py` | 5 | Agent configuration from CLI args | `AgentConfig` |
| `mutual_fund_ingestion/agent/nav_pipeline.py` | 2 | **NEW** Dedicated NAV ingestion pipeline — backfill, incremental, gap detection, coverage | `NAVPipeline` |
| `mutual_fund_ingestion/agent/portfolio_pipeline.py` | 2 | **NEW** Dedicated Portfolio ingestion pipeline — strategy-aware, multi-AMC | `PortfolioPipeline` |
| `mutual_fund_ingestion/agent/scheme_identity.py` | 2 | **NEW** Scheme identity resolution — AMFI code, ISIN, fuzzy name, plan/option | `SchemeIdentityResolver`, `SchemeMappingManager` |
| `mutual_fund_ingestion/agent/coverage.py` | 2 | **NEW** Coverage & quality monitoring — 6 tables, calculator, alerts | `CoverageCalculator`, `get_coverage_report()` |
| `mutual_fund_ingestion/agent/artifact_storage.py` | 3 | **NEW** Raw artifact storage abstraction — Local/S3 backends, tiered retention | `ArtifactStorageManager`, `StorageBackend` |
| `mutual_fund_ingestion/agent/source_registry.py` | 2 | **NEW** Unified source capability registry — loads AMFI census + AMC matrix | `SourceCapabilityRegistry`, `get_registry()` |
| `utils/__init__.py` | — | Shared utilities package marker | — |
| `utils/http.py` | 5 | Shared HTTP session — HttpSettings + build_session (consolidated) | `HttpSettings`, `build_session()`, `DEFAULT_USER_AGENT` |
| `utils/url_utils.py` | 5 | URL/text utilities — canonical_url, file_type_from_url, safe_name, slugify (consolidated) | `canonical_url()`, `file_type_from_url()`, `safe_name()`, `slugify()` |
| `utils/text_utils.py` | 5 | Text normalization utilities | `normalize_amc_name()` |

---

## Notebooks

**Current plan:** `docs/06_plans/active/STORY_NOTEBOOK_SERIES_PLAN.md`

| Notebook | Status | Purpose |
|---|---|---|
| `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb` | Story rewrite complete | System health, test baseline, artifact inventory, DB table inventory, notebook inventory |
| `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb` | Stale index; replace with pointer or archive later | Current thin index to 01A/01B; not a story notebook |
| `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb` | Rewrite planned | Source registry inputs, provenance, AMFI/SEBI reference entries, provider readiness |
| `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb` | Rewrite planned | Provider profiles, strategies, candidate links, debug evidence |
| `notebooks/mutual_fund_ingestion/02_agent_pipeline_inspection.ipynb` | Keep/rewrite as canonical | DB-backed agent pipeline inspection |
| `notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb` | Duplicate/stale; merge or replace with pointer later | Older component walkthrough with stale docs reference |
| `notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb` | Rewrite planned | Discovery/candidate review from DB and runtime artifacts |

---

## Configs

| Config | Purpose |
|---|---|
| `configs/amc_sources.yaml` | Curated source registry — 53 AMC entries + AMFI + SEBI reference entries |

---

## Tests

| Path | Coverage |
|---|---|---|
| `tests/test_mutual_fund_ingestion.py` | Phase 1A/1B: registry, model validation, candidate merging, extraction, profiling, artifacts, reports, CLI |
| `tests/test_agent.py` | Agent: config, parser routing, NAV/AMC parsing, validation, quarantine, CLI flags |
| `tests/test_amfi_disclosure.py` | amfi_disclosure: disclosure discovery, file downloading, JSONL round-trip, download naming |
| `tests/fixtures/provider_static.html` | Static HTML with portfolio links, factsheet links, API hints |
| `tests/fixtures/amfi_members.html` | AMFI member list HTML |
| `tests/fixtures/amfi_member_detail.html` | AMFI member detail page with provider URL |
| `tests/fixtures/amfi_portfolio.html` | AMFI portfolio disclosure page with AMC links |
| `tests/fixtures/amc_portfolio.html` | AMC-level portfolio landing page with download links |

---

## Output Directories

| Directory | Produced by | Contents |
|---|---|---|
| `data/raw/mutual_funds/source_registry/` | Phase 1A | `source_registry_candidates.jsonl`, `source_registry.latest.json` |
| `data/raw/mutual_funds/provider_profiles/` | Phase 1B | `provider_profiles.jsonl` (append history), `provider_profiles.latest.json` (snapshot) |
| `data/reports/mutual_funds/` | Both phases | `source_registry_report.html`, `provider_profile_report.html`, `provider_profile_summary.csv` |
| `data/debug/mutual_funds/provider_profiles/<safe_amc_name>/` | Phase 1B | `static.html`, `rendered.html`, `screenshot.png`, `network_log.jsonl`, `accessibility_snapshot.json`, `profiler_error.json` |

---

## Off-Limits — Do Not Import Into Agent Pipeline

| Path | Reason |
|---|---|
| `mutual_fund_ingestion/amfi_disclosure/` | Standalone AMFI crawler prototype — do not import from agent pipeline; isolated by design |
| `docs/archive/legacy_experiments/` | Legacy experiments — inspect for historical context only, do not import |
| `data/datasets/` | Historical XLSX/CSV samples — fixtures for future parser tests, not production imports |

---

## Phase Status

| Phase | Status | Key modules |
|---|---|---|
| Phase 1A | Implemented | `profiling/source_discovery.py`, `profiling/source_registry.py`, `profiling/registry.py` |
| Phase 1B | Implemented | `profiling/profiler.py`, `profiling/extract.py`, `profiling/browser.py`, `profiling/http.py`, `profiling/artifacts.py`, `profiling/reports.py` |
| **Dataset Census** | ✅ **Implemented** | `configs/amfi_dataset_census.yaml`, `configs/amc_capability_matrix.yaml`, `agent/source_registry.py` |
| **Scheme Identity** | ✅ **Implemented** | `agent/scheme_identity.py` |
| **NAV Pipeline** | ✅ **Implemented** | `agent/nav_pipeline.py` |
| **Portfolio Pipeline** | ✅ **Implemented** | `agent/portfolio_pipeline.py` |
| **Artifact Storage** | ✅ **Implemented** | `agent/artifact_storage.py` |
| **Coverage & Quality** | ✅ **Implemented** | `agent/coverage.py` |
| Task-URL Agent (Phase 2 vertical slice) | ✅ Implemented | `agent/runner.py`, `agent/discovery.py`, `agent/browser.py`, `agent/extract.py`, `agent/parser/`, `agent/validate.py`, `agent/vlm.py`, `agent/db.py`, `agent/upserts.py`, `agent/artifact_processor.py` |
| Phase 2+ | In progress (7/10 AMCs) | — |
| Phase 3: document classification | Not started | — |
| Phase 4: parsing | Partially (parsers exist, pipelines use them) | — |
| Phase 5+: validation, quarantine, canonical PostgreSQL | ✅ Implemented (extended with coverage) | — |

---

## Import Guidance for Future Phases

When implementing Phase 1.5 or later, import from these public entry points — never from internal files:

- Phase 1A data: `profiling/source_registry.py` → `load_registry()`, `SourceRegistryPaths`, `merge_source_candidates()`
- Phase 1B data: `profiling/artifacts.py` → `load_latest_profiles()`, `ArtifactPaths`
- Schema models: `profiling/models.py` → `AMCSource`, `ProviderProfile`, `SourceRegistryEntry`
- HTTP: `utils/http.py` → `build_session()`, `HttpSettings` (use utils, not profiling)
- Agent config: `agent/config.py` → `AgentConfig`
- Agent runner: `agent/runner.py` → `IngestionRunner`
- Agent DB: `agent/db.py` → `create_tables()`, `get_session_maker()`
- Agent parsers: `agent/parser/__init__.py` → `route_parser()`, `parse_file()`
- Agent validation: `agent/validate.py` → `validate_and_filter_records()`
- Shared utils: `utils/http.py`, `utils/url_utils.py`, `utils/text_utils.py` — use these instead of duplicating logic
