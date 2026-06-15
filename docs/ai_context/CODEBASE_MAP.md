# CODEBASE_MAP.md

Module ownership map for the mutual fund ingestion system.
Referenced by `AGENTS.md` §1 and §3. Update whenever module structure changes.

---

## Module Ownership

| Module | Layer | Responsibility | Public API |
|---|---|---|---|
| `mutual_fund_ingestion/__init__.py` | 2 | Public API surface — re-exports core classes and functions | `__all__` list |
| `mutual_fund_ingestion/cli.py` | 2 | CLI entry point — argument parsing, command dispatch, run identity, agent subcommands | `main()`, `build_parser()` |
| `mutual_fund_ingestion/registry.py` | 5 | YAML registry loading — loads and validates `configs/amc_sources.yaml` | `load_registry()`, `load_sources()`, `DEFAULT_REGISTRY` |
| `mutual_fund_ingestion/models.py` | 5 | Schema classes — frozen dataclasses for all domain objects | `AMCSource`, `SourceRegistryEntry`, `SourceCandidate`, `ProviderProfile`, `CandidateLink`, `SourcePage` |
| `mutual_fund_ingestion/profiler.py` | 4 | Core profiling logic — static HTML + optional Playwright inspection, strategy detection | `ProfileContext`, `ProfileOptions`, `profile_source()`, `profile_sources()` |
| `mutual_fund_ingestion/extract.py` | 5 | HTML parsing — `EvidenceParser`, link/file/API extraction, document type hints | `EvidenceParser`, `extract_page_evidence()`, `safe_name()`, `canonical_url()`, `file_type_from_url()` |
| `mutual_fund_ingestion/http.py` | 5 | HTTP session — requests Session with retry/backoff and descriptive user-agent | `HttpSettings`, `build_session()`, `DEFAULT_USER_AGENT` |
| `mutual_fund_ingestion/browser.py` | 4 | Optional Playwright inspection — deterministic JS rendering, network capture, debug artifacts | `render_reference_html()`, `inspect_with_browser()`, `BrowserUnavailable`, `BrowserEvidence` |
| `mutual_fund_ingestion/artifacts.py` | 3 | Artifact paths, persistence — JSONL history append, latest snapshot write | `ArtifactPaths`, `load_latest_profiles()`, `write_profile_artifacts()` |
| `mutual_fund_ingestion/reports.py` | 3 | HTML/CSV report generation — metrics calculation, table rendering | `calculate_metrics()`, `generate_profile_reports()` |
| `mutual_fund_ingestion/source_discovery.py` | 4 | AMFI/SEBI candidate discovery — follows member pages, extracts provider URLs | `discover_amfi_candidates()`, `discover_sebi_candidates()` |
| `mutual_fund_ingestion/source_registry.py` | 3 | Candidate merging, YAML write — provenance ranking, domain deduplication, atomic writes | `merge_source_candidates()`, `write_source_registry_artifacts()`, `normalize_amc_name()` |
| `mutual_fund_ingestion/agent/__init__.py` | — | Agent package marker | — |
| `mutual_fund_ingestion/agent/runner.py` | 3 | Ingestion run orchestration — coordinates discover → extract → parse → validate → load | `IngestionRunner` |
| `mutual_fund_ingestion/agent/discovery.py` | 4 | URL queue, static HTTP fetch, link extraction, relevance scoring, dataset classification | `DiscoveryEngine` |
| `mutual_fund_ingestion/agent/browser.py` | 4 | Playwright extraction — rendered HTML, screenshots, network capture | `extract_with_browser()`, `BrowserUnavailable`, `BrowserResult` |
| `mutual_fund_ingestion/agent/extract.py` | 4 | Artifact download, SHA256 checksum, temp file management, retention policy | `ArtifactCollector` |
| `mutual_fund_ingestion/agent/parser/__init__.py` | 4 | Parser router — dispatches by (dataset_type, file_type) | `ParserRouter`, `route_parser()`, `parse_file()` |
| `mutual_fund_ingestion/agent/parser/nav.py` | 4 | AMFI NAV text/CSV parser → `nav_history` rows | `parse_nav_text()`, `parse_nav_csv()` |
| `mutual_fund_ingestion/agent/parser/amc.py` | 4 | AMC provider list HTML parser → `amcs` rows | `parse_amc_html()` |
| `mutual_fund_ingestion/agent/parser/portfolio.py` | 4 | Excel portfolio disclosure parser → `portfolio_holdings` rows | `parse_portfolio_excel()` |
| `mutual_fund_ingestion/agent/validate.py` | 4 | NAV/portfolio validation, quarantine writer, retry queue | `validate_nav_record()`, `validate_portfolio_record()`, `validate_and_filter_records()` |
| `mutual_fund_ingestion/agent/vlm.py` | 4 | Pluggable VLM client — null backend (default) + Ollama backend | `VLMClient`, `NullVLMClient`, `OllamaVLMClient`, `PageAnalysisPayload`, `PageAnalysisDecision` |
| `mutual_fund_ingestion/agent/db.py` | 5 | SQLAlchemy models for all 17 tables + schema creation | 17 table classes, `create_tables()`, `get_session_maker()` |
| `mutual_fund_ingestion/agent/models.py` | 5 | Runtime dataclasses — `AgentResult`, `ParserResult`, record types | `AgentResult`, `ParserResult`, `SourcePageRecord`, `DiscoveredLinkRecord`, `DatasetCandidateRecord`, `RawArtifactRecord` |
| `mutual_fund_ingestion/agent/config.py` | 5 | Agent configuration from CLI args | `AgentConfig` |
| `utils/__init__.py` | — | Shared utilities package marker | — |
| `utils/http.py` | 5 | Shared HTTP session — HttpSettings + build_session (consolidated) | `HttpSettings`, `build_session()`, `DEFAULT_USER_AGENT` |
| `utils/url_utils.py` | 5 | URL/text utilities — canonical_url, file_type_from_url, safe_name, slugify (consolidated) | `canonical_url()`, `file_type_from_url()`, `safe_name()`, `slugify()` |
| `utils/text_utils.py` | 5 | Text normalization utilities | `normalize_amc_name()` |

---

## Notebooks

| Notebook | Phase | Purpose |
|---|---|---|
| `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb` | index | Index to 01A and 01B; artifact availability check |
| `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb` | 1A | Source registry inputs, provenance, quality checks, Phase 1B readiness |
| `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb` | 1B | Provider profiles, strategies, candidate links, debug evidence, Phase 1.5 readiness |

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
| `tests/fixtures/provider_static.html` | Static HTML with portfolio links, factsheet links, API hints |
| `tests/fixtures/amfi_members.html` | AMFI member list HTML |
| `tests/fixtures/amfi_member_detail.html` | AMFI member detail page with provider URL |

---

## Output Directories

| Directory | Produced by | Contents |
|---|---|---|
| `data/raw/mutual_funds/source_registry/` | Phase 1A | `source_registry_candidates.jsonl`, `source_registry.latest.json` |
| `data/raw/mutual_funds/provider_profiles/` | Phase 1B | `provider_profiles.jsonl` (append history), `provider_profiles.latest.json` (snapshot) |
| `data/reports/mutual_funds/` | Both phases | `source_registry_report.html`, `provider_profile_report.html`, `provider_profile_summary.csv` |
| `data/debug/mutual_funds/provider_profiles/<safe_amc_name>/` | Phase 1B | `static.html`, `rendered.html`, `screenshot.png`, `network_log.jsonl`, `accessibility_snapshot.json`, `profiler_error.json` |

---

## Off-Limits — Do Not Import Into Phase 1+

| Path | Reason |
|---|---|
| `amfi_disclosure/` | Standalone AMFI crawler prototype — isolated; Phase 1 scope is provider profiling, not document download |
| `Code Base/` | Legacy experiments — inspect for historical context only |
| `Dataset/` | Historical XLSX/CSV samples — fixtures for future parser tests, not Phase 1 |

---

## Phase Status

| Phase | Status | Key modules |
|---|---|---|
| Phase 1A | Implemented | `source_discovery.py`, `source_registry.py`, `registry.py` (load) |
| Phase 1B | Implemented | `profiler.py`, `extract.py`, `browser.py`, `http.py`, `artifacts.py`, `reports.py` |
| Task-URL Agent | Implemented | `agent/runner.py`, `agent/discovery.py`, `agent/browser.py`, `agent/extract.py`, `agent/parser/`, `agent/validate.py`, `agent/vlm.py`, `agent/db.py` |
| Phase 2+ | Not yet implemented | — |

---

## Import Guidance for Future Phases

When implementing Phase 1.5 or later, import from these public entry points — never from internal files:

- Phase 1A data: `source_registry.py` → `load_registry()`, `SourceRegistryPaths`, `merge_source_candidates()`
- Phase 1B data: `artifacts.py` → `load_latest_profiles()`, `ArtifactPaths`
- Schema models: `models.py` → `AMCSource`, `ProviderProfile`, `SourceRegistryEntry`
- HTTP: `http.py` → `build_session()`, `HttpSettings`
- Agent config: `agent/config.py` → `AgentConfig`
- Agent runner: `agent/runner.py` → `IngestionRunner`
- Agent DB: `agent/db.py` → `create_tables()`, `get_session_maker()`
- Agent parsers: `agent/parser/__init__.py` → `route_parser()`, `parse_file()`
- Agent validation: `agent/validate.py` → `validate_and_filter_records()`
- Shared utils: `utils/http.py`, `utils/url_utils.py`, `utils/text_utils.py` — use these instead of duplicating logic
