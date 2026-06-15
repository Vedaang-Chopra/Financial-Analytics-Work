# Task-URL Driven Mutual Fund Ingestion Agent — Design Pack

This documentation pack defines the target system Codex should build: an end-to-end task-URL driven ingestion agent for Indian mutual fund data.

The user will provide one or more task URLs, initially AMFI URLs. The agent must discover relevant data sources from those URLs and linked AMC/provider pages, extract raw data, parse it, validate it, and load real rows into PostgreSQL.

The success criterion is PostgreSQL populated with useful mutual fund data, not a phase report or notebook.

## Recommended Codex Entry Point

Give Codex this instruction:

```text
Read this entire design pack first, especially docs/design/task_url_ingestion_agent/00_codex_entrypoint.md.
Then inspect the existing repository, including any Phase 1A/1B implementation, provider profiling code, crawler utilities, parser code, tests, database utilities, and notebooks.
Reuse existing code where compatible, but build the requested end-to-end task-URL driven ingestion agent.
Do not preserve the old phase-first architecture if it blocks the end-to-end goal.
The main deliverable is a runnable command that accepts task URLs and fills PostgreSQL tables with real data.
```

## File Map

```text
docs/design/task_url_ingestion_agent/
  00_codex_entrypoint.md
  01_product_goal_and_scope.md
  02_end_to_end_architecture.md
  03_agent_runtime_and_orchestration.md
  04_discovery_and_browser_agent.md
  05_vlm_integration.md
  06_data_sources_and_dataset_types.md
  07_postgresql_schema.md
  08_extraction_and_parser_design.md
  09_validation_quarantine_and_provenance.md
  10_storage_raw_file_policy.md
  11_cli_config_and_operations.md
  12_reuse_existing_phase_1a_1b.md
  13_testing_acceptance_criteria.md
  14_codex_build_plan.md
```
