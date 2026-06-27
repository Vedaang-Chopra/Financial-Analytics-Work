# Provider Profile Schema

## Purpose

Provider profiles are the persistent website knowledge base.

They record how each AMC/provider website exposes investor documents and which extraction strategy should be used in future runs.

The system should not rediscover each website from scratch every time. It should load existing provider profiles, try the known strategy, and re-profile only when the known strategy fails.

## Storage Location

Primary Phase 1 output:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl
```

Latest compact snapshot:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
```

## Schema Version

Current schema version:

```text
provider_profile_v1
```

Each record must include `schema_version`.

## Required Fields

```json
{
  "schema_version": "provider_profile_v1",
  "run_id": "20260606_120000_ab12cd",
  "created_at": "2026-06-06T12:00:00Z",
  "amc_name": "HDFC Mutual Fund",
  "source_name": null,
  "seed_url": "https://www.hdfcfund.com/statutory-disclosure/portfolio-disclosure",
  "source_role": "primary_provider",
  "source_type": "provider_disclosure_page",
  "source_provenance": ["manual_curated", "existing_config"],
  "status": "success",
  "detected_strategy": "static_html",
  "strategy_confidence": "high",
  "requires_javascript": false,
  "static_links_found": 12,
  "rendered_links_found": 0,
  "download_links_found": 5,
  "candidate_document_links_found": 8,
  "file_types_found": ["pdf", "xlsx"],
  "document_type_hints": ["portfolio_disclosure"],
  "known_link_patterns": [],
  "known_selectors": {},
  "source_pages_examined": [],
  "candidate_links": [],
  "debug_artifacts": {},
  "failure_reason": null,
  "notes": ""
}
```

## Field Definitions

### `schema_version`

The provider profile schema version.

### `run_id`

Identifier for the profiling run.

### `created_at`

UTC timestamp.

### `amc_name`

Human-readable AMC/provider name.

### `seed_url`

Initial URL used for this provider.

### `status`

Allowed values:

```text
success
partial_success
failed
manual_review_required
```

### `detected_strategy`

Allowed values:

```text
static_html
network_api
playwright
vlm_required
manual_review
failed_blocked
unknown
```

Meaning:

- `static_html`: downloadable or candidate links were found through direct HTTP/HTML.
- `network_api`: links appear to come from an API/network call that can likely be reproduced.
- `playwright`: JavaScript rendering or deterministic UI interaction appears necessary.
- `vlm_required`: visual/UI reasoning may be needed after deterministic browser automation fails.
- `manual_review`: automation failed and human inspection is needed.
- `failed_blocked`: the provider is blocked, unreachable, or repeatedly failed.
- `unknown`: not enough evidence.

### Source and confidence fields

`source_name`, `source_role`, `source_type`, and `source_provenance` preserve
the Phase 1A registry context used for profiling. `strategy_confidence` records
`high`, `medium`, `low`, or `unknown`. `rendered_links_found` counts links
observed after browser rendering.

Old `provider_profile_v1` records without these fields remain loadable through
backward-compatible defaults.

### `requires_javascript`

Boolean or null.

### `static_links_found`

Count of links found in static HTML.

### `download_links_found`

Count of direct downloadable links found.

Direct downloadable links include:

```text
.pdf
.xls
.xlsx
.csv
.zip
```

### `candidate_document_links_found`

Count of links that look relevant but are not necessarily direct files.

Examples:

- portfolio disclosure pages
- factsheet pages
- statutory disclosure pages
- download-center pages

### `file_types_found`

List of file extensions discovered.

Example:

```json
["pdf", "xlsx", "zip"]
```

### `document_type_hints`

List of likely document types found from link text, URL, or page content.

Allowed values:

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

### `known_link_patterns`

Patterns that future crawls may use.

Example:

```json
[
  {
    "type": "url_contains",
    "value": "portfolio-disclosure"
  },
  {
    "type": "extension",
    "value": ".xlsx"
  }
]
```

### `known_selectors`

Selectors that worked during profiling.

Example:

```json
{
  "portfolio_tab": "text=Portfolio Disclosure",
  "download_links": "a[href$='.xlsx']"
}
```

Selectors should only be stored if they actually worked.

### `source_pages_examined`

List of pages inspected during profiling.

Example:

```json
[
  {
    "url": "https://www.example.com/downloads",
    "status_code": 200,
    "method": "static_html",
    "links_found": 42
  }
]
```

### `candidate_links`

A small capped list of relevant links found during profiling.

Each candidate link:

```json
{
  "url": "https://example.com/file.xlsx",
  "text": "Portfolio Disclosure May 2026",
  "file_type": "xlsx",
  "document_type_hint": "portfolio_disclosure",
  "source_page_url": "https://example.com/downloads",
  "discovery_method": "static_html"
}
```

Limit candidate links in profile records to avoid huge files. Full link discovery happens in Phase 2.

### `debug_artifacts`

Paths to saved debug files.

Example:

```json
{
  "static_html": "data/debug/mutual_funds/provider_profiles/hdfc/static.html",
  "screenshot": "data/debug/mutual_funds/provider_profiles/hdfc/screenshot.png",
  "network_log": "data/debug/mutual_funds/provider_profiles/hdfc/network_log.jsonl"
}
```

### `failure_reason`

Short failure reason if status is failed or manual review is required.

### `notes`

Optional notes.

## Provider Profile Summary

In addition to JSONL, Phase 1 should generate a summary report.

Minimum columns:

```text
amc_name
seed_url
status
detected_strategy
requires_javascript
static_links_found
download_links_found
candidate_document_links_found
file_types_found
failure_reason
```

## Re-Profiling Policy

Future runs should:

1. Load existing profile.
2. Try the known strategy first.
3. If it succeeds, update `last_successful_profile`.
4. If it fails, re-profile the provider.
5. Save a new profile record with the new run ID.

Do not overwrite old JSONL records.

## Quality Criteria

A good provider profile should answer:

- Can the site be accessed?
- Can relevant links be found?
- Which strategy should future phases use?
- What evidence supports that decision?
- What failed, if anything?
