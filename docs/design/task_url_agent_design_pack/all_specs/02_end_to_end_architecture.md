# 02 — End-to-End Architecture

## Target Pipeline

```text
task_urls
→ ingestion run manager
→ discovery crawler
→ source graph builder
→ extraction strategy selector
→ static HTTP extractor
→ Playwright/Chromium extractor
→ network/API interceptor
→ optional VLM-guided navigator
→ raw artifact collector
→ document/dataset classifier
→ parser router
→ staging loader
→ validation layer
→ canonical PostgreSQL loader
→ provenance, quarantine, and retry logging
```

The architecture may be modular internally, but the user-facing flow must be one command.

## Core Components

### 1. Ingestion Run Manager

Responsible for:

- creating run IDs,
- loading CLI/config,
- connecting to PostgreSQL,
- initializing tables/migrations,
- coordinating crawl/extraction/parser stages,
- collecting metrics,
- finalizing run status.

### 2. Task URL Manager

Responsible for:

- accepting one or more task URLs,
- normalizing URLs,
- storing initial seed/task records,
- enforcing crawl limits,
- passing URLs into the discovery queue.

### 3. Discovery Crawler

Responsible for:

- fetching pages,
- extracting links,
- identifying relevant pages,
- identifying external AMC/provider domains,
- discovering forms, buttons, downloads, APIs, and page tables,
- maintaining source graph.

### 4. Extraction Strategy Selector

Responsible for deciding whether to use:

- static HTTP,
- static HTML parsing,
- rendered Playwright DOM,
- network interception,
- browser form interaction,
- direct download,
- VLM-guided action.

The user does not configure this per site.

### 5. Raw Artifact Collector

Responsible for capturing:

- HTML snapshots,
- rendered HTML,
- screenshots,
- network logs,
- downloaded files,
- API responses,
- extracted tables,
- metadata sidecars.

### 6. Classifier

Classifies discovered artifacts into dataset/document types:

- amc_provider_list,
- scheme_master,
- nav_history,
- portfolio_disclosure,
- factsheet,
- ter,
- sid,
- kim,
- statutory_disclosure,
- aum_aaum,
- unknown.

### 7. Parser Router

Routes artifacts to parsers based on dataset type and file type.

Supported file types:

- HTML,
- CSV,
- XLS,
- XLSX,
- PDF,
- ZIP,
- JSON/API.

### 8. Database Loader

Loads parsed data first into staging, then validates and promotes trusted records to canonical tables.

### 9. Provenance/Quarantine/Retry System

Every decision and record should be traceable. Failures should be stored and retryable where appropriate.

## Design Principle

This is not a one-off scraper. It is an adaptive ingestion system. However, it must remain bounded, reproducible, and debuggable.
