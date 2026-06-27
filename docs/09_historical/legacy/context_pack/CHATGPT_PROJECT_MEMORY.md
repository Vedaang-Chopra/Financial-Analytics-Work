# ChatGPT Project Memory — Indian Mutual Fund Ingestion and Analytics

## Project Identity

This project is an agentic financial transparency system for Indian mutual fund data.

The goal is to collect public investor disclosure data from Indian mutual fund AMC/provider websites, structure it, validate it, store it in PostgreSQL, and eventually build analytics and agentic query tools over it.

This is not a generic chatbot and not a simple one-off scraper. It is a reproducible data ingestion and analysis system.

## Core Goal

Build a system that can answer questions such as:

- Which stocks are held by the most Indian mutual funds?
- Which stocks are being accumulated across multiple AMCs?
- Which fund managers agree or disagree on stocks/sectors?
- How much hidden overlap exists between user-selected mutual funds?
- Which sectors are fund managers increasing or reducing exposure to?
- How concentrated or diversified are funds at the underlying holdings level?

The system should support financial transparency and research. It should not present itself as investment advice.

## Data Source Decision

AMFI is not the primary source.

AMC/provider websites are the primary source because they publish actual investor documents such as portfolio disclosures, factsheets, statutory disclosures, TER documents, SID/KIM documents, fund manager information, and other investor disclosures.

AMFI can be used only as a reference or secondary index.

## Main Architecture

```text
AMC provider source registry
→ provider website profiling
→ persistent provider profiles
→ strategy resolution
→ document discovery
→ raw file download
→ document classification
→ parsing
→ staging tables
→ validation and quarantine
→ canonical PostgreSQL tables
→ visual QA reports
→ analytics and agentic query layer
```

## Strategy Hierarchy

Prefer deterministic methods first:

1. Static HTTP scraping
2. Network/API extraction
3. Deterministic Playwright browser automation
4. Local VLM/LLM-assisted recovery
5. Manual review

Local VLMs can be used, but only as fallback/recovery for difficult UI cases or ambiguous parser/selector failures.

## Phase Plan

Phase 1: Provider website profiling  
Phase 1.5: Strategy resolution for manual-review/unknown providers  
Phase 2: Raw document discovery and download  
Phase 3: Document classification  
Phase 4: Excel-first parser into staging tables  
Phase 5: PostgreSQL schema and canonical loader  
Phase 6: Validation, quarantine, and data quality  
Phase 7: Visual QA dashboard/reporting  
Phase 8: Agentic recovery layer using local VLM/LLM where needed  
Phase 9: Analytics agent over PostgreSQL

## Implementation Philosophy

Build incrementally. Do not implement everything at once.

Each phase must produce:

1. machine-readable artifacts
2. human-readable reports
3. quantifiable metrics
4. debug/failure artifacts
5. a simple Jupyter notebook to understand and test what was built

## Codex/Coding-Agent Rules

Before implementation, Codex should read the project docs and audit the existing codebase.

Codex should:

- reuse existing code where sensible
- not start from scratch blindly
- not create monolithic scrapers
- implement one phase at a time
- preserve raw files
- keep provider website knowledge persistent
- add reports and notebooks at the end of every phase
- avoid financial advice language

## Status Update — 2026-06-23

125/125 tests pass (+4 from last update). Full documentation audit completed. Key additions:

- Documentation audit: created docs/agent_context/ (9 files), docs/historical/ (3 files)
- plans/ACTIVE_EXECUTION_PLAN.md, plans/MICROTASK_BATCHES.md created
- 25 task statuses updated to "complete" in TASKS_FULL_SYSTEM_MICRO_PLAN.md
- Conflicts resolved: VLM IS wired (runner.py:179-195), portfolio fix confirmed, raw retention confirmed
- docs/session_state.md is stale (R003/R004 blocker resolved) — use docs/agent_context/08_session_handoff_template.md
- Next: Batch B (documentation cleanup), then Batch E (validation coverage), then Phase 2

See: docs/agent_context/01_current_system_state.md

## Status Update — 2026-06-22

121/121 tests pass (+33 from last update). Epic R (fixture tests) completed. Key additions:

- R003/R004: Fixture-based end-to-end tests for seed page discovery and NAV file upsert
- Epic E: Logging observability (link count, parser results, validation counts, retry queue, run completion)
- Epic S: Smoke tests (AMFI reachability, NAV discovery)
- F002/F003: Schema tests for nav_history composite index and amc unique constraint
- Parser router: Added ('nav_history','txt') routes for .txt NAV files
- discovery.py: Removed 'Download' from RELEVANCE_KEYWORDS[high] to fix false relevance
- runner.py: Added classify_dataset() for file URLs (was returning generic 'relevant')
- db.py: Added unique index on nav_history for SQLite-compatible ON CONFLICT upsert

See: docs/session_state.md (note: stale — R003/R004 blocker resolved)

## Status Update — 2026-06-22

Full audit completed. 125/125 tests pass. Key findings:

- Phase 1A/1B: complete and frozen
- Task-URL Agent: orchestration loop complete with DB persistence
- runner.py writes to all 17 tables (prior note that it did not was incorrect)
- portfolio.py column mapping bug FIXED (TASK-P001) - header row detection works for real AMFI Excel files
- VLM is wired and invoked for low-confidence pages (TASK-K004) - TASK-K005 tests verify the invocation
- retry-failed CLI crashes without --run-id (TASK-D001 - FIXED)
- 5 root-level .db files not in .gitignore (TASK-A001 - FIXED, patterns exist)
- pika removed from requirements.txt (TASK-A002 - FIXED)
- logging format fixed with timestamps (TASK-D002 - FIXED)
- Portfolio CSV parser added (parse_portfolio_csv)
- NAV HTML parser implemented (parse_nav_html, TASK-N003)
- RAW file retention implemented (move to raw_dir, TASK-L001)
- All 25 Epic A-K tasks marked complete; Epic L-N, P-Q, R-T pending
See: plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md

## Current Status

Phase 1 design documents were created. The user later indicated Phase 1 has been completed or is in progress.

A Phase 1 review notebook was requested to inspect the provider profiling implementation.

Because many providers may be marked manual review, a Phase 1.5 strategy-resolution step was designed before moving to Phase 2.

## Immediate Next Step

If Phase 1 has completed and many providers are marked `manual_review`, `unknown`, or `vlm_required`, implement Phase 1.5 before Phase 2.

If most providers have concrete strategies (`static_html`, `network_api`, or `playwright`), proceed to Phase 2 raw document discovery/download using persisted provider profiles.
