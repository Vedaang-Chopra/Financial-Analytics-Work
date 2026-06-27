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

## Current Status

Phase 1 design documents were created. The user later indicated Phase 1 has been completed or is in progress.

A Phase 1 review notebook was requested to inspect the provider profiling implementation.

Because many providers may be marked manual review, a Phase 1.5 strategy-resolution step was designed before moving to Phase 2.

## Immediate Next Step

If Phase 1 has completed and many providers are marked `manual_review`, `unknown`, or `vlm_required`, implement Phase 1.5 before Phase 2.

If most providers have concrete strategies (`static_html`, `network_api`, or `playwright`), proceed to Phase 2 raw document discovery/download using persisted provider profiles.
