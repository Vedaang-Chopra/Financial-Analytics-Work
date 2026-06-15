# Phase 2 Testing and Acceptance Criteria

## 1. Purpose

This document defines the minimum tests and acceptance criteria for Phase 2 raw document discovery and download.

The goal is to keep the implementation reliable while avoiding premature work from later phases.

## 2. Required test categories

Codex should add lightweight tests that match the existing repository test style.

If no test structure exists, create a minimal test module under a sensible location such as:

```text
tests/mutual_fund_ingestion/test_phase_2_*.py
```

## 3. Unit tests

### 3.1 URL canonicalization

Test that:

- relative URLs are resolved correctly,
- URL fragments are removed,
- repeated tracking parameters can be handled if the project has a URL cleaner,
- invalid URLs are rejected cleanly.

### 3.2 Candidate document extraction

Use saved HTML fixtures or inline test HTML.

Test extraction of:

- PDF links,
- XLS/XLSX links,
- CSV links,
- ZIP links,
- portfolio disclosure keyword matches,
- factsheet keyword matches.

Example input:

```html
<a href="/downloads/monthly-portfolio-may-2026.xlsx">Monthly Portfolio Disclosure May 2026</a>
<a href="/factsheets/factsheet-may-2026.pdf">Factsheet May 2026</a>
```

Expected output:

```text
2 discovered documents
portfolio_disclosure hint for first link
factsheet hint for second link
```

### 3.3 Safe filename generation

Test that filenames are:

- deterministic,
- filesystem-safe,
- not too long,
- preserve useful extension,
- include AMC/document/reporting-period hints where possible.

### 3.4 JSONL writing and reading

Test that:

- JSONL writer creates valid line-delimited JSON,
- every record can be parsed,
- required fields are present.

### 3.5 Metadata sidecar generation

Test that a downloaded file record can create a sidecar JSON with required fields.

### 3.6 Preview extraction

Use tiny local fixtures where practical.

Test:

- Excel sheet names and first rows for `.xlsx`,
- CSV first rows,
- ZIP file listing,
- graceful failure for unsupported/corrupt files.

PDF preview test is optional unless the repository already has a lightweight PDF dependency.

## 4. Integration tests

Live website tests should be limited and disabled by default.

Recommended marker:

```text
@pytest.mark.live
```

or equivalent existing convention.

A basic live test may run against one known provider or one local mock server, but CI/default test should not depend on external websites.

## 5. Sample run acceptance

A Phase 2 sample run should pass if:

1. it loads resolved provider profiles,
2. it skips unresolved providers cleanly,
3. it discovers at least some candidate documents for available providers,
4. it downloads a bounded number of files,
5. it writes metadata sidecars,
6. it writes JSONL artifacts,
7. it writes CSV and HTML reports,
8. it creates/updates the review notebook,
9. it shows actual raw preview values for at least one Excel/CSV file if such a file is downloaded.

## 6. Failure acceptance

Phase 2 may still be acceptable if some providers fail.

Failures are acceptable when:

- they are isolated to specific providers,
- the run continues for other providers,
- failure reasons are categorized,
- debug artifacts are saved where useful,
- the report clearly shows what failed.

Failures are not acceptable when:

- missing inputs are silently ignored,
- all providers are re-profiled from scratch without using Phase 1.5,
- JSONL files are invalid,
- successful downloads lack metadata sidecars,
- the notebook cannot locate outputs,
- the implementation starts parsing/loading canonical database tables.

## 7. Phase boundary tests

Add tests or code checks to ensure Phase 2 does not import or execute future-phase loaders unnecessarily.

Phase 2 should not require PostgreSQL.

Phase 2 should not require a canonical holdings schema.

Phase 2 should not require full document classification.

## 8. Manual verification checklist

After Codex implementation, run:

```bash
pytest
```

Then run a sample command similar to:

```bash
python -m mutual_fund_ingestion discover-download-documents \
  --sample \
  --limit-providers 5 \
  --limit-documents-per-provider 5 \
  --document-types portfolio_disclosure,factsheet \
  --latest-only \
  --skip-existing
```

If the repository uses a different CLI entry point, use the equivalent command and document it in the report/notebook.

Then open:

```text
notebooks/mutual_fund_ingestion/02_phase_2_raw_download_review.ipynb
```

Confirm it shows:

- strategy counts,
- discovered document rows,
- downloaded file rows,
- raw previews,
- failure summary,
- next-phase readiness.

## 9. Definition of done

Phase 2 is done when:

- source profiles from Phase 1/1.5 are reused,
- sample mode works,
- raw documents are discovered and downloaded,
- metadata and sidecars exist,
- raw previews show actual data values where possible,
- reports and notebook exist,
- tests cover core utilities,
- no future phases are implemented prematurely.
