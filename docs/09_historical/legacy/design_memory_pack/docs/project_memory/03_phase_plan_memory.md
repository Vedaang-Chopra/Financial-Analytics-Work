# Phase Plan Memory

## Phase 1 — Provider Website Profiling

Goal: Inspect each AMC/provider website and build persistent provider profiles.

Outputs: provider_profiles.jsonl, provider_profiles.latest.json, provider_profile_report.html, provider_profile_summary.csv, debug artifacts.

Does not download all files, parse documents, or load PostgreSQL.

Notebook: `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb`

## Phase 1.5 — Strategy Resolution

Goal: Resolve providers marked manual_review, unknown, or vlm_required.

Inputs: Phase 1 profiles and debug artifacts.

Outputs: provider_strategy_resolutions.jsonl, provider_profiles.resolved.latest.json, strategy resolution report.

Resolution classes: static_html, network_api, playwright, vlm_required, failed_blocked, manual_review_final.

Notebook: `notebooks/mutual_fund_ingestion/01_5_strategy_resolution_review.ipynb`

## Phase 2 — Raw Document Discovery and Download

Goal: Use resolved provider profiles to discover and download raw investor documents.

Outputs: discovered_documents.jsonl, raw files, metadata sidecars, download summary report.

Rule: Phase 2 should not rediscover websites from scratch. It should use known strategies and re-profile only on failure.

## Phase 3 — Document Classification

Goal: Classify downloaded files before parsing.

Outputs: document_classification.jsonl and classification report.

## Phase 4 — Excel-First Parser

Goal: Parse Excel/CSV portfolio disclosure documents into staging rows.

Outputs: staging_portfolio_rows, parse_runs, parse_errors, parser preview report.

Do not parse all PDFs initially.

## Phase 5 — PostgreSQL Schema and Loader

Goal: Create/update PostgreSQL schema and load validated/staged data.

Tables include amcs, funds, documents, portfolio_holdings, sector_allocations, crawl_runs, downloaded_files, parse_runs, validation_results, and quarantine_rows.

## Phase 6 — Validation and Data Quality

Goal: Prevent garbage from entering trusted canonical tables.

Checks include NAV percentage plausibility, ISIN sanity, non-empty security names, numeric market values, date consistency, duplicate handling, and fund mapping quality.

## Phase 7 — Visual QA Dashboard

Goal: Create human-readable inspection views for crawl status, downloaded files, document types, parse status, sample holdings, top securities, fund overlap, and sector allocation.

## Phase 8 — Agentic Recovery Layer

Goal: Use local VLM/LLM to recover failed navigation or parsing cases.

## Phase 9 — Analytics Agent

Goal: Query structured PostgreSQL data for consensus stocks, fund overlap, allocation deltas, sector exposure, and concentration metrics.
