# docs/ Directory — Complete Documentation Index

## Purpose

This file is the authoritative guide to every document in the `docs/` directory. It describes what each file contains, its purpose, how it relates to other documents, and which files should be read by whom.

---

## Top-Level Files

### `docs/ai_context/CODEBASE_MAP.md`

**What it is:** The module ownership map. Lists every Python module in the repository with its layer classification, responsibility, and public API surface.

**Purpose:** Referenced by `AGENTS.md` §1 and §3. Every AI coding agent must read this before touching any module.

**Contents:**
- Module ownership table (35+ entries covering Phase 1A/1B, agent, utils)
- Layer model assignments (Layer 2 = CLI, Layer 3 = orchestration, Layer 4 = core logic, Layer 5 = schemas/utilities)
- Notebook index with phase labels
- Config file registry
- Test file index
- Output directory inventory
- Phase status tracker (Phase 1A ✅, Phase 1B ✅, Task-URL Agent ✅, Phase 2+ ⏳)
- Import guidance for future phases
- Off-limits module warnings

**When to read:** Before any code change. Updated whenever module structure changes.

---

### `docs/amfi_disclosure_investigation.md`

**What it is:** A field investigation report on AMFI's portfolio disclosure page, written before implementing the `amfi_disclosure/` module.

**Purpose:** Documents the discovery that AMFI's disclosure page uses JavaScript-driven selectors, that a prior Selenium attempt failed, and the recommended strategy for Phase 2.

**Contents:**
- Source URLs (current and historical)
- Confirmed behavior (dynamic disclosure selector requiring Playwright)
- Implemented discovery strategy (static HTML → Playwright fallback)
- Limitations (AMC website structure is not uniform, AMC names/dates best-effort)
- Recommended next phase

**When to read:** Before implementing Phase 2 (raw document download). Relevant to anyone adding AMFI crawl logic.

---

## `docs/design/mutual_fund_project_memory_pack/`

**What it is:** Memory/context files capturing decisions from the first major planning conversation. These are continuity files, not implementation specs.

**Purpose:** Provide persistent context for AI coding agents. When an agent resumes work after a gap, these files tell it what was already decided.

**Files:**

| File | Purpose |
|---|---|
| `README_PROJECT_MEMORY_PACK.md` | How to use with ChatGPT/Codex — paste `CHATGPT_PROJECT_MEMORY.md` into the AI prompt. Also paste phase plan and status summaries. |
| `CHATGPT_PROJECT_MEMORY.md` | High-level project summary, key decisions, phase plan, current status |
| `docs/project_memory/00_project_summary.md` | Project goal, source philosophy, AMFI/provider role, long-term analytics targets |
| `docs/project_memory/01_conversation_decisions.md` | All named decisions made: provider-first principle, deterministic-first philosophy, AMFI as secondary index, phase strategy, VLM as fallback, no over-engineering |
| `docs/project_memory/02_system_architecture_memory.md` | Architecture overview, 13 component descriptions, execution principle, observability requirements |
| `docs/project_memory/03_phase_plan_memory.md` | All phases: Phase 1A (source registry), Phase 1B (provider profiling), Phase 1.5 (strategy resolution), Phase 2 (raw download), Phase 3 (classification), Phase 4 (parsing/staging), Phase 5+ (validation/canonical/analytics) |
| `docs/project_memory/04_current_status_and_next_steps.md` | What was done, what was verified, what remains |
| `docs/project_memory/05_codex_working_instructions.md` | Instructions for AI coding agents: read files first, audit codebase, implement one phase at a time, produce artifacts, write tests |
| `docs/project_memory/06_data_sources_and_provider_strategy.md` | Data source breakdown by type: NAV, portfolio, factsheet, SID/KIM, statutory disclosure, TER. Source type per data category. |
| `docs/project_memory/07_notebook_and_testing_policy.md` | Notebook purpose (inspection/debugging only, no production logic), testing requirements per phase |
| `docs/project_memory/08_phase_1_5_strategy_resolution_memory.md` | Phase 1.5 scope: load provider profiles, try known strategy first, re-profile on failure, detect new dataset types, decide on parse strategy |

**When to read:** When starting a new session. Paste the key memory files into the AI prompt for continuity.

---

## `docs/design/phase_1/`

**What it is:** Phase 1 design specifications — source registry bootstrap (Phase 1A) and provider profiling (Phase 1B). These define what was built in the initial implementation.

**Files:**

| File | Purpose |
|---|---|
| `00_project_overview.md` | **Start here for Phase 1 context.** Project goal (AMC-provider-first ingestion), why provider websites over AMFI, system philosophy (deterministic before agentic), what makes this different from a scraper (persistent provider profiles), phase strategy, Phase 1 non-goals, long-term target command |
| `01_system_architecture.md` | Full 13-component architecture: Source Registry, Site Profiler, Strategy Router, Discovery Engine, Download Manager, Document Classifier, Parser Layer, Staging Layer, Validation Layer, Canonical PostgreSQL Loader, Visual QA Reporter, Agentic Recovery Layer, Analytics Agent. Strategy order for extraction. |
| `02_existing_codebase_audit.md` | Audit specification for Phase 1. Must inspect repository before implementing. Outputs audit report to `docs/design/phase_1/generated/`. Reuse policy (simple, readable, compatible, testable). |
| `03_data_artifacts_and_storage.md` | Where Phase 1 outputs live: `data/raw/mutual_funds/source_registry/` and `data/raw/mutual_funds/provider_profiles/`. JSONL history + latest snapshot pattern. Report outputs: HTML + CSV. Debug artifacts per provider. Raw file handling. |
| `04_provider_profile_schema.md` | ProviderProfile schema — all fields, types, default values, example JSON. Strategy enum: static_html, network_api, playwright, vlm_required, manual_review, failed_blocked. |
| `generated/existing_codebase_audit_report.md` | Audit report produced during Phase 1 implementation. Lists reusable and non-reusable code, existing sample data, missing dependencies, implementation risks. |
| `phases/phase_1_provider_profiling.md` | Detailed Phase 1B spec. Covers static HTML profiling, Playwright fallback, strategy detection logic, artifact persistence, debug evidence for failures. |

**When to read:** Before implementing Phase 1A or Phase 1B. `00_project_overview.md` and `01_system_architecture.md` are the primary reference.

---

## `docs/design/phase_2/`

**What it is:** Phase 2 design specs for raw document discovery and download. Phase 2 is not yet implemented.

**Files:**

| File | Purpose |
|---|---|
| `README_PHASE_2_CODEX_PACK.md` | Entry point for Phase 2. Lists all Phase 2 files and recommended reading order. References 4 spec files under `docs/design/mutual_fund_ingestion/phases/`. |
| `prompts/codex_phase_2_raw_document_download_prompt.md` | Pre-written Codex prompt for Phase 2 implementation. Tells Codex what to read, what to audit, what to implement. |
| `docs/design/mutual_fund_ingestion/phases/02_phase_2_artifact_contract.md` | What Phase 2 must produce: machine-readable artifact contract, human-readable report, quantifiable metrics, failure/debug artifacts |
| `docs/design/mutual_fund_ingestion/phases/02_phase_2_raw_document_discovery_and_download.md` | Discovery strategy: AMFI → linked AMC pages → disclosure pages → raw files. Download manager requirements: rate limiting, retry with backoff, deterministic filenames, content hash, skip-known files, sidecar metadata |
| `docs/design/mutual_fund_ingestion/phases/02_phase_2_sample_values_and_amfi_reference.md` | Real AMFI disclosure data samples. Link patterns, file naming conventions, date formats, expected AMC name variations |
| `docs/design/mutual_fund_ingestion/phases/02_phase_2_testing_and_acceptance.md` | Phase 2 acceptance criteria: bounded run completes without error, links discovered are relevant, files downloaded with correct hash, skip-known-files works, debug artifacts on failure |

**When to read:** Before implementing Phase 2. Read the design pack README first for navigation.

---

## `docs/design/task_url_agent_design_pack/`

**What it is:** The complete design specification for the Task-URL Driven Ingestion Agent. The agent accepts task URLs and produces PostgreSQL rows. This is the primary design reference for the current implementation.

**Package files:**

| File | Purpose |
|---|---|
| `README.md` | Design pack navigation. Lists all 14 spec files. Provides Codex entry point instruction. |
| `implementation_report.md` | **The authoritative implementation reference.** Covers architecture, all module references, database schema (all 17 tables with SQL), CLI commands, data flow, parser system, validation/quarantine, VLM integration, testing (50 passing tests), usage examples, and build status checklist. ~830 lines. |
| `all_specs/00_codex_entrypoint.md` | **Start here.** Build target (task-URL agent), primary success criterion (real PostgreSQL rows), main command template, 12-step required behavior list, existing codebase inspection requirements, non-goals, data priority order (AMC → schemes → NAV → portfolio → factsheet → other disclosures) |
| `all_specs/01_product_goal_and_scope.md` | User mental model (URL in → rows out), source framing (no rigid primary/secondary terminology, store provenance), data domains (AMC, schemes, NAV, portfolio, factsheet, TER, SID/KIM, statutory disclosures, AUM/AAUM), success criteria |
| `all_specs/02_end_to_end_architecture.md` | Target pipeline (task_urls → ingestion run manager → discovery crawler → extraction strategy selector → static/P&W/VLM extractors → raw artifact collector → classifier → parser router → staging → validation → canonical → quarantine), 9 core components with responsibilities, design principle (not a one-off scraper) |
| `all_specs/03_agent_runtime_and_orchestration.md` | Agent runtime behavior, phase coordination, CLI interface design, configuration management |
| `all_specs/04_discovery_and_browser_agent.md` | Discovery strategy: static HTML → Playwright → network/API → VLM → quarantine. Link extraction, relevance scoring, dataset classification. Playwright config (headless, viewport, navigation timeout, network blocking). VLM as last resort. |
| `all_specs/05_vlm_integration.md` | VLM integration: abstract interface with null backend (always succeeds), Ollama HTTP backend, prompt templates for page analysis (dataset type hint, file type hint, relevance decision, routing recommendation), when to invoke VLM, performance and cost considerations |
| `all_specs/06_data_sources_and_dataset_types.md` | Dataset type taxonomy: amc_list, scheme_master, nav_history, portfolio_disclosure, factsheet, ter, sid, kim, statutory_disclosure, aum_aaum, unknown. Source types: amfi_page, amc_provider_website, amc_disclosure_page, amc_api, amc_form_generated, direct_download. Dataset type → file type matrix. |
| `all_specs/07_postgresql_schema.md` | **The canonical database schema.** 17 tables with full CREATE TABLE statements: ingestion_runs, task_urls, source_pages, discovered_links, dataset_candidates, raw_artifacts, amcs, schemes, nav_history, documents, instruments, portfolio_snapshots, portfolio_holdings, staging_rows, validation_results, quarantine_rows, retry_queue. Indexes on key columns. |
| `all_specs/08_extraction_and_parser_design.md` | Parser system: parser router dispatches by (dataset_type, file_type). Supported types: text/nav_history, csv/nav_history, html/amc_list, html/scheme_master, xlsx/portfolio_disclosure, csv/portfolio_disclosure, html/factsheet, csv/factsheet. Parser output: dataset_type, rows, parse_errors, metadata. Per-parser field mappings. |
| `all_specs/09_validation_quarantine_and_provenance.md` | Validation rules per dataset type. NAV: scheme_name required, nav_value > 0, date valid. Portfolio: scheme_name + industry required, percentage_to_nav in 0–100. Quarantine: reason code, raw data JSON, retryable flag. Provenance: source_url and raw_artifact_id on every canonical row. |
| `all_specs/10_storage_raw_file_policy.md` | Raw file retention policy: delete after successful parse (configurable with --keep-raw-files), always keep failed parse files, SHA256 checksum for integrity, sidecar metadata JSON per artifact, max raw file size for retention (100 MB default) |
| `all_specs/11_cli_config_and_operations.md` | CLI specification: run-agent (task-url, database-url, use-browser, headless, use-vlm, vlm-endpoint, max-pages, max-depth, max-files, keep-raw-files, keep-failed-raw-files, dry-run, log-level, temp-dir), init-db, retry-failed, inspect-run, export-run-summary |
| `all_specs/12_reuse_existing_phase_1a_1b.md` | Reuse guidance: discovery/engine, browser/Playwright, HTTP session, URL utilities, file type detection, text normalization. What NOT to duplicate: phase-first pipeline, JSONL artifact outputs, HTML report generation. |
| `all_specs/13_testing_acceptance_criteria.md` | Testing requirements: schema creation tests, source discovery tests, parser routing tests, NAV parser tests (text + CSV fixtures), AMC HTML parser tests, portfolio parser tests (Excel + CSV), validation tests (valid, invalid, quarantine), provenance tests, end-to-end dry run with mock database |
| `all_specs/14_codex_build_plan.md` | **Implementation sequence.** 10-step build plan: (1) repo audit, (2) DB schema, (3) CLI skeleton, (4) static discovery, (5) Playwright discovery, (6) raw artifact collector, (7) first parsers (NAV, AMC, portfolio), (8) validation + quarantine, (9) optional VLM backend, (10) run summary + tests. Vertical build, not horizontal. First milestone: one URL → nav_history rows in PostgreSQL. |

**When to read:** All 14 spec files for the Task-URL Agent. Read `00_codex_entrypoint.md` first for the build target and success criterion. Read `14_codex_build_plan.md` for the implementation sequence.

---

## Relationship Between Document Groups

```
CHATGPT_PROJECT_MEMORY.md          ← Paste into every AI prompt for continuity
    ↓
docs/ai_context/CODEBASE_MAP.md   ← Read before any code change
    ↓
docs/design/phase_1/               ← Phase 1A/1B implementation reference
    ↓
docs/design/task_url_agent_design_pack/
    ├── README.md                  ← Navigation
    ├── 00_codex_entrypoint.md     ← Build target + success criterion
    ├── 01_product_goal_and_scope.md
    ├── 02_end_to_end_architecture.md
    ├── 03_agent_runtime_and_orchestration.md
    ├── 04_discovery_and_browser_agent.md
    ├── 05_vlm_integration.md
    ├── 06_data_sources_and_dataset_types.md
    ├── 07_postgresql_schema.md    ← All 17 DB table definitions
    ├── 08_extraction_and_parser_design.md
    ├── 09_validation_quarantine_and_provenance.md
    ├── 10_storage_raw_file_policy.md
    ├── 11_cli_config_and_operations.md
    ├── 12_reuse_existing_phase_1a_1b.md
    ├── 13_testing_acceptance_criteria.md
    ├── 14_codex_build_plan.md     ← Implementation sequence
    └── implementation_report.md   ← Completed implementation reference
```

---

## Reading Order by Role

**For a new AI coding agent working on this codebase:**
1. `CHATGPT_PROJECT_MEMORY.md` (paste into prompt)
2. `docs/ai_context/CODEBASE_MAP.md`
3. `docs/design/task_url_agent_design_pack/00_codex_entrypoint.md`
4. `docs/design/task_url_agent_design_pack/07_postgresql_schema.md`
5. `docs/design/task_url_agent_design_pack/14_codex_build_plan.md`
6. `docs/design/task_url_agent_design_pack/implementation_report.md` (to see what's already done)

**For Phase 1A/1B maintenance:**
1. `docs/design/phase_1/00_project_overview.md`
2. `docs/design/phase_1/01_system_architecture.md`
3. `docs/ai_context/CODEBASE_MAP.md`

**For Phase 2 implementation:**
1. `docs/design/phase_2/README_PHASE_2_CODEX_PACK.md`
2. `docs/design/phase_2/prompts/codex_phase_2_raw_document_download_prompt.md`
3. `docs/design/phase_2/docs/design/mutual_fund_ingestion/phases/02_phase_2_raw_document_discovery_and_download.md`
4. `docs/amfi_disclosure_investigation.md`

**For understanding data sources:**
1. `docs/design/task_url_agent_design_pack/all_specs/06_data_sources_and_dataset_types.md`
2. `docs/design/mutual_fund_project_memory_pack/docs/project_memory/06_data_sources_and_provider_strategy.md`

---

## Maintenance

This index must be updated whenever:
- A new document is added to `docs/`
- An existing document is moved, renamed, or replaced
- A new design pack directory is created
- A phase moves from "planned" to "implemented" in `CODEBASE_MAP.md`

Last updated: 2026-06-15 (Task-URL Agent implementation complete)
