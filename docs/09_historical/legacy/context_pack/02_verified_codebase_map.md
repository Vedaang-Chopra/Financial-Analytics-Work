# Verified Codebase Map

_Verified: 2026-06-23. Supersedes `docs/ai_context/CODEBASE_MAP.md` for current accuracy.
The original CODEBASE_MAP.md should still be read by agents; this file adds corrections and updates._

---

## Module Ownership

| Module | Layer | Responsibility | Public API | Notes |
|---|---|---|---|---|
| `mutual_fund_ingestion/__init__.py` | 2 | Public API surface — re-exports from profiling/ | `__all__` | — |
| `mutual_fund_ingestion/cli.py` | 2 | CLI entry point — 8 subcommands | `main()`, `build_parser()` | Logging format fixed (timestamps) |
| `mutual_fund_ingestion/profiling/registry.py` | 5 | YAML registry loading | `load_registry()`, `load_sources()` | Frozen — Phase 1A |
| `mutual_fund_ingestion/profiling/models.py` | 5 | Schema dataclasses | `AMCSource`, `ProviderProfile`, etc. | Frozen |
| `mutual_fund_ingestion/profiling/profiler.py` | 4 | Static HTML + Playwright profiling | `profile_source()`, `profile_sources()` | Frozen |
| `mutual_fund_ingestion/profiling/extract.py` | 5 | HTML link/API extraction | `EvidenceParser`, `extract_page_evidence()` | Frozen |
| `mutual_fund_ingestion/profiling/http.py` | 5 | HTTP session | `HttpSettings`, `build_session()` | Delegates to utils/http.py |
| `mutual_fund_ingestion/profiling/browser.py` | 4 | Playwright inspection | `render_reference_html()`, `inspect_with_browser()` | Frozen |
| `mutual_fund_ingestion/profiling/artifacts.py` | 3 | Artifact persistence | `write_profile_artifacts()`, `load_latest_profiles()` | Frozen |
| `mutual_fund_ingestion/profiling/reports.py` | 3 | HTML/CSV report generation | `generate_profile_reports()` | Frozen |
| `mutual_fund_ingestion/profiling/source_discovery.py` | 4 | AMFI/SEBI candidate discovery | `discover_amfi_candidates()` | Frozen |
| `mutual_fund_ingestion/profiling/source_registry.py` | 3 | Candidate merge, YAML write | `merge_source_candidates()` | Frozen |
| `mutual_fund_ingestion/amfi_disclosure/` | — | **LEGACY PROTOTYPE** — standalone AMFI crawler | `Discoverer`, `Downloader` | Do not import from agent pipeline |
| `mutual_fund_ingestion/agent/runner.py` | 3 | Ingestion run orchestration | `IngestionRunner` | VLM wired ✅; raw retention ✅ |
| `mutual_fund_ingestion/agent/discovery.py` | 4 | BFS crawl, relevance scoring, dataset classification | `DiscoveryEngine` | classify_dataset() added; relevance keywords fixed |
| `mutual_fund_ingestion/agent/browser.py` | 4 | Playwright extraction | `extract_with_browser()` | — |
| `mutual_fund_ingestion/agent/extract.py` | 4 | Artifact download, SHA256, retention | `ArtifactCollector` | Retention implemented ✅ |
| `mutual_fund_ingestion/agent/parser/__init__.py` | 4 | Parser router | `route_parser()`, `parse_file()` | Routes: nav_txt, nav_csv, nav_html, nav_history_txt, portfolio_excel, portfolio_csv, scheme_master_csv, scheme_master_html, amc_html |
| `mutual_fund_ingestion/agent/parser/nav.py` | 4 | NAV parsers | `parse_nav_text()`, `parse_nav_csv()`, `parse_nav_html()` | nav_html added ✅ |
| `mutual_fund_ingestion/agent/parser/amc.py` | 4 | AMC provider parser | `parse_amc_html()` | — |
| `mutual_fund_ingestion/agent/parser/portfolio.py` | 4 | Portfolio disclosure parser | `parse_portfolio_excel()`, `parse_portfolio_csv()` | Header row detection fixed ✅; CSV parser added ✅ |
| `mutual_fund_ingestion/agent/parser/scheme_master.py` | 4 | Scheme master parser | `parse_scheme_master_csv()`, `parse_scheme_master_html()` | — |
| `mutual_fund_ingestion/agent/validate.py` | 4 | NAV/portfolio validation, quarantine | `validate_nav_record()`, `validate_portfolio_record()`, `validate_and_filter_records()` | scheme_master/AMC validators: verify if added (TASK-G001/G002) |
| `mutual_fund_ingestion/agent/vlm.py` | 4 | VLM client | `VLMClient`, `NullVLMClient`, `OllamaVLMClient` | analyze_page() called in runner ✅ |
| `mutual_fund_ingestion/agent/db.py` | 5 | 17 SQLAlchemy table models | 17 table classes, `create_tables()` | Unique index on nav_history added ✅ |
| `mutual_fund_ingestion/agent/models.py` | 5 | Runtime dataclasses | `AgentResult`, `ParserResult`, record types | — |
| `mutual_fund_ingestion/agent/config.py` | 5 | Agent config | `AgentConfig` | — |
| `utils/http.py` | 5 | Shared HTTP session | `HttpSettings`, `build_session()` | — |
| `utils/url_utils.py` | 5 | URL utilities | `canonical_url()`, `file_type_from_url()`, `safe_name()` | — |
| `utils/text_utils.py` | 5 | Text normalization | `normalize_amc_name()` | — |

---

## Notebooks

| Notebook | Phase | Status |
|---|---|---|
| `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb` | Index | Exists |
| `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb` | 1A | Exists |
| `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb` | 1B | Exists |

**Missing notebooks** (required by AGENTS.md §12):
- No agent pipeline inspection notebook
- No run-audit notebook

---

## Tests

| File | Tests | Coverage |
|---|---|---|
| `tests/test_mutual_fund_ingestion.py` | ~38 | Phase 1A/1B: registry, profiling, artifacts, CLI |
| `tests/test_agent.py` | ~47 | Agent unit: config, parsers, validation, discovery, relevance |
| `tests/test_agent_db.py` | ~22 | DB integration: init-db, ingestion run, upserts, fixture e2e |
| `tests/test_amfi_disclosure.py` | 11 | AMFI disclosure prototype |
| `tests/test_smoke.py` | 3 | Live smoke: AMFI reachability, NAV discovery, raw file retention |

**Fixtures:**

| Path | Purpose |
|---|---|
| `tests/fixtures/provider_static.html` | Phase 1B profiling |
| `tests/fixtures/amfi_members.html` | AMFI member list |
| `tests/fixtures/amfi_member_detail.html` | AMFI member detail |
| `tests/fixtures/amfi_portfolio.html` | AMFI portfolio page |
| `tests/fixtures/amc_portfolio.html` | AMC portfolio landing |
| `tests/fixtures/amfi_seed_page.html` | Agent seed page (R001) |
| `tests/fixtures/amc_disclosure_page.html` | Agent disclosure page (R002) |
| `tests/fixtures/data/nav_all_schemes.txt` | NAV text fixture |
| `tests/fixtures/data/scheme_master.csv` | Scheme master fixture |
| `tests/fixtures/data/portfolio_sample.xlsx` | Portfolio Excel fixture |

---

## Configs

| File | Purpose |
|---|---|
| `configs/amc_sources.yaml` | 53 AMC entries + AMFI + SEBI reference entries |

---

## Output Directories

| Directory | Produced by | Contents |
|---|---|---|
| `data/raw/mutual_funds/source_registry/` | Phase 1A | JSONL history + latest snapshot |
| `data/raw/mutual_funds/provider_profiles/` | Phase 1B | JSONL history + latest snapshot |
| `data/reports/mutual_funds/` | Phase 1A/1B | HTML reports, CSV summary |
| `data/debug/mutual_funds/provider_profiles/<name>/` | Phase 1B | Static/rendered HTML, screenshots, network logs |
| `data/raw/amfi/links/` | amfi_disclosure | AMFI portfolio link JSONL |
| `data/raw/amfi/files/` | amfi_disclosure | Raw files + JSON metadata sidecars |
| `data/tmp/mutual_funds/runtime/<run_id>/` | agent/extract.py | Temp download storage (not permanent) |

---

## Do Not Import Into Agent Pipeline

| Path | Reason |
|---|---|
| `mutual_fund_ingestion/amfi_disclosure/` | Legacy prototype — isolated by design |
| `docs/archive/legacy_experiments/` | Historical experiments only |

---

## Phase / Module Status

| Phase | Status | Frozen? | Key modules |
|---|---|---|---|
| Phase 1A | Complete | Yes | `profiling/source_discovery.py`, `profiling/source_registry.py` |
| Phase 1B | Complete | Yes | `profiling/profiler.py`, `profiling/browser.py`, `profiling/artifacts.py` |
| Task-URL Agent | Substantially complete | No | `agent/runner.py` and all agent/ submodules |
| Phase 2 | Not started | No | Spec: `docs/design/phase_2/` |
| Phase 3+ | Not started | No | — |

---

## Corrections vs. Original CODEBASE_MAP.md

| Item | Old claim | Verified reality |
|---|---|---|
| VLM invocation | `analyze_page()` never called | Called in runner.py lines 179–195 ✅ |
| portfolio.py | Column mapping broken | Header row detection fixed ✅ |
| amfi_disclosure status | Ambiguous | "LEGACY PROTOTYPE — do not import into agent pipeline" |
| Raw file retention | Files not permanently retained | Implemented in runner.py L001 ✅ |
| nav_html parser | Missing | `parse_nav_html` exists in nav.py ✅ |
| portfolio CSV parser | Missing | `parse_portfolio_csv` exists in portfolio.py ✅ |
| Logging format | No timestamps | Fixed in cli.py ✅ |
