# Mutual Fund Ingestion System — Architecture

## Architecture Summary

The system is a provider-first ingestion pipeline with a reference-source
bootstrap layer.

Phase 1A builds a provenance-aware registry from curated entries, AMFI, and
optional SEBI evidence. Phase 1B profiles only enabled primary provider sites.

## Core Components

```text
1. Source Registry
2. Site Profiler
3. Strategy Router
4. Discovery Engine
5. Download Manager
6. Document Classifier
7. Parser Layer
8. Staging Layer
9. Validation Layer
10. Canonical PostgreSQL Loader
11. Visual QA Reporter
12. Agentic Recovery Layer
13. Analytics Agent
```

## 1. Source Registry

The source registry stores primary provider sources and secondary reference
indexes. It is refreshed by Phase 1A rather than maintained only by hand.

Suggested file:

```text
configs/amc_sources.yaml
```

Minimum fields:

```yaml
sources:
  - amc_name: "HDFC Mutual Fund"
    seed_url: "https://www.hdfcfund.com/statutory-disclosure/portfolio-disclosure"
    enabled: true
    source_role: "primary_provider"
    source_type: "provider_disclosure_page"
    expected_document_types:
      - portfolio_disclosure
      - factsheet
    discovered_from:
      - manual_curated
      - existing_config
    priority: primary
    manual_overrides:
      - seed_url
      - source_type
    notes: ""
```

Reference indexes use `source_role: reference_index` and `priority: secondary`.
They are used for discovery and corroboration and are excluded from provider
profiling.

Phase 1A writes candidate history, the latest merged snapshot, the YAML
registry, and a source-registry HTML report. Locked manual fields always win
during merges.

## 2. Site Profiler

The site profiler inspects each provider website and determines the best extraction strategy.

It should check:

- reachability
- status code
- static HTML links
- downloadable file links
- internal page links
- scripts and forms
- likely network/API calls
- whether JavaScript rendering is required
- whether Playwright is required
- whether VLM/manual review is likely required

Output:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl
```

## 3. Strategy Router

The strategy router chooses the best extraction method per provider.

Strategy order:

```text
static_html
network_api
playwright
vlm_required
manual_review
failed_blocked
```

For Phase 1, the router only assigns a detected strategy. Later phases will execute the known strategy.

## 4. Discovery Engine

The discovery engine finds document links.

Potential outputs:

- portfolio disclosure files
- factsheets
- statutory disclosure files
- TER files
- SID/KIM files
- ZIP bundles
- unknown investor documents

The discovery engine should preserve source context:

- AMC name
- seed URL
- source page URL
- link text
- file URL
- detected document type
- file extension
- discovery method
- crawl timestamp

## 5. Download Manager

The download manager retrieves raw documents.

Rules:

- preserve raw files exactly as downloaded
- use deterministic sanitized filenames
- avoid overwriting
- compute content hash
- skip known files unless forced
- write sidecar metadata JSON
- use polite rate limiting and retry with backoff

The download manager is not part of Phase 1.

## 6. Document Classifier

The classifier labels downloaded files.

Document types:

```text
portfolio_disclosure
factsheet
statutory_disclosure
ter
sid
kim
notice
form
unknown
```

Classification signals:

- filename
- URL path
- page context
- file extension
- first-page text
- Excel sheet names
- LLM fallback for ambiguous cases

The classifier is not part of Phase 1.

## 7. Parser Layer

The parser extracts tables from documents.

Initial priority:

1. Excel/XLSX
2. CSV
3. PDF tables
4. ZIP files containing the above

Parsing should be source-specific when necessary, but the canonical output should be common.

The parser is not part of Phase 1.

## 8. Staging Layer

Parsed data should first enter staging tables.

Do not insert directly into trusted canonical tables.

Staging rows preserve raw extracted values and parser confidence.

## 9. Validation Layer

Validation decides whether staging rows can enter canonical tables.

Examples:

- `% NAV` sum per scheme/month should be plausible
- ISIN should match expected format when present
- market value should be numeric
- security name should not be empty
- disclosure month should be known
- duplicate rows should be detected
- fund names should be mapped consistently

Invalid rows go to quarantine.

## 10. Canonical PostgreSQL Loader

Canonical tables should include:

```text
amcs
funds
documents
portfolio_holdings
sector_allocations
crawl_runs
downloaded_files
parse_runs
validation_results
quarantine_rows
```

PostgreSQL loading is not part of Phase 1.

## 11. Visual QA Reporter

The system should generate human-inspectable reports.

Examples:

- provider profile report
- crawl/download status report
- classification report
- parser preview report
- validation quality dashboard
- database summary report

For Phase 1, the required report is:

```text
data/reports/mutual_funds/provider_profile_report.html
```

or equivalent CSV/Markdown if HTML is not practical.

## 12. Agentic Recovery Layer

The agentic layer is a fallback, not the default.

Use it when deterministic systems fail.

Inputs:

- screenshot
- HTML snapshot
- accessibility tree
- network logs
- parser error
- file preview
- current goal

Possible outputs:

- browser action
- selector suggestion
- API endpoint candidate
- parser column mapping
- failure classification

Local VLMs can be used for browser/UI understanding.

LLMs can be used for schema mapping and failure repair.

## 13. Analytics Agent

Analytics comes after reliable ingestion.

The analytics agent should query PostgreSQL and call deterministic tools.

Possible tools:

- `query_holdings`
- `compute_consensus_stocks`
- `compute_fund_overlap`
- `compute_monthly_delta`
- `compute_sector_exposure`

This is out of scope until ingestion is reliable.

## Execution Principle

Every run should be reproducible.

Provider profiles should persist site knowledge.

Future runs should load known strategies first. If known strategies fail, the system should re-profile the site and update the provider profile.

## Observability

Every component should log:

- inputs
- outputs
- strategy used
- count of records processed
- failures
- artifact paths

Failures should produce debug artifacts, not just console errors.

## Out-of-Scope for Current Phase

Phase 1 excludes:

- full downloads
- parsing
- PostgreSQL loading
- analytics
- recommendation generation
- financial advice
