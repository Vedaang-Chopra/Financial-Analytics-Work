# Existing Codebase Audit Report

## Audit Scope

This audit was completed before implementing Phase 1 provider profiling. It
covers the repository structure, ingestion and crawler code, data samples,
parsers, database utilities, configuration, tests, notebooks, dependencies,
logging, and CLI patterns.

## 1. Repository Structure Summary

- The repository has 173 tracked files.
- `Code Base/` contains the legacy data collection, database, and analytics
  experiments.
- `Dataset/` contains 151 files, including 137 files under
  `Dataset/Monthly Reports October 2024/`.
- The repository contains 10 notebooks, primarily for exploratory ingestion,
  parsing, database work, and analytics.
- `amfi_disclosure/` is an uncommitted, tested AMFI-first crawler prototype.
- `docs/design/mutual_fund_ingestion/` defines the provider-first phased
  ingestion architecture.
- There is no existing Python packaging metadata or established package-level
  test directory convention.

## 2. Relevant Existing Files

| Path | Relevance | Classification |
| --- | --- | --- |
| `amfi_disclosure/http.py` | Polite requests session with retries, backoff, timeout, and user agent | reusable_now |
| `amfi_disclosure/discovery.py` | Deterministic HTML link and embedded-file extraction concepts | reusable_now |
| `amfi_disclosure/browser.py` | Optional Playwright import and failure-artifact patterns | reusable_now |
| `amfi_disclosure/models.py` | JSONL serialization example for crawler metadata | needs_refactor |
| `amfi_disclosure/downloader.py` | Raw-file download implementation | reusable_later |
| `Code Base/Dataset_Collection_Module/data_collection_module/jupyter notebooks/portfolio_distribution.ipynb` | Historical Selenium exploration with saved failures | not_recommended |
| `Code Base/Dataset_Collection_Module/data_collection_module/list_of_amc.py` | Historical AMFI group-company fetcher | reusable_later |
| `Code Base/Dataset_Collection_Module/database_module/portfolio_distribution/xlsx_extraction.ipynb` | Experimental workbook extraction | reusable_later |
| `Code Base/Dataset_Collection_Module/database_module/schema_definition/define_schema.py` | Legacy PostgreSQL schema code | not_recommended |
| `Resource Information Links/url_to_fetch_iforamtion.xlsx` | Historical AMFI URLs, not provider URLs | reusable_later |

## 3. Reusable Modules and Functions

- Reuse the behavior of `amfi_disclosure.http.HttpSettings` and
  `build_session`: descriptive user agent, request timeout, retry, and
  exponential backoff.
- Reuse the deterministic concepts in `amfi_disclosure.discovery`: URL
  canonicalization, direct-file detection, embedded-file detection, and
  standard-library HTML parsing.
- Reuse the optional dependency handling and debug-artifact approach in
  `amfi_disclosure.browser`.
- Reuse safe deterministic naming concepts from
  `amfi_disclosure.downloader.slugify`, without importing downloader code into
  Phase 1.

The Phase 1 package should implement its own provider-profile models and
orchestration rather than depend on AMFI-specific models.

## 4. Code That Should Be Modified

- Add a new `mutual_fund_ingestion/` package for provider-first Phase 1 code.
- Add `configs/amc_sources.yaml` as the provider source registry.
- Extend `requirements.txt` with `PyYAML`.
- Update `.gitignore` for generated mutual-fund profile artifacts.
- Update `README.md` with the Phase 1 CLI, scope, setup, and artifacts.

The existing `amfi_disclosure/` prototype should remain unchanged and isolated.

## 5. Code That Should Be Avoided or Deprecated

- Do not use the legacy Selenium notebook as an implementation base. It has
  brittle selectors and recorded timeout/no-such-element failures.
- Do not import legacy scripts that create RabbitMQ or PostgreSQL connections
  at module import time.
- Do not use the legacy database schema or loader during Phase 1.
- Do not use notebook-only parsing logic during Phase 1.
- Do not use `amfi_disclosure.downloader` during Phase 1 because document
  downloads are explicitly out of scope.

## 6. Existing Data Samples

- `Dataset/Monthly Reports October 2024/` contains provider disclosure samples
  from 360 ONE, Aditya Birla, Axis, Nippon India, Bank of India, Motilal
  Oswal, PPFAS, Quant, and ICICI Prudential.
- The directory includes 136 `.xlsx` files and 5 `.xls` files across the full
  dataset.
- The ICICI folder contains provider-specific per-scheme workbooks.
- `Dataset/analyse_csv/SEBI_Monthly_Portfolio 31 December 2023.xls` is another
  future portfolio parser fixture.
- These files are suitable for later parser tests but must not be parsed or
  transformed during Phase 1.

## 7. Existing Dependencies Available

`requirements.txt` already declares:

- `requests`
- `lxml`
- `numpy`
- `openpyxl`
- `pandas`
- `pika`
- `playwright`
- `SQLAlchemy`

The repository-local `financial_env` currently provides Playwright and its
Chromium browser binaries. Playwright must remain optional so the CLI can
produce explicit profiles when it is unavailable.

## 8. Missing Dependencies

- Add `PyYAML` for the source registry.
- The system Python environment does not currently provide all declared
  requirements, while `financial_env` does not currently provide `PyYAML`.
  Tests should avoid requiring optional browser or database dependencies.

## 9. Suggested Phase 1 Implementation Location

Implement Phase 1 under `mutual_fund_ingestion/` with focused modules for:

- source registry loading
- profile and evidence models
- static HTML inspection
- optional Playwright inspection
- provider profiling orchestration
- artifact persistence
- report generation
- CLI handling

Place deterministic Phase 1 fixtures and tests under `tests/`.

## 10. Risks and Unknowns

- Provider websites have heterogeneous disclosure structures and may change
  without notice.
- Some sites block static HTTP, require JavaScript, or use anti-bot controls.
- Current provider disclosure URLs require periodic manual registry review.
- Clear API hints in HTML do not prove an endpoint is stable or public.
- A full live run may be slow because profiling is intentionally sequential
  and polite.
- Browser availability and network restrictions vary by environment.
- Existing uncommitted AMFI prototype work must be preserved without being
  coupled to the provider-first implementation.

## Phase 1 Revision Decision

Keep the provider-first `mutual_fund_ingestion` package and split Phase 1 into
source-registry bootstrap and provider profiling. Reuse its HTTP, parsing,
naming, optional-browser, artifact, and report patterns. Keep the legacy AMFI
document downloader isolated because Phase 1A discovers provider sources, not
portfolio files. Phase 1 remains limited to registry/profile artifacts,
reports, metrics, and debug evidence.
