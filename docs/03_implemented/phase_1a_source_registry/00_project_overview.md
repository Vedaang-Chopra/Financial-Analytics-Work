# Mutual Fund Ingestion System — Project Overview

## Project Goal

Build an AMC-provider-first ingestion system for Indian mutual fund public disclosure data.

The system should collect investor documents directly from Indian mutual fund provider websites, preserve the raw files, parse supported files into structured data, validate quality, and eventually load reliable data into PostgreSQL for analytics and agentic querying.

The final system should support questions such as:

- Which stocks are held by the most mutual funds?
- Which stocks are being accumulated across multiple AMCs?
- How much hidden overlap exists between two or more mutual funds?
- Which sectors are fund managers increasing exposure to?
- Which funds are concentrated or diversified at the underlying stock level?

The immediate goal is not analytics. The immediate goal is reliable data capture.

## Why AMC Provider Websites

AMFI can be used as a reference or discovery index, but it should not be the main dependency.

The actual investor documents are published on AMC/provider websites. These provider websites are the primary source for:

- portfolio disclosures
- factsheets
- statutory disclosures
- total expense ratio documents
- scheme information documents
- key information memoranda
- fund manager information
- other investor disclosures

Therefore, the ingestion system should start from a curated registry of AMC provider URLs.

## System Philosophy

This system should be deterministic first and agentic only where useful.

Use the simplest working method for each website:

1. Static scraping if links are present in HTML.
2. Network/API extraction if the website calls internal APIs.
3. Playwright if JavaScript rendering or UI interaction is required.
4. Local VLM/LLM fallback only when deterministic methods fail.
5. Manual review if automation fails.

A local VLM can be used later for browser recovery or UI understanding, but it should not be the default path.

## What Makes This System Different From a Scraper

A one-off scraper downloads files.

This system should maintain persistent knowledge about each provider website.

For every AMC website, the system should store:

- source URL
- whether static scraping works
- whether JavaScript is required
- known successful strategy
- known selectors or link patterns
- last successful crawl
- candidate document types
- failure reasons
- debug evidence

This allows the system to run reproducibly in future months without rediscovering the website from scratch.

## High-Level Pipeline

```text
AMFI / SEBI / curated source references
    ↓
Source registry bootstrap and merge
    ↓
Provider website profiling
    ↓
Persistent provider profiles
    ↓
Document discovery
    ↓
Raw file download
    ↓
Document classification
    ↓
Parsing into staging tables
    ↓
Validation and quarantine
    ↓
Canonical PostgreSQL tables
    ↓
Visual QA reports
    ↓
Analytics and agentic query layer
```

## Phase Strategy

Implementation should be phased.

Each phase must produce inspectable artifacts before moving to the next phase.

Every phase should have:

1. A machine-readable output.
2. A human-readable report.
3. Quantifiable metrics.
4. Failure artifacts.

This prevents silent failure and makes the system easy to debug with coding agents.

## Initial Phase

Phase 1 has two internal parts:

1. Phase 1A bootstraps or refreshes the source registry from existing curated
   entries plus AMFI and optional SEBI reference evidence.
2. Phase 1B profiles enabled primary provider websites from that registry.

AMFI and SEBI are reference indexes. Direct AMC/provider websites remain the
primary sources for investor documents.

Phase 1 does not download documents, parse holdings, load PostgreSQL, or build analytics.

It only builds knowledge of each AMC provider website.

The key output is a persistent provider profile for each AMC.

## Non-Goals for Phase 1

Phase 1 must not:

- parse Excel or PDF holdings
- normalize portfolio rows
- insert data into PostgreSQL
- build financial analytics
- build an investment recommendation system
- use VLM/LLM unless deterministic inspection fails
- create a full autonomous browser agent

## Long-Term Target

The long-term system should allow this workflow:

```bash
python -m mf_ingestion run --month latest
```

Expected outcome:

- provider profiles are loaded
- each AMC is crawled using its known strategy
- new investor documents are discovered
- raw files are downloaded
- files are classified
- supported files are parsed
- rows are validated
- structured data is loaded into PostgreSQL
- an ingestion QA report is generated
- unresolved failures are saved for agentic or human review
```

## Financial Disclaimer

This system is for public disclosure analytics and research.

It should not present itself as financial advice, investment advice, or a buy/sell recommendation engine.
