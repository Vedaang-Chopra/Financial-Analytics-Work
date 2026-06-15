# Codex Prompt — Implement Phase 2 Raw Document Discovery and Download

Read the following project context first:

```text
AGENTS.md
CHATGPT_PROJECT_MEMORY.md
docs/project_memory/*.md
docs/design/mutual_fund_ingestion/*.md
docs/design/mutual_fund_ingestion/phases/*.md
```

Then inspect the existing codebase before writing code.

The repository already has Phase 1a and Phase 1b provider profiling work. Phase 1.5 strategy resolution may be partial or complete. Continue from the existing implementation. Do not start a new scraper architecture from scratch unless the existing code is unusable, and if so, explain why.

## Task

Implement Phase 2: raw document discovery and download.

Use the design files:

```text
docs/design/mutual_fund_ingestion/phases/02_phase_2_raw_document_discovery_and_download.md
docs/design/mutual_fund_ingestion/phases/02_phase_2_artifact_contract.md
docs/design/mutual_fund_ingestion/phases/02_phase_2_sample_values_and_amfi_reference.md
docs/design/mutual_fund_ingestion/phases/02_phase_2_testing_and_acceptance.md
```

## Required behavior

Phase 2 must load Phase 1/1.5 provider profile artifacts and use resolved provider strategies.

Preferred input:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.resolved.latest.json
```

Fallback input:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
```

Only use fallback providers that already have concrete strategies:

```text
static_html
network_api
playwright
```

Skip unresolved providers by default:

```text
manual_review
unknown
vlm_required
manual_review_final
failed_blocked
```

Do not silently re-profile all provider websites.

## Required outputs

Produce these artifacts or clearly compatible equivalents:

```text
data/raw/mutual_funds/documents/discovered_documents.jsonl
data/raw/mutual_funds/documents/downloaded_files.jsonl
data/raw/mutual_funds/documents/files/<amc_safe_name>/<reporting_period_or_unknown>/<downloaded_file>
data/raw/mutual_funds/documents/files/<amc_safe_name>/<reporting_period_or_unknown>/<downloaded_file>.metadata.json
data/reports/mutual_funds/phase_2_raw_download_summary.csv
data/reports/mutual_funds/phase_2_raw_download_report.html
notebooks/mutual_fund_ingestion/02_phase_2_raw_download_review.ipynb
```

Add debug artifacts for failed or complex providers under:

```text
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/
```

## Required CLI/sample mode

Add a CLI command using the repository’s existing CLI style.

Suggested command if no pattern exists:

```bash
python -m mutual_fund_ingestion discover-download-documents \
  --sample \
  --limit-providers 5 \
  --limit-documents-per-provider 5 \
  --document-types portfolio_disclosure,factsheet \
  --latest-only \
  --skip-existing
```

Sample mode is required. It should let the user see real raw values quickly without running a full crawl.

## Raw preview requirement

The Phase 2 notebook/report must show actual raw values from downloaded files when possible.

For Excel/CSV files, show:

- sheet names if Excel,
- first 5–20 raw rows,
- raw columns/cells exactly as found.

For PDFs, optionally show a first-page text snippet if a lightweight dependency already exists. Do not use OCR.

For ZIP files, list contained filenames if cheap.

Do not normalize holdings. Do not create canonical tables. Do not implement Phase 3/4/5.

## AMFI reference sample

Optionally add a separate AMFI reference notebook:

```text
notebooks/mutual_fund_ingestion/02a_amfi_raw_sample_review.ipynb
```

This is reference-only. It should not replace the provider-first architecture.

If AMFI pages are dynamic or difficult, record the limitation and do not derail Phase 2.

## Tests

Add lightweight tests for:

- URL canonicalization,
- candidate link extraction,
- document type hinting,
- safe filename generation,
- JSONL validity,
- sidecar metadata generation,
- preview extraction for local Excel/CSV fixtures if practical.

Live website tests should be disabled by default or clearly marked.

## Phase boundaries

Do not implement:

- full document classification,
- full parser,
- staging tables,
- PostgreSQL schema/loading,
- validation/quarantine,
- analytics,
- financial recommendations.

## Final response expected from Codex

After implementation, summarize:

1. files changed,
2. existing code reused,
3. new CLI command,
4. sample command to run,
5. artifacts produced,
6. tests added and test command,
7. known limitations,
8. whether Phase 3 is ready.
