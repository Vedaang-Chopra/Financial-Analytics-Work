# System Architecture Memory

## Main Pipeline

```text
AMC source registry
→ Provider profiling
→ Provider strategy resolution
→ Document discovery
→ Raw file download
→ Document classification
→ Parsing
→ Staging tables
→ Validation and quarantine
→ Canonical PostgreSQL tables
→ Visual QA reports
→ Agentic analytics
```

## Core Modules

### Source Registry

A structured registry of AMC provider URLs, suggested at `configs/amc_sources.yaml`.

Fields: amc_name, seed_url, enabled, source_type, expected_document_types, notes.

### Provider Profiler

Inspects each AMC provider website and determines reachability, static links, direct downloads, candidate pages, JavaScript requirement, Playwright requirement, and VLM/manual review need.

### Strategy Resolver

Used after Phase 1 if providers remain unresolved. Converts ambiguous providers into static_html, network_api, playwright, vlm_required, failed_blocked, or manual_review_final.

### Discovery Engine

Finds documents after strategy is known: portfolio disclosures, factsheets, statutory disclosures, TER documents, SID/KIM documents, PDFs, Excels, CSVs, ZIPs.

### Download Manager

Downloads raw files with deterministic sanitized names, hash-based deduplication, sidecar metadata JSON, retry/backoff, polite crawling, and skip-existing behavior.

### Document Classifier

Classifies downloaded documents before parsing into portfolio_disclosure, factsheet, statutory_disclosure, ter, sid, kim, notice, form, or unknown.

### Parser Layer

Parses supported documents. Priority: Excel/XLSX, CSV, PDFs, ZIP bundles. Initial parser should be Excel-first.

### Staging Layer

Raw parsed rows should first enter staging and preserve source file, sheet name, raw columns, extracted fields, parser confidence, and parse run ID.

### Validation Layer

Checks NAV percentage sums, ISIN format, security name presence, numeric fields, date consistency, duplicate rows, and fund name mapping.

### Canonical PostgreSQL Loader

Loads validated rows into canonical tables: amcs, funds, documents, portfolio_holdings, sector_allocations, crawl_runs, downloaded_files, parse_runs, validation_results, quarantine_rows.

### Visual QA

Every phase must generate inspectable reports.

### Agentic Recovery Layer

Uses local VLM/LLM only when deterministic systems fail. Inputs include screenshot, HTML snapshot, rendered DOM, accessibility tree, network logs, parser error, and file preview. Outputs include recommended strategy, browser action, selector suggestion, parser mapping, or failure classification.

### Analytics Agent

Later phase only. Should answer questions using PostgreSQL-backed tools like query_holdings, compute_consensus_stocks, compute_fund_overlap, compute_monthly_delta, and compute_sector_exposure.
