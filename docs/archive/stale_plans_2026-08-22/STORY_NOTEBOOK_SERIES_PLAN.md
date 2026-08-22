# Story Notebook Series Plan

**Status:** Planning complete; implementation not approved in this task  
**Created:** 2026-06-29  
**Validation baseline:** `./financial_env/bin/python -m pytest tests/ -q --tb=no` -> `145 passed, 3 skipped`

## Summary

The notebook series should explain the actual working system, not mirror old phase labels. The live codebase supports a story from source discovery through provider profiling, agent discovery, raw artifact download, parsing, validation, quarantine, and canonical database persistence. This plan keeps ingestion behavior unchanged and defines the notebook rewrite sequence needed to make that story inspectable.

Live facts used:

- Seven notebooks currently exist under `notebooks/mutual_fund_ingestion/`.
- The agent database schema exposes 17 SQLAlchemy tables in `mutual_fund_ingestion/agent/db.py`.
- Current artifacts exist for source registry, provider profiles, reports, debug files, and runtime downloads.
- Full tests currently report `145 passed, 3 skipped`.
- Some active docs still contained stale claims about notebook inventory, old test baselines, `runner.py` size, and `confirmed_disclosure_url`; live code and tests are authoritative.

## Current Notebook Audit

| Notebook | Current state | Decision | Reason |
|---|---|---|---|
| `00_system_checkpoint.ipynb` | Rewritten: 20 cells, 17 assertions, 9 stage blocks | Complete | First story notebook; system health and evidence index. |
| `01_phase_1_provider_profiling_review.ipynb` | 4 cells, index only, no assertions/stages | Replace with story index or archive after replacement | It is a thin compatibility index, not a review notebook. |
| `01a_phase_1_source_registry_review.ipynb` | 21 cells, no assertions/stages | Rewrite | Good source-registry topic, but it needs stage blocks, assertions, artifact checks, and clearer story framing. |
| `01b_phase_1_provider_profiling_review.ipynb` | 23 cells, no assertions/stages | Rewrite | Good provider-profile topic, but it needs strategy evidence, debug inspection, assertions, and failure sections. |
| `02_agent_pipeline_inspection.ipynb` | 23 cells, 3 assertions, 9 stage blocks | Keep and rewrite as canonical agent story | It already follows the intended shape and should become the main DB-backed ingestion-run notebook. |
| `02_task_url_ingestion_agent_inspection.ipynb` | 32 cells, no assertions/stages, stale `docs/design` reference | Merge/replace with pointer | It duplicates the canonical agent notebook and should not continue as a second divergent explanation. |
| `03_phase2_discovery_review.ipynb` | 3 cells, no assertions/stages | Rewrite | It should explain discovered pages, links, candidates, and run evidence, not just display a small result. |

## Proposed Story Notebook Series

### 00 - System Checkpoint

- **Filename:** `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb`
- **Question answered:** What exists, what passes, and what evidence can I inspect?
- **Story position:** Entry point and health dashboard.
- **Inputs:** project root, `configs/amc_sources.yaml`, current artifact directories, optional recorded pytest output.
- **Code/public APIs used:** `mutual_fund_ingestion.cli.build_parser`, `mutual_fund_ingestion.load_registry`, `mutual_fund_ingestion.agent.db.Base`.
- **Expected outputs:** DataFrames for CLI commands, DB tables, artifact existence, notebook inventory.
- **DataFrames/tables shown:** CLI command inventory, database table list, artifact path status, notebook status.
- **DB tables inspected:** schema table names only.
- **Artifacts inspected:** `source_registry.latest.json`, `provider_profiles.latest.json`, report CSV/HTML, runtime raw/temp directories.
- **Assertions included:** table count is 17; required CLI commands exist; registry has entries; required notebooks are present.
- **Failure/debug section:** missing artifact paths, missing database dependency, stale or missing notebooks.
- **Live network required:** no.
- **Offline from existing artifacts:** yes.
- **Visual result:** a compact dashboard showing system readiness and known gaps.

### 01 - Source Registry Story

- **Filename:** rewrite `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb`
- **Question answered:** How does the system represent AMC/provider/reference sources?
- **Story position:** Source truth and provenance.
- **Inputs:** `configs/amc_sources.yaml`, `data/raw/mutual_funds/source_registry/`.
- **Code/public APIs used:** `load_registry`, `SourceRegistryEntry`, `merge_source_candidates`, `calculate_source_registry_metrics`.
- **CLI mapped:** `python -m mutual_fund_ingestion bootstrap-sources --dry-run --no-reference-network`.
- **Expected outputs:** source registry DataFrame, provenance distribution, source-role distribution, unresolved-source table.
- **DataFrames/tables shown:** registry entries, candidate provenance, manual overrides, reference index rows.
- **DB tables inspected:** none.
- **Artifacts inspected:** `source_registry.latest.json`, `source_registry_candidates.jsonl`, `source_registry_report.html`.
- **Assertions included:** enabled primary providers exist; AMFI/SEBI are reference entries; artifact row count is consistent with registry fields.
- **Failure/debug section:** missing config, missing latest artifact, unresolved provider rows.
- **Live network required:** optional only for reference refresh.
- **Offline from existing artifacts:** yes.
- **Visual result:** a table-backed explanation of provider-first source truth.

### 02 - Provider Profile Story

- **Filename:** rewrite `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb`
- **Question answered:** How are provider websites profiled and which document links were found?
- **Story position:** Provider website evidence and strategy selection.
- **Inputs:** source registry entries, provider profile artifacts, profile reports.
- **Code/public APIs used:** `load_sources`, `load_latest_profiles`, `ProviderProfile`, `calculate_metrics`.
- **CLI mapped:** `python -m mutual_fund_ingestion profile-providers --limit 3 --no-browser`.
- **Expected outputs:** profile status table, strategy distribution, candidate link table, debug artifact table.
- **DataFrames/tables shown:** profile summary, strategies, candidate links, file/document hints, debug artifact paths.
- **DB tables inspected:** none.
- **Artifacts inspected:** `provider_profiles.latest.json`, `provider_profile_summary.csv`, provider debug directories.
- **Assertions included:** latest profiles load; each profile has status/strategy fields; candidate-link counts match profile fields.
- **Failure/debug section:** failed profiles, manual review cases, missing debug evidence.
- **Live network required:** optional bounded profiling run.
- **Offline from existing artifacts:** yes.
- **Visual result:** provider-by-provider evidence and unresolved cases.

### 03 - Discovery and Candidate Story

- **Filename:** rewrite `notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb`
- **Question answered:** Given a provider URL, what pages and candidate document links did the agent discover?
- **Story position:** Agent crawl and candidate selection.
- **Inputs:** database URL, run ID, optional existing run artifacts.
- **Code/public APIs used:** `IngestionRunner` only for optional bounded run, `get_session_maker`, SQLAlchemy DB models.
- **CLI mapped:** `run-agent --max-pages 5 --max-files 0/1 --dry-run` and `inspect-run`.
- **Expected outputs:** DataFrames for run summary, task URLs, source pages, discovered links, dataset candidates, retry rows.
- **DataFrames/tables shown:** `ingestion_runs`, `task_urls`, `source_pages`, `discovered_links`, `dataset_candidates`, `retry_queue`.
- **DB tables inspected:** `ingestion_runs`, `task_urls`, `source_pages`, `discovered_links`, `dataset_candidates`, `retry_queue`.
- **Artifacts inspected:** runtime debug screenshots/logs if present.
- **Assertions included:** selected run exists; run has source pages or retry rows; candidates have recognized or explicitly unknown dataset types.
- **Failure/debug section:** HTTP failures, empty candidate sets, retry queue rows.
- **Live network required:** optional bounded run only.
- **Offline from existing artifacts:** yes, if a prior run exists.
- **Visual result:** crawl trail from seed URL to candidate document links.

### 04 - Raw Artifact Download Story

- **Filename:** create `notebooks/mutual_fund_ingestion/04_raw_artifact_download_story.ipynb`
- **Question answered:** Did one raw document download, and what metadata proves it?
- **Story position:** Candidate link to retained raw file.
- **Inputs:** database URL, run ID with a downloaded or attempted artifact, runtime raw/temp directories.
- **Code/public APIs used:** `IngestionRunner` only for optional bounded run; DB models for inspection.
- **CLI mapped:** `run-agent --max-pages 10 --max-files 1 --keep-raw-files`.
- **Expected outputs:** raw artifact table, checksum/size table, retained path checks.
- **DataFrames/tables shown:** `raw_artifacts`, joined `dataset_candidates`, run summary.
- **DB tables inspected:** `raw_artifacts`, `dataset_candidates`, `ingestion_runs`.
- **Artifacts inspected:** `data/raw/mutual_funds/runtime/`, `data/tmp/mutual_funds/runtime/`, retained files and debug files.
- **Assertions included:** at least one candidate reached download status; downloaded artifacts have checksums; retained paths exist when `retained=True`.
- **Failure/debug section:** failed downloads, oversized files, missing retained paths, content-type mismatch.
- **Live network required:** optional bounded run.
- **Offline from existing artifacts:** yes, if prior artifacts exist.
- **Visual result:** proof of one raw file and its metadata lineage.

### 05 - Parse, Validate, and Load Story

- **Filename:** create `notebooks/mutual_fund_ingestion/05_parse_validate_load_story.ipynb`
- **Question answered:** How does downloaded data become parsed rows, validation results, quarantine, and canonical DB records?
- **Story position:** Raw artifact to structured database state.
- **Inputs:** existing fixture or retained artifact, database URL/run ID, parser metadata.
- **Code/public APIs used:** `parse_file`, `validate_and_filter_records`, `get_session_maker`, DB models.
- **CLI mapped:** `run-agent` on a known fixture or retained artifact.
- **Expected outputs:** parsed records, staging rows, validation results, quarantine rows, canonical table counts.
- **DataFrames/tables shown:** parsed records, `staging_rows`, `validation_results`, `quarantine_rows`, canonical tables.
- **DB tables inspected:** `staging_rows`, `validation_results`, `quarantine_rows`, `amcs`, `schemes`, `nav_history`, `documents`, `instruments`, `portfolio_snapshots`, `portfolio_holdings`.
- **Artifacts inspected:** retained raw file and parser metadata.
- **Assertions included:** parser returns a `ParserResult`; staging rows preserve raw JSON; valid rows land in canonical tables or invalid rows land in quarantine.
- **Failure/debug section:** no parser, parse warnings, validation errors, quarantine reasons.
- **Live network required:** no when run from fixture/existing artifact.
- **Offline from existing artifacts:** yes.
- **Visual result:** row lifecycle from raw file to DB persistence.

## Required Notebook Standards

Every retained notebook must:

- Use public entry points where available.
- Avoid duplicating production logic in notebook cells.
- Keep live network calls bounded, optional, and off by default.
- Prefer existing artifacts or small controlled runs.
- Include at least three assertions.
- Include stage blocks and short explanatory markdown.
- Include artifact or DB inspection where relevant.
- Include a failure/debug section.
- End with a "what this proves / what this does not prove" section.
- Avoid analytics, buy/sell language, personalized investment recommendations, and Phase 3/4 feature implementation.

## Gaps Found

The notebooks can be written today with existing APIs, but DB/artifact inspection would be cleaner with small public helpers. Do not implement these helpers until a microtask explicitly approves them.

| Helper | Smallest public API | Why needed |
|---|---|---|
| `mutual_fund_ingestion/agent/inspection.py` | `summarize_run(session, run_id: str) -> dict[str, object]`; `load_run_tables(session, run_id: str) -> dict[str, Any]` | Prevents notebooks from duplicating SQLAlchemy queries across run/candidate/artifact tables. |
| `mutual_fund_ingestion/profiling/inspection.py` | `load_source_registry_summary(config_path: Path, artifact_dir: Path) -> dict[str, Any]`; `load_provider_profile_summary(profile_path: Path, report_csv: Path) -> dict[str, Any]` | Standardizes artifact-to-table summaries for source and profile notebooks. |
| `mutual_fund_ingestion/agent/artifact_inspection.py` | `inspect_raw_artifact(path: Path) -> dict[str, object]` | Centralizes checksum/path/sidecar checks for raw artifact notebooks. |

## Execution Task Breakdown

1. **STORY-NB-001 - Current notebook audit and batch task setup**
   - Touch: `STORY_NOTEBOOK_SERIES_TASKS.md`, `MICROTASK_SPEC.md`, status docs.
   - Validate: pytest, notebook inventory, stale-doc search.

2. **STORY-NB-002 - Public inspection helper decision**
   - Touch: at most one helper module plus focused tests, only if approved.
   - Validate: targeted helper tests plus full pytest.

3. **STORY-NB-003 - Rewrite `00_system_checkpoint.ipynb`**
   - Touch: one notebook.
   - Validate: structural check and offline execution if tooling is available.

4. **STORY-NB-004 - Rewrite source registry notebook**
   - Touch: one notebook.
   - Validate: no production logic duplication, at least three assertions, artifact checks.

5. **STORY-NB-005 - Rewrite provider profile notebook**
   - Touch: one notebook.
   - Validate: profile artifact loads, candidate/debug tables, assertions.

6. **STORY-NB-006 - Rewrite discovery/candidate notebook**
   - Touch: one notebook.
   - Validate: DB/run inspection from existing artifacts or bounded optional run.

7. **STORY-NB-007 - Create raw artifact download notebook**
   - Touch: one notebook.
   - Validate: checksum/path assertions from existing or bounded run artifacts.

8. **STORY-NB-008 - Create parse/validate/load notebook**
   - Touch: one notebook.
   - Validate: parser/validation/DB inspection from fixture or existing artifact.

9. **STORY-NB-009 - Compatibility cleanup**
   - Touch: duplicate/index notebooks only after explicit approval.
   - Validate: old notebook names either point to canonical notebooks or are listed for archival.

10. **STORY-NB-010 - Final validation and docs handoff**
    - Touch: status/planning docs only.
    - Validate: full pytest, notebook structural inventory, stale-doc search.

## Final Recommendation

Build `00_system_checkpoint.ipynb` first, then source registry, provider profile, discovery/candidate, raw artifact download, and parse/validate/load. Keep old notebooks until the replacement notebooks exist. Convert `01_phase_1_provider_profiling_review.ipynb` and `02_task_url_ingestion_agent_inspection.ipynb` to pointers or archive them only after explicit approval.

The next executable microtask is `STORY-NB-001`: write the batch task file and keep notebook implementation stopped.
