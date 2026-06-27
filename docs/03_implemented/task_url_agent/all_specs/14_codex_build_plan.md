# 14 — Codex Build Plan

## Goal

Build the smallest working end-to-end system first, then expand coverage.

Do not get stuck designing every parser before the pipeline works.

## Step 1 — Repository Audit

Codex must inspect:

```text
AGENTS.md
CHATGPT_PROJECT_MEMORY.md
docs/project_memory/
docs/design/
existing ingestion modules
existing crawler/profile modules
existing parser modules
existing database modules
existing CLI modules
existing tests and notebooks
```

Then summarize what can be reused.

## Step 2 — Add/Adapt Database Schema

Implement tables from `07_postgresql_schema.md` using the repository's preferred migration approach.

Minimum required for first working run:

```text
ingestion_runs
task_urls
source_pages
discovered_links
dataset_candidates
raw_artifacts
amcs
schemes
nav_history
documents
staging_rows
validation_results
quarantine_rows
retry_queue
```

Add portfolio tables before or during portfolio parser work.

## Step 3 — Implement CLI Skeleton

Add:

```bash
python -m mutual_fund_ingestion run-agent
```

It should create an ingestion run, store task URLs, run a bounded crawl, and write source/discovery rows.

## Step 4 — Implement Static Discovery

Implement:

- HTTP fetch,
- HTML parsing,
- link extraction,
- table detection,
- file link detection,
- relevance scoring,
- dataset candidate detection,
- PostgreSQL persistence.

## Step 5 — Add Playwright Discovery

Implement browser fallback for pages requiring rendering.

Capture:

- screenshot,
- rendered HTML,
- links/buttons/forms,
- downloads,
- network logs.

## Step 6 — Add Raw Artifact Collector

Implement download/API/table artifact capture with checksum and metadata.

Respect raw file retention policy.

## Step 7 — Add First Parsers

Prioritize:

1. NAV parser.
2. AMC/provider list parser.
3. Excel/CSV portfolio parser.

Load to staging first, then canonical tables.

## Step 8 — Add Validation and Quarantine

Implement validation for NAV and portfolio rows.

Quarantine unsupported/failed rows.

## Step 9 — Add Optional VLM Backend

Implement VLM interface and fake backend first.

Then add local HTTP/Ollama-compatible backend if straightforward.

Keep VLM optional.

## Step 10 — Add Run Summary and Tests

At end of run, print concise metrics.

Add tests for:

- URL/link extraction,
- relevance scoring,
- parser routing,
- NAV parsing,
- Excel portfolio parsing fixture,
- DB inserts,
- quarantine handling,
- fake VLM decisions.

## Implementation Rule

Build vertically, not horizontally.

A good first milestone is:

```text
One AMFI task URL
→ discover source pages and links
→ identify NAV dataset candidate
→ extract/parse NAV rows
→ insert nav_history rows into PostgreSQL
→ log unsupported links for later
```

Then expand to:

```text
AMFI provider list
→ linked AMC disclosure page
→ downloaded Excel portfolio disclosure
→ parsed holdings
→ portfolio_holdings rows in PostgreSQL
```
