# Phase 2 Sample Values and AMFI Reference Experiment

## 1. Purpose

The user wants Phase 2 to start showing real raw data values. This document explains what “raw values” means in Phase 2 and how AMFI should be handled.

Phase 2 should show real source data samples, but it should not become the parser phase.

## 2. Raw values expected in Phase 2

The Phase 2 review notebook and report should show concrete values from real source documents and metadata.

Examples:

```text
AMC Name: HDFC Mutual Fund
Document URL: https://...
Document Type Hint: portfolio_disclosure
Reporting Period Hint: 2026-05
File Extension: .xlsx
File Size: 842,331 bytes
SHA256: ...
Excel Sheets: Portfolio, Debt, Derivatives
First Raw Rows:
  Row 1: Scheme Name | Security Name | ISIN | Quantity | Market Value | % to NAV
  Row 2: HDFC Flexi Cap Fund | ICICI Bank Ltd | INE090A01021 | ... | ... | ...
```

These values should be shown as raw previews only.

Do not standardize security names, map ISINs, compute NAV sums, or load PostgreSQL in Phase 2.

## 3. Preview depth by file type

### Excel files

Required preview if dependency support exists:

- workbook sheet names,
- first 5–20 raw rows from first sheet or likely portfolio sheet,
- raw column names where available.

### CSV files

Required preview:

- first 5–20 raw rows,
- raw column names.

### PDF files

Optional preview:

- first-page text snippet only,
- no OCR,
- no table extraction requirement.

### ZIP files

Optional preview:

- contained filenames,
- compressed/uncompressed size if cheap.

## 4. Sample run expectation

The default notebook should run or load a conservative sample.

Suggested sample target:

```text
3–5 providers
up to 5 documents per provider
portfolio_disclosure and factsheet hints
latest documents preferred
```

The notebook should display:

1. provider strategy counts,
2. discovered document table,
3. downloaded file table,
4. preview table for 2–5 downloaded files,
5. failure table,
6. Phase 3 readiness summary.

## 5. AMFI role

AMC/provider websites remain the primary canonical source path.

AMFI can be used in Phase 2 only as a reference-source experiment or comparison sample.

Do not replace the provider-first architecture with AMFI scraping.

## 6. AMFI sample artifact

If implemented, create a separate notebook:

```text
notebooks/mutual_fund_ingestion/02a_amfi_raw_sample_review.ipynb
```

This notebook should be clearly marked as optional/reference-only.

It should answer:

- What AMFI pages or endpoints expose useful raw data?
- Can basic document links or data rows be extracted?
- What sample values are visible?
- How does AMFI coverage differ from provider websites?
- Should AMFI be used as a secondary index, validation aid, or fallback?

## 7. AMFI sample output

Optional outputs:

```text
data/raw/mutual_funds/amfi_reference/amfi_sample_documents.jsonl
data/raw/mutual_funds/amfi_reference/amfi_sample_values.jsonl
data/reports/mutual_funds/amfi_reference_sample_report.html
notebooks/mutual_fund_ingestion/02a_amfi_raw_sample_review.ipynb
```

Suggested AMFI sample record:

```json
{
  "schema_version": "phase2.amfi_reference_sample.v1",
  "run_id": "20260610T120000Z_ab12cd",
  "sampled_at": "2026-06-10T12:00:00Z",
  "source_name": "AMFI",
  "source_url": "https://www.amfiindia.com/...",
  "sample_type": "document_link_or_table_row",
  "raw_values": {
    "text": "Monthly Portfolio Disclosure",
    "href": "https://...",
    "date_hint": "May 2026"
  },
  "notes": "Reference only; not canonical Phase 2 provider source."
}
```

## 8. AMFI constraints

Codex should not spend excessive effort reverse-engineering AMFI dynamic pages in this task.

If AMFI requires complex JavaScript interaction or anti-bot handling, record the limitation and stop. Do not derail Phase 2.

## 9. What not to do

Do not:

- make AMFI the main source registry,
- replace AMC/provider downloads with AMFI-only downloads,
- parse AMFI data into canonical holdings,
- build NAV history ingestion in this phase,
- add investment advice outputs.

## 10. Success criteria

Phase 2 sample values are successful if the user can open the notebook/report and see:

- real provider document URLs,
- real downloaded file metadata,
- actual file previews where possible,
- enough concrete evidence to proceed to document classification and parsing.
