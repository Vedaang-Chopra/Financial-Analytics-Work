# Phase 2 — Raw Document Discovery and Download

## 1. Purpose

Phase 2 starts collecting actual raw investor disclosure documents from AMC/provider websites.

The project has already completed or partially completed Phase 1a and Phase 1b provider profiling. Phase 1.5 strategy resolution may also exist partially. Phase 2 must build on top of those outputs instead of starting from scratch.

The goal is to discover and download raw files from known provider sources using the best known provider strategy.

Phase 2 should produce visible, inspectable evidence that real data is being collected:

- real document URLs,
- real downloaded files,
- real metadata sidecars,
- real checksums,
- real file sizes,
- real sheet names / first rows for Excel or CSV files where possible,
- real first-page text snippets for PDFs where cheap and reliable.

Phase 2 is not a parser phase. It should preview raw values for confidence, but it should not normalize holdings into canonical database tables.

## 2. Position in the pipeline

The project pipeline is:

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

Phase 2 owns only:

```text
Provider strategy resolution outputs
→ Document discovery
→ Raw file download
→ raw metadata
→ sample previews
→ review notebook/report
```

## 3. Inputs

Phase 2 should prefer these inputs:

```text
configs/amc_sources.yaml

data/raw/mutual_funds/provider_profiles/provider_profiles.resolved.latest.json
```

Fallback input if Phase 1.5 has not produced resolved profiles:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
```

However, fallback is allowed only for providers that already have concrete strategies such as:

```text
static_html
network_api
playwright
```

Do not use unresolved providers by default.

Unresolved strategy values should be skipped unless explicitly requested:

```text
manual_review
unknown
vlm_required
manual_review_final
failed_blocked
```

## 4. Main outputs

Expected Phase 2 outputs:

```text
data/raw/mutual_funds/documents/discovered_documents.jsonl
data/raw/mutual_funds/documents/downloaded_files.jsonl
data/raw/mutual_funds/documents/files/<amc_safe_name>/<yyyy_mm_or_unknown>/<filename>
data/raw/mutual_funds/documents/files/<amc_safe_name>/<yyyy_mm_or_unknown>/<filename>.metadata.json
data/reports/mutual_funds/phase_2_raw_download_summary.csv
data/reports/mutual_funds/phase_2_raw_download_report.html
notebooks/mutual_fund_ingestion/02_phase_2_raw_download_review.ipynb
```

Optional debug outputs:

```text
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/discovery_page.html
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/rendered_page.html
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/network_log.jsonl
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/screenshot.png
data/debug/mutual_funds/phase_2/<run_id>/<amc_safe_name>/errors.jsonl
```

## 5. Discovery behavior

Phase 2 should use the resolved provider strategy.

### 5.1 Static HTML strategy

For providers marked `static_html`:

1. Fetch the provider seed URL and known source pages.
2. Parse anchor tags and form-linked URLs.
3. Extract candidate document links.
4. Resolve relative URLs.
5. Filter by known file extensions and disclosure keywords.
6. Write candidates to `discovered_documents.jsonl`.

Candidate file extensions:

```text
.pdf
.xls
.xlsx
.csv
.zip
```

Candidate keywords:

```text
portfolio
portfolio-disclosure
monthly-portfolio
factsheet
fact-sheet
statutory-disclosure
scheme
sid
kim
ter
disclosure
fund portfolio
```

### 5.2 Network/API strategy

For providers marked `network_api`:

1. Reuse network endpoint hints from provider profiles if available.
2. Call known JSON/API endpoints using polite request settings.
3. Extract document URLs and metadata fields from JSON responses.
4. Preserve raw API response excerpts in debug artifacts if not too large.
5. Write candidates to `discovered_documents.jsonl`.

Do not hardcode provider-specific endpoints unless existing Phase 1 artifacts provide them or the codebase already has provider-specific logic.

### 5.3 Playwright strategy

For providers marked `playwright`:

1. Use deterministic browser automation only.
2. Do not use autonomous browsing.
3. Load the provider page.
4. Wait for network idle or known selectors from provider profile.
5. Extract visible document links and download URLs.
6. Capture screenshot and rendered HTML as debug artifacts.
7. Write candidates to `discovered_documents.jsonl`.

Do not use local VLM by default in Phase 2. VLM recovery belongs to a later fallback layer unless explicitly requested.

## 6. Document candidate schema

Each discovered document record should be JSONL-compatible and include:

```json
{
  "schema_version": "phase2.discovered_document.v1",
  "run_id": "2026-06-10T00-00-00Z_xxxxx",
  "discovered_at": "2026-06-10T00:00:00Z",
  "amc_name": "Example Mutual Fund",
  "provider_seed_url": "https://example.com/disclosures",
  "source_page_url": "https://example.com/disclosures/monthly",
  "resolved_strategy": "static_html",
  "document_url": "https://example.com/path/file.xlsx",
  "document_url_canonical": "https://example.com/path/file.xlsx",
  "link_text": "Monthly Portfolio Disclosure - May 2026",
  "document_type_hint": "portfolio_disclosure",
  "reporting_period_hint": "2026-05",
  "file_extension_hint": ".xlsx",
  "mime_type_hint": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "confidence": 0.81,
  "evidence": {
    "matched_keywords": ["portfolio", "disclosure"],
    "matched_extension": ".xlsx",
    "selector_or_source": "a[href]"
  },
  "status": "discovered",
  "failure_reason": null
}
```

## 7. Download behavior

For each discovered document selected for download:

1. Download using `requests`/`httpx` or existing project download utility.
2. Use retry/backoff.
3. Respect polite crawling settings.
4. Avoid duplicate downloads by canonical URL and content checksum.
5. Save file with deterministic sanitized filename.
6. Compute checksum.
7. Write metadata sidecar JSON.
8. Append a record to `downloaded_files.jsonl`.

Recommended checksum:

```text
sha256
```

Recommended file naming pattern:

```text
<amc_safe_name>__<document_type_hint>__<reporting_period_or_unknown>__<short_hash>.<ext>
```

Example:

```text
hdfc_mutual_fund__portfolio_disclosure__2026_05__a1b2c3d4.xlsx
```

## 8. Download metadata sidecar schema

For every downloaded file, write a sidecar:

```json
{
  "schema_version": "phase2.downloaded_file_metadata.v1",
  "run_id": "2026-06-10T00-00-00Z_xxxxx",
  "downloaded_at": "2026-06-10T00:00:00Z",
  "amc_name": "Example Mutual Fund",
  "source_page_url": "https://example.com/disclosures/monthly",
  "document_url": "https://example.com/path/file.xlsx",
  "document_url_canonical": "https://example.com/path/file.xlsx",
  "resolved_strategy": "static_html",
  "document_type_hint": "portfolio_disclosure",
  "reporting_period_hint": "2026-05",
  "local_file_path": "data/raw/mutual_funds/documents/files/example_mutual_fund/2026_05/example.xlsx",
  "metadata_file_path": "data/raw/mutual_funds/documents/files/example_mutual_fund/2026_05/example.xlsx.metadata.json",
  "file_name": "example.xlsx",
  "file_extension": ".xlsx",
  "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "content_length_bytes": 123456,
  "sha256": "...",
  "http_status": 200,
  "final_url": "https://example.com/path/file.xlsx",
  "download_status": "success",
  "failure_reason": null,
  "preview": {
    "preview_status": "success",
    "excel_sheet_names": ["Portfolio", "Debt"],
    "first_rows_sample": [
      ["Scheme Name", "Security Name", "ISIN", "% to NAV"],
      ["Example Fund", "Example Ltd", "INE000A01000", "2.34"]
    ],
    "pdf_first_page_text_snippet": null
  }
}
```

## 9. Raw preview behavior

Phase 2 must show raw values, but only as lightweight previews.

Preview rules:

### Excel/XLSX/XLS

For Excel files:

- list sheet names,
- read the first sheet or likely portfolio sheet,
- display the first 5–20 rows without normalization,
- preserve original column names and cell values,
- do not infer canonical schema yet.

Use existing utilities if available. Otherwise prefer `pandas` and `openpyxl` for `.xlsx`.

### CSV

For CSV files:

- read the first 5–20 rows,
- preserve original columns,
- do not normalize.

### PDF

For PDFs:

- do not do expensive OCR,
- optionally extract first-page text only if a lightweight PDF text tool already exists,
- otherwise show file metadata only.

### ZIP

For ZIP files:

- list contained filenames,
- do not recursively parse all files yet,
- optionally extract only metadata.

## 10. Sample mode

Phase 2 must support a small sample run so the user can inspect real data without triggering a large crawl.

Required CLI options:

```text
--sample
--limit-providers 3
--limit-documents-per-provider 5
--document-types portfolio_disclosure,factsheet
--latest-only
--dry-run
--skip-existing
--output-dir data/raw/mutual_funds/documents
--report-dir data/reports/mutual_funds
```

Example command:

```bash
python -m mutual_fund_ingestion discover-download-documents \
  --sample \
  --limit-providers 5 \
  --limit-documents-per-provider 5 \
  --document-types portfolio_disclosure,factsheet \
  --latest-only \
  --skip-existing
```

If the current codebase has a different CLI pattern, reuse that pattern instead of forcing this exact command name.

## 11. Full-run mode

Full-run mode can exist, but it should not be the default in the review notebook.

Defaults should be conservative:

- skip unresolved providers,
- skip failed/blocked providers,
- skip existing files,
- limit concurrency,
- preserve debug artifacts for failures,
- write reports even when downloads fail.

## 12. Error handling

Each provider should produce a clear final status:

```text
success
partial_success
no_documents_found
skipped_unresolved_strategy
download_failed
blocked_or_unreachable
strategy_failed
```

Errors should not crash the whole run unless a core input artifact is missing.

## 13. Reuse requirements

Codex must inspect and reuse existing code where compatible:

- source registry loader,
- provider profile models,
- strategy resolution outputs,
- HTTP client utilities,
- safe filename utilities,
- JSONL writer utilities,
- report generation utilities,
- Playwright helpers,
- notebook conventions,
- test patterns.

Do not create duplicate abstractions if suitable ones already exist.

## 14. Notebook requirements

Create:

```text
notebooks/mutual_fund_ingestion/02_phase_2_raw_download_review.ipynb
```

The notebook should:

1. explain Phase 2 scope,
2. load resolved provider profiles,
3. show strategy counts,
4. run or load a sample discovery/download run,
5. display discovered documents as a DataFrame,
6. display downloaded files as a DataFrame,
7. show local file paths and metadata sidecars,
8. show raw previews from 2–5 files,
9. summarize failures,
10. state readiness for Phase 3 classification.

The notebook must not duplicate production logic.

## 15. Readiness for Phase 3

Phase 2 is ready for Phase 3 when:

- discovered documents are written to JSONL,
- downloaded file metadata is written to JSONL and sidecars,
- sample downloaded files are inspectable,
- at least a few real Excel/PDF/CSV files are present if available,
- raw previews show actual values,
- failures are categorized,
- the report and notebook are understandable.

Phase 2 does not require complete coverage of all AMCs.
