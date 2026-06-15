# Phase 2 Artifact Contract

## 1. Purpose

This document defines the machine-readable and human-readable artifacts Phase 2 must produce.

Codex should treat this as the output contract. Implementation details can adapt to the existing repository, but these artifacts should exist or have clear equivalents.

## 2. Required directory structure

```text
data/raw/mutual_funds/documents/
  discovered_documents.jsonl
  downloaded_files.jsonl
  files/
    <amc_safe_name>/
      <reporting_period_or_unknown>/
        <downloaded_file>
        <downloaded_file>.metadata.json

data/reports/mutual_funds/
  phase_2_raw_download_summary.csv
  phase_2_raw_download_report.html

data/debug/mutual_funds/phase_2/
  <run_id>/
    <amc_safe_name>/
      ...debug artifacts...

notebooks/mutual_fund_ingestion/
  02_phase_2_raw_download_review.ipynb
```

## 3. discovered_documents.jsonl

One JSON object per discovered candidate document.

Required fields:

```text
schema_version
run_id
discovered_at
amc_name
provider_seed_url
source_page_url
resolved_strategy
document_url
document_url_canonical
link_text
document_type_hint
reporting_period_hint
file_extension_hint
mime_type_hint
confidence
evidence
status
failure_reason
```

Allowed `status` values:

```text
discovered
skipped_duplicate
skipped_unresolved_strategy
invalid_url
failed
```

Allowed `document_type_hint` values:

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

Phase 2 should infer only hints, not final classifications.

## 4. downloaded_files.jsonl

One JSON object per attempted downloaded file.

Required fields:

```text
schema_version
run_id
downloaded_at
amc_name
source_page_url
document_url
document_url_canonical
resolved_strategy
document_type_hint
reporting_period_hint
local_file_path
metadata_file_path
file_name
file_extension
mime_type
content_length_bytes
sha256
http_status
final_url
download_status
failure_reason
preview_status
```

Allowed `download_status` values:

```text
success
skipped_existing
skipped_duplicate_hash
failed_http
failed_timeout
failed_invalid_url
failed_content_type
failed_write
failed_unknown
```

## 5. Metadata sidecar

For every successful download, write:

```text
<downloaded_file>.metadata.json
```

The sidecar should contain all fields from `downloaded_files.jsonl`, plus optional richer preview metadata:

```json
{
  "preview": {
    "preview_status": "success",
    "excel_sheet_names": [],
    "first_rows_sample": [],
    "csv_columns": [],
    "pdf_first_page_text_snippet": null,
    "zip_file_names": []
  }
}
```

Preview failures should never fail the download. Use:

```json
{
  "preview": {
    "preview_status": "failed",
    "failure_reason": "Could not open workbook"
  }
}
```

## 6. Summary CSV

Create:

```text
data/reports/mutual_funds/phase_2_raw_download_summary.csv
```

Suggested columns:

```text
run_id
amc_name
resolved_strategy
provider_status
discovered_count
download_success_count
download_failed_count
skipped_count
document_type_hints
file_extensions
latest_reporting_period_hint
sample_file_paths
failure_reasons
```

## 7. HTML report

Create:

```text
data/reports/mutual_funds/phase_2_raw_download_report.html
```

The HTML report should include:

1. run metadata,
2. provider counts by strategy,
3. discovered document counts,
4. download success/failure counts,
5. table of downloaded sample files,
6. table of failures,
7. links or paths to debug artifacts,
8. raw preview snippets for a few files,
9. readiness assessment for Phase 3.

The report does not need complex styling.

## 8. Debug artifacts

For failed or complex providers, save debug artifacts where available:

```text
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/
```

Possible files:

```text
discovery_request.json
source_page.html
rendered_page.html
network_log.jsonl
screenshot.png
candidate_links.jsonl
errors.jsonl
```

Do not store very large network bodies unless explicitly needed.

## 9. JSONL validity

Every JSONL file must be line-delimited valid JSON.

Tests should validate:

- file exists,
- every non-empty line parses as JSON,
- required fields exist,
- allowed enum fields are valid,
- local file paths exist for successful downloads,
- sidecar paths exist for successful downloads.

## 10. Deterministic identity and deduplication

Use stable identity fields:

```text
document_url_canonical
sha256
amc_name
document_type_hint
reporting_period_hint
```

Duplicate logic:

1. Same canonical URL and same output file exists: skip if `--skip-existing`.
2. Same checksum already downloaded in the run: mark `skipped_duplicate_hash`.
3. Different URL but same checksum: keep one file and record duplicate relationship if simple to support.

## 11. Run metadata

Every run should have a `run_id` that is stable for the process.

Recommended format:

```text
YYYYMMDDTHHMMSSZ_<short_random_or_hash>
```

Example:

```text
20260610T120000Z_ab12cd
```

## 12. Compatibility rule

If the existing repository already has a different artifact naming convention, Codex may adapt names only if:

1. the same information is preserved,
2. the review notebook can find the outputs,
3. the report clearly states the paths,
4. tests validate the actual paths.
