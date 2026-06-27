# Phase 2 — Document Discovery Tasks (TBD)
# Status: not yet specified
# Gate: Milestone 2 complete (≥145 tests, all Epics G–Q done)

## Status

Phase 2 tasks have not yet been written. They must be written from the Phase 2 spec before any implementation begins.

## Prerequisites

Before writing these tasks:
1. Read `docs/05_planned/phase_2_discovery/README_PHASE_2_CODEX_PACK.md`
2. Read all files in `docs/05_planned/phase_2_discovery/docs/design/mutual_fund_ingestion/phases/`
3. Complete `docs/04_in_progress/REFACTOR_runner.md` (runner.py refactor)
4. Confirm all Milestone 2 gate criteria met (SPRINT_CURRENT.md)

## Scope (from Phase 2 spec)

- Given Phase 1B provider profiles, discover actual disclosure documents
- Input: `data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json`
- Output: `data/raw/mutual_funds/links/` (JSONL), `data/raw/mutual_funds/files/` (raw + sidecars)
- Acceptance: 3+ AMCs traversed; 1+ Excel downloaded; HTML report; review notebook

## How to Proceed

1. Claude Code reads Phase 2 spec in full
2. Claude Code writes task decomposition into `docs/06_plans/active/BATCH_PHASE2_*.md`
3. Human approves
4. Pi executes tasks one at a time
