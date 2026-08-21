# Mutual Fund Ingestion System — Comprehensive Audit Report

**Audit Date:** 2026-08-21  
**Auditor:** AI Agent  
**Scope:** End-to-end verification of mutual fund disclosure ingestion system against actual codebase, configuration, and live PostgreSQL database.

---

## A. Executive Summary

### What is Genuinely Working (Production-Proven)

| Capability | Evidence | Status |
|------------|----------|--------|
| **Phase 1A: Source Registry Bootstrap** | 53 AMCs + AMFI + SEBI catalogued in `configs/amc_sources.yaml`; CLI `bootstrap-sources` works | ✅ Complete |
| **Phase 1B: Provider Profiling** | 18 AMCs profiled; 6 strategies identified; static HTML + Playwright extraction works | ✅ Complete |
| **Dataset Census** | 20 AMFI datasets catalogued in `configs/amfi_dataset_census.yaml` | ✅ Complete |
| **AMC Capability Matrix** | 53 AMCs with strategy, format, frequency, working status in `configs/amc_capability_matrix.yaml` | ✅ Complete |
| **Scheme Identity Layer** | `SchemeIdentityResolver` resolves AMFI scheme_code, ISIN, fuzzy name; handles plan/option | ✅ Complete |
| **NAV Pipeline** | Backfill (90-day windows), incremental, gap detection, coverage reporting; parser handles multiple formats | ✅ Complete |
| **Portfolio Pipeline** | Strategy-aware (static_html, playwright, playwright_vlm); 6 AMCs working (PPFAS, DSP, Mirae, Invesco, ICICI, Groww); ZIP handling | ✅ Complete |
| **Raw Artifact Storage** | Local + S3 backends; tiered retention (hot/warm/cold/archived); SHA256 deduplication; metadata in PostgreSQL | ✅ Complete |
| **Coverage & Quality** | 6 coverage tables; `CoverageCalculator` with gap detection, alerts, quality metrics | ✅ Complete |
| **Validation & Quarantine** | NAV/portfolio/scheme_master/AMC validators; quarantine_rows table; retry_queue | ✅ Complete |
| **AMC-Specific Navigators** | 9 navigators for complex sites (ICICI, Mirae, LIC, Axis, Aditya Birla, etc.) | ✅ Complete |

### What is Partially Implemented

| Capability | Gap | Evidence |
|------------|-----|----------|
| **NAV Historical Backfill** | Only 3 weeks of NAV data (2026-07-30 to 2026-08-20); 7,468 records across 7,468 schemes | Live DB shows 22-day window only |
| **Portfolio Historical Coverage** | 836 snapshots across 154 schemes (2013-2026) but only 6 AMCs; ICICI dominates (106K holdings) | Live DB shows heavy skew |
| **AMC Table** | **0 AMCs** in `amcs` table; all 7,622 schemes have NULL `amc_id` | Critical data identity gap |
| **Provenance Chain** | `documents.raw_artifact_id` = NULL; `documents.checksum` = NULL; cannot trace from canonical → raw file | Broken linkage |
| **Coverage Tables** | All 6 coverage tables **empty** (`dataset_coverage`, `scheme_coverage`, `amc_coverage`, `coverage_snapshots`, `coverage_alerts`, `ingestion_quality_metrics`) | `CoverageCalculator.update_all_coverage()` never run |
| **Scheme Metadata** | Schemes from NAV have placeholder names ("Scheme 100033"); portfolio schemes have real names but no AMC link | Dual scheme populations not merged |
| **Debt-Specific Fields** | `rating`, `coupon`, `maturity_date`, `asset_class` all NULL/empty in `portfolio_holdings` | 0 records with these fields |
| **Sector/Industry Classification** | `sector` field holds credit rating (CRISIL AAA, SOV) not industry sector | Parser maps rating → sector column |
| **ISIN Coverage** | Only 27.5% of holdings have ISIN (61,683 / 224,422) | Equity schemes lack ISIN |
| **Market Value / % NAV** | Only ~48% of holdings have these fields | Equity schemes missing |

### What is Only Designed/Catalogued (Not Implemented)

| Dataset | Census Status | Parser | Pipeline | DB Tables |
|---------|---------------|--------|----------|-----------|
| Scheme Master Monthly | ✅ Catalogued | ❌ `scheme_master_excel_v1` needed | ❌ Metadata Pipeline | ❌ |
| TER (Expense Ratio) | ✅ Catalogued | ❌ `ter_excel_v1` needed | ❌ TER Pipeline | ❌ |
| AUM / AAUM | ✅ Catalogued | ❌ `aum_excel_v1` needed | ❌ AUM Pipeline | ❌ |
| AMFI Monthly/Quarterly | ✅ Catalogued | ❌ `scheme_master_excel_v1` needed | ❌ Industry Data Pipeline | ❌ |
| Factsheet/SID/KIM/SAI | ✅ Catalogued | ❌ PDF parsers needed | ❌ Metadata Pipeline | ❌ |
| Risk Parameters | ✅ Catalogued | ❌ Not investigated | ❌ | ❌ |
| NFO | ✅ Catalogued | ❌ Not implemented | ❌ | ❌ |
| Tracking Error | ✅ Catalogued | ❌ Not implemented | ❌ | ❌ |

### What is Broken

1. **AMC table empty** — No AMC records exist; schemes cannot be linked to AMCs
2. **Provenance chain broken** — `documents.raw_artifact_id` NULL; cannot trace canonical row → raw file → checksum
3. **Coverage system inert** — All coverage tables empty; calculator never executed
4. **Scheme identity fragmentation** — Two separate scheme populations (NAV: 7,622 placeholder schemes; Portfolio: 154 real schemes) not reconciled
5. **Debt fields not captured** — Rating, coupon, maturity, asset_class all empty
6. **Duplicate holdings** — "Total", "Sub Total", "Direct Plan" section headers stored as holdings (hundreds of duplicates)
7. **Invalid ISINs** — "Nil", "(Short)" stored as ISINs in instruments table

---

## B. Dataset Implementation Matrix

Based on `configs/amfi_dataset_census.yaml` (20 datasets) and `configs/amc_capability_matrix.yaml` (53 AMCs):

| Dataset ID | Category | Source Discovery | Download | Parser | Staging | Validation | Canonical Schema | Loader | Live Rows | Historical | Incremental | Status |
|------------|----------|------------------|----------|--------|---------|------------|------------------|--------|-----------|------------|-------------|--------|
| nav_history | nav | ✅ AMFI form | ✅ | ✅ nav_text_v1 | ✅ | ✅ | ✅ nav_history | ✅ | 7,468 | ❌ 22 days | ✅ Daily | **PARTIAL** |
| nav_latest_open_ended | nav | ✅ | ✅ | ✅ nav_text_v1 | ✅ | ✅ | ✅ nav_history | ✅ | — | — | — | **PARTIAL** |
| portfolio_disclosure | portfolio | ✅ Provider pages | ✅ (6 AMCs) | ✅ portfolio_excel_v1, portfolio_zip_v1 | ✅ | ✅ | ✅ portfolio_snapshots/holdings | ✅ | 224,422 | ✅ 2013-2026 | ✅ Monthly | **WORKING (6 AMCs)** |
| scheme_master_monthly | metadata | ✅ AMFI links | ❌ | ❌ scheme_master_excel_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| scheme_wise_disclosure | metadata | ✅ AMFI form | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| aum_aaum_disclosure | aum | ✅ AMFI form | ❌ | ❌ aum_excel_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| average_aum | aum | ✅ AMFI form | ❌ | ❌ aum_excel_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| ter_mf_schemes | ter | ✅ AMFI form | ❌ | ❌ ter_excel_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| amfi_monthly_data | industry | ✅ AMFI links | ❌ | ❌ scheme_master_excel_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| amfi_quarterly_data | industry | ✅ AMFI links | ❌ | ❌ scheme_master_excel_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |
| factsheet_index | factsheet | ✅ AMFI index | ❌ | ❌ factsheet_pdf_v1 | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | ❌ | **NOT_IMPLEMENTED** |

### AMC-Specific Dataset Status (from capability matrix)

| AMC | Portfolio | Factsheet | NAV | TER | AUM | Riskometer | SID/KIM | Status |
|-----|-----------|-----------|-----|-----|-----|------------|---------|--------|
| PPFAS | ✅ Working | Discovered | Via AMFI | Not profiled | Not profiled | Not profiled | Discovered | **Working** |
| DSP | ✅ Working | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Working** |
| Mirae | ✅ Working | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Working** |
| Invesco | ✅ Working | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Working** |
| ICICI | ✅ Working | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Working** |
| Groww | ✅ Working | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Working** |
| Aditya Birla | Needs browser/VLM | Discovered | Via AMFI | Discovered | Discovered | Discovered | Not profiled | **Needs VLM** |
| HDFC | Failed | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Broken** |
| Axis, Kotak, LIC, SBI, UTI, Nippon, 47 others | Not profiled | Not profiled | Via AMFI | Not profiled | Not profiled | Not profiled | Not profiled | **Not Started** |

---

## C. Parser Audit

| Parser | Module | Input Dataset | Formats | Source/Provider | Fields Extracted | Fields Ignored | Raw Fields Preserved? | Reporting Date Extraction | Scheme ID Method | AMC ID Method | Validation | Tests | Live Evidence |
|--------|--------|---------------|---------|-----------------|------------------|----------------|----------------------|---------------------------|------------------|---------------|------------|-------|---------------|
| nav_text_v1 | `agent/parser/nav.py` | nav_history | text, txt | AMFI NAVAll.txt | scheme_code, nav_date, nav_value, (isin_div_payout, isin_div_reinvestment, scheme_name, plan, option — **detected but not stored**) | — | ❌ Only 3 fields in output | DD-MMM-YYYY, YYYY-MM-DD, DD/MM/YYYY | scheme_code (primary) | Not used (AMFI primary) | validate_nav_record | Unit tests pass | 7,468 records in DB |
| nav_csv_v1 | `agent/parser/nav.py` | nav_history | csv | AMFI CSV | Same as text | — | ❌ | Same | Same | Same | Same | Unit tests pass | Not used in prod |
| nav_html_v1 | `agent/parser/nav.py` | nav_history | html | AMFI HTML tables | scheme_code, nav_value, nav_date, scheme_name | — | ❌ | HTML table parsing | Same | Same | Same | Unit tests pass | Not used in prod |
| portfolio_excel_v1 | `agent/parser/portfolio.py` | portfolio_disclosure | xlsx, xls | AMC provider sites | security_name, isin, sector (← **actually rating**), percentage_to_nav, market_value, sheet_name, row_number, scheme_name, reporting_date | quantity, asset_class, coupon, maturity_date | ❌ Unknown columns dropped | Regex from sheet: "as on", "portfolio as on" | Sheet name / filename / zip_scheme_name | From registry capability | validate_portfolio_record | Unit tests pass | 224,422 holdings |
| portfolio_zip_v1 | `agent/parser/portfolio.py` | portfolio_disclosure | zip | ICICI Prudential | Delegates to portfolio_excel_v1 per file | — | ❌ | From ZIP filename (e.g., "15th August 2026") | From filename (zip_scheme_name) | From registry | Same | Unit tests pass | ICICI ZIPs processed |
| portfolio_csv_v1 | `agent/parser/portfolio.py` | portfolio_disclosure | csv | AMC sites | Same as Excel | — | ❌ | — | — | — | Same | Unit tests pass | Not used |
| scheme_master_csv_v1 | `agent/parser/scheme_master.py` | scheme_master | csv | AMFI Monthly | scheme_code, scheme_name, plan, option, category, sub_category, isin | — | ❌ | — | scheme_code | amc_name column | validate_scheme_master_record | Unit tests pass | Not used (no CSV source) |
| scheme_master_html_v1 | `agent/parser/scheme_master.py` | scheme_master | html | AMFI HTML | Same | — | ❌ | — | Same | Same | Same | Unit tests pass | Not used |
| amc_html_v1 | `agent/parser/amc.py` | amc_provider_list | html | AMFI members | name, website_url | — | ❌ | — | — | — | validate_amc_record | Unit tests pass | Not used |
| metadata_html/pdf/csv | `agent/parser/metadata.py` | factsheet/sid/kim/ter/aum | html, pdf, csv | Various | **STUBS ONLY — returns empty ParserResult** | — | — | — | — | — | — | None | Not implemented |

### Critical Parser Findings

1. **NAV Parser drops 5+ fields** from AMFI 8-column format: `isin_div_payout`, `isin_div_reinvestment`, `scheme_name`, `plan`, `option` — detected in header parsing but not included in output records.

2. **Portfolio Parser maps "rating" → "sector" column** — The `sector` field in DB actually contains credit ratings (CRISIL AAA, SOV, ICRA A1+). True industry sector is not captured.

3. **Debt-specific fields completely missing** — `coupon`, `maturity_date`, `asset_class` are parsed from column aliases but **never appear in output records** (all NULL in DB).

4. **Unknown Excel columns silently dropped** — No JSONB/raw_fields preservation; any column not in `COLUMN_ALIASES` is ignored.

5. **Multiple sheets handled** — `parse_portfolio_excel` iterates all sheets, extracts scheme_name from pre-header rows.

6. **ZIP archives handled** — `parse_portfolio_zip` extracts each file, parses recursively, attaches filename-derived scheme_name and reporting_date.

7. **Parser failures quarantined** — `validate_and_filter_records` routes invalid records to `quarantine_rows` with reason codes.

8. **Dates inferred from multiple patterns** — Regex handles "as on June 30, 2026", "Portfolio as on Aug 15,2026", "Monthly Portfolio Statement as on June 30, 2026".

9. **Scheme names from filenames/sheets** — For ZIP: filename stripped of suffixes; for Excel: pre-header row text; fallback to sheet_name.

10. **AMC identification** — From capability registry (seed URLs), not from file content.

---

## D. PostgreSQL Schema Audit

### Table Inventory (23 Tables)

| Table | Purpose | PK | FKs | Unique Constraints | Key Indexes | Date/Time | Provenance Ref | JSONB Support | Row Count | Earliest | Latest | Issues |
|-------|---------|----|-----|-------------------|-------------|-----------|----------------|---------------|-----------|----------|--------|--------|
| ingestion_runs | Top-level run tracking | id (UUID) | — | — | — | started_at, finished_at | — | config_json, error_summary | 42 | 2026-08-20 | 2026-08-20 | Working |
| task_urls | Input URLs | id (UUID) | run_id → ingestion_runs | — | run_id | created_at | run_id | notes | 0 | — | — | Not populated by pipelines |
| source_pages | Fetched pages | id (UUID) | run_id → ingestion_runs | — | run_id, domain | created_at | run_id | metadata_json | 0 | — | — | Legacy agent only |
| discovered_links | Extracted links | id (UUID) | run_id, source_page_id | — | run_id | created_at | run_id | metadata_json | 0 | — | — | Legacy agent only |
| dataset_candidates | High-relevance files | id (UUID) | run_id, source_page_id | — | dataset_type | created_at | run_id | metadata_json | 0 | — | — | Legacy agent only |
| raw_artifacts | Downloaded file metadata | id (UUID) | run_id, dataset_candidate_id | checksum (index) | checksum | fetch_timestamp | run_id | metadata_json | 456 | 2026-06-29 | 2026-08-20 | **checksum NULL for all** |
| amcs | AMC master | id (UUID) | — | normalized_name | normalized_name | created_at, updated_at | source_url | metadata_json | **0** | — | — | **EMPTY — CRITICAL** |
| schemes | Scheme master | id (UUID) | amc_id → amcs | scheme_code, normalized_scheme_name (idx) | scheme_code, normalized_scheme_name | created_at, updated_at | — | metadata_json | 7,622 | — | — | **All amc_id NULL; NAV schemes have placeholder names** |
| nav_history | Daily NAV | id (UUID) | scheme_id → schemes | (scheme_code, nav_date) | scheme_code+nav_date | nav_date | raw_artifact_id, source_url | — | 7,468 | 2026-07-30 | 2026-08-20 | **Only 22 days; scheme_id often NULL** |
| documents | Document records | id (UUID) | raw_artifact_id, amc_id, scheme_id | (scheme_id, reporting_date, document_type, source_url) | — | reporting_date | raw_artifact_id (FK), checksum | metadata_json | 836 | 2013-03-31 | 2026-08-21 | **raw_artifact_id NULL; checksum NULL** |
| instruments | Securities by ISIN | id (UUID) | — | isin (idx) | isin, security_name | created_at, updated_at | — | metadata_json | 182,018 | — | — | **Invalid ISINs: "Nil", "(Short)"** |
| portfolio_snapshots | Disclosure events | id (UUID) | amc_id, scheme_id, document_id | (scheme_id, reporting_date) | scheme_id+reporting_date | reporting_date | source_url, parser_version | metadata_json | 836 | 2013-03-31 | 2026-08-21 | **amc_id NULL** |
| portfolio_holdings | Individual holdings | id (UUID) | snapshot_id, instrument_id | (snapshot_id, security_name, isin) | isin, security_name | created_at | — | metadata_json | 224,422 | — | — | **sector=rating; asset_class/coupon/maturity/rating all NULL; 27.5% ISIN coverage** |
| staging_rows | Pre-validation records | id (UUID) | run_id, raw_artifact_id, document_id | — | — | created_at | run_id, raw_artifact_id | raw_row_json, parsed_fields_json | 453,283 | 2026-08-20 | 2026-08-20 | Working |
| validation_results | Validation audit log | id (UUID) | run_id | — | — | created_at | run_id | metadata_json | 0 | — | — | Not populated |
| quarantine_rows | Rejected records | id (UUID) | run_id, raw_artifact_id | — | — | created_at | run_id | raw_data_json | **0** | — | — | Empty — validation passes everything? |
| retry_queue | Failed task retry | id (UUID) | run_id | — | status | created_at, updated_at | run_id | metadata_json | 0 | — | — | Not used by pipelines |
| coverage_snapshots | Daily coverage | id (UUID) | amc_id, scheme_id | (snapshot_date, dataset_type, amc_id, scheme_id) | snapshot_date+type, amc_id, scheme_id | snapshot_date, expected_start/end | — | metadata_json | **0** | — | — | **EMPTY — calculator never run** |
| scheme_coverage | Per-scheme coverage | id (UUID) | scheme_id | (scheme_id, dataset_type) | status, coverage_pct | earliest_source/stored, latest_source/stored, last_gap_check | — | missing_periods_json | **0** | — | — | **EMPTY** |
| amc_coverage | Per-AMC coverage | id (UUID) | amc_id | (amc_id, dataset_type) | coverage_pct | earliest, latest | — | — | **0** | — | — | **EMPTY** |
| dataset_coverage | Global coverage | id (UUID) | — | dataset_type | coverage_pct | global_earliest, global_latest | — | — | **0** | — | — | **EMPTY** |
| coverage_alerts | Quality alerts | id (UUID) | amc_id, scheme_id | — | status, type, scheme_id | created_at, acknowledged_at, resolved_at | — | details_json | **0** | — | — | **EMPTY** |
| ingestion_quality_metrics | Per-run quality | id (UUID) | run_id | run_id | run_id, dataset_type | started_at, finished_at | run_id | errors_by_type, errors_by_provider | **0** | — | — | **EMPTY** |

### Schema Fitness Issues

1. **amcs table empty** — No AMC master data; all downstream FKs (schemes.amc_id, portfolio_snapshots.amc_id) are NULL
2. **Provenance FKs not populated** — `documents.raw_artifact_id`, `nav_history.raw_artifact_id` are NULL
3. **Checksums not stored** — `raw_artifacts.checksum` NULL for all 456 records; `documents.checksum` NULL
4. **Scheme fragmentation** — 7,622 NAV schemes (placeholder names, has scheme_code) vs 154 portfolio schemes (real names, no scheme_code) — no reconciliation
5. **Missing debt fields** — `portfolio_holdings` has columns for coupon, maturity_date, rating, asset_class but all empty
6. **Sector column misused** — Stores credit rating, not industry sector
7. **Coverage tables exist but empty** — Calculator implemented but never invoked in pipelines

---

## E. Live Data Audit (PostgreSQL Evidence)

### NAV Data (nav_history)

- **Total records:** 7,468
- **Unique scheme_codes:** 7,468 (1:1 — only latest NAV per scheme)
- **Date range:** 2026-07-30 to 2026-08-20 (22 calendar days, ~15 business days)
- **AMCs:** Unknown (amc_id NULL, scheme_name = "Scheme XXXXX")
- **Duplicate observations:** 0 (unique constraint enforced)
- **Conflicting observations:** 0
- **Unmapped schemes:** 7,468 (all — no AMC linkage)
- **Missing periods:** Cannot assess — only 22-day window

### Portfolio Data (portfolio_snapshots + portfolio_holdings)

- **Total snapshots:** 836
- **Total holdings:** 224,422
- **Unique schemes:** 154
- **Date range:** 2013-03-31 to 2026-08-21
- **AMCs represented (by scheme name prefix):**
  - ICICI Prudential: ~45 schemes, 106K+ holdings (dominant)
  - Aditya Birla Sun Life: ~40 schemes, 50K+ holdings
  - Mirae Asset: ~2 schemes
  - DSP: ~2 schemes
  - Invesco: ~3 schemes
  - PPFAS: ~7 schemes
  - Groww: ~35 schemes
  - Others: parsing artifacts ("dfltr", "Portfolio as of...")
- **Reporting periods per scheme:** Up to 47 (DSP Liquidity Fund: 2020-09 to 2026-07)
- **ISIN coverage:** 27.5% (61,683 / 224,422)
- **Sector coverage:** 23.1% (51,789 / 224,422) — actually credit ratings
- **% to NAV coverage:** 48.9% (109,729 / 224,422)
- **Market value coverage:** 48.0% (107,828 / 224,422)
- **Rating coverage:** 0% (stored in sector column)
- **Coupon/Maturity/Asset Class:** 0%
- **Duplicate snapshots:** 0 (unique constraint enforced)
- **Duplicate holdings:** Hundreds — "Total", "Sub Total", "Direct Plan", "Monthly IDCW Option" section headers stored as holdings
- **Unmapped schemes:** 154 (no AMC linkage, no scheme_code)
- **Quarantined rows:** 0

### Scheme Identity Audit

- **NAV schemes (7,622):** Have `scheme_code` (e.g., "120503"), placeholder `scheme_name` ("Scheme 120503"), NULL `amc_id`
- **Portfolio schemes (154):** Have real `scheme_name` ("ICICI Prudential Liquid Fund"), NULL `scheme_code`, NULL `amc_id`
- **Overlap:** Unknown — no reconciliation performed
- **Direct/Regular collisions:** Not tracked (plan/option in metadata_json only for portfolio schemes)
- **Growth/IDCW collisions:** Not tracked
- **AMFI code inconsistencies:** NAV schemes have codes; portfolio schemes don't

### Instrument Identity

- **Total instruments:** 182,018
- **With ISIN:** ~61K unique ISINs (but many duplicates in holdings point to same instrument)
- **Invalid ISINs:** "Nil" (1,267 holdings), "(Short)" (273 holdings) — parsing artifacts
- **ISIN deduplication:** Working (unique constraint on instruments.isin)

---

## F. Data-Loss Audit

### Source Fields vs. Database Fields

#### NAV (AMFI 8-column format: NAVAll.txt)

| Source Column | In Parser Output? | In DB Column? | Preserved? |
|---------------|-------------------|---------------|------------|
| Scheme Code | ✅ | ✅ scheme_code | ✅ |
| ISIN Div Payout | ✅ Detected in header | ❌ | ❌ **LOST** |
| ISIN Div Reinvestment | ✅ Detected in header | ❌ | ❌ **LOST** |
| Scheme Name | ✅ Detected in header | ❌ | ❌ **LOST** |
| Plan | ✅ Detected in header | ❌ | ❌ **LOST** |
| Option | ✅ Detected in header | ❌ | ❌ **LOST** |
| Net Asset Value | ✅ | ✅ nav_value | ✅ |
| Date | ✅ | ✅ nav_date | ✅ |

#### Portfolio (Excel columns from real files)

| Source Column (aliases) | In Parser Output? | In DB Column? | Preserved? |
|------------------------|-------------------|---------------|------------|
| Name of Instrument / Security | ✅ | ✅ security_name | ✅ |
| ISIN | ✅ | ✅ isin | ✅ |
| Quantity / No. of Shares / Units | ✅ Parsed | ❌ **No DB column** | ❌ **LOST** |
| Market Value (Rs. in Lakhs) | ✅ | ✅ market_value | ✅ |
| % to NAV / % Net Assets | ✅ | ✅ percentage_to_nav | ✅ |
| Industry / Sector / Rating | ✅ | ✅ sector (← **rating**) | ⚠️ **MISMAPPED** |
| Rating / Credit Rating | ✅ Parsed as "rating" | ❌ **No DB column** | ❌ **LOST** (except in sector) |
| Coupon / Coupon Rate / YTM | ✅ Parsed | ❌ **No DB column** | ❌ **LOST** |
| Maturity / Maturity Date | ✅ Parsed | ❌ **No DB column** | ❌ **LOST** |
| Asset Class / Type | ✅ Parsed | ❌ **No DB column** | ❌ **LOST** |
| Any other columns | ❌ Ignored | ❌ | ❌ **LOST** |

#### Fields with NO Database Destination (Data Loss Confirmed)

1. **NAV:** ISIN Div Payout, ISIN Div Reinvestment, Scheme Name, Plan, Option
2. **Portfolio:** Quantity, Rating (separate from sector), Coupon, Maturity Date, Asset Class
3. **All:** Any column not in `COLUMN_ALIASES` — silently dropped

#### Fields in DB but Empty

- `portfolio_holdings.asset_class` — 0 records
- `portfolio_holdings.coupon` — 0 records
- `portfolio_holdings.maturity_date` — 0 records
- `portfolio_holdings.rating` — 0 records (rating stored in `sector`)
- `instruments.instrument_type` — 0 populated
- `instruments.issuer` — 0 populated

---

## G. Provenance Audit

### Traceability Test Results

| Trace Path | Result | Evidence |
|------------|--------|----------|
| portfolio_holding → portfolio_snapshot | ✅ Works | `snapshot_id` FK populated |
| portfolio_snapshot → document | ✅ Works | `document_id` FK populated |
| document → raw_artifact | ❌ **BROKEN** | `documents.raw_artifact_id` = NULL for all 836 |
| document → checksum | ❌ **BROKEN** | `documents.checksum` = NULL for all 836 |
| nav_history → raw_artifact | ❌ **BROKEN** | `nav_history.raw_artifact_id` = NULL for all 7,468 |
| raw_artifact → ingestion_run | ✅ Works | `raw_artifacts.run_id` populated |
| raw_artifact → checksum | ❌ **BROKEN** | `raw_artifacts.checksum` = NULL for all 456 |
| raw_artifact → source URL | ✅ Works | `raw_artifacts.source_url` populated |
| raw_artifact → fetch timestamp | ✅ Works | `raw_artifacts.fetch_timestamp` populated |
| holding → instrument (ISIN) | ✅ Works | `instrument_id` FK for ISIN-matched holdings |

### Provenance Gap Analysis

The provenance chain is **broken at the document/raw_artifact boundary**. The `upsert_portfolio` method in `upserts.py` creates a `Document` record but does not link it to the `RawArtifact`. The `raw_artifact_id` is available in the processor but not passed to the document upsert.

**Impact:** Cannot audit a canonical row back to the exact source file, its checksum, or verify it hasn't been tampered with.

---

## H. Coverage Audit

### Coverage System Status

- **All 6 coverage tables EMPTY** — `CoverageCalculator.update_all_coverage()` never called
- **No coverage snapshots** — No daily, scheme, AMC, or dataset-level metrics
- **No alerts generated** — `coverage_alerts` empty
- **No quality metrics** — `ingestion_quality_metrics` empty

### Expected vs Actual Coverage (Manual Calculation)

| Dataset | Expected Granularity | Actual Data | Coverage Reality |
|---------|---------------------|-------------|------------------|
| nav_history | Daily (business days) | 15 business days for 7,468 schemes | ~100% for 22-day window; 0% for history |
| portfolio_disclosure | Monthly (equity) / Fortnightly (debt) | 836 snapshots, 154 schemes | ICICI: 20 fortnightly periods (Oct 2025-Aug 2026); DSP: 47 monthly (2020-2026); others: 1-3 |

### Coverage Calculator Logic Issues

1. **NAV gap detection** assumes business days Mon-Fri — correct for Indian markets
2. **Portfolio gap detection** assumes monthly periods — **incorrect for fortnightly debt disclosures** (ICICI, DSP are fortnightly)
3. **No weekend/holiday calendar** — Indian market holidays not accounted for
4. **Scheme status not tracked** — Discontinued/merged schemes treated as "missing"

---

## I. Storage Audit

### Current Disk Usage (Raw/Downloaded Files)

| Location | Size | Purpose | Safe to Delete? | Still Required? |
|----------|------|---------|-----------------|-----------------|
| `data/raw/mutual_funds/source_registry/` | ~100 KB | Phase 1A JSON artifacts | No | Yes (source of truth) |
| `data/raw/mutual_funds/provider_profiles/` | ~65 KB | Phase 1B JSON artifacts | No | Yes (strategy registry) |
| `data/debug/mutual_funds/provider_profiles/*/` | ~50 MB | HTML, screenshots, network logs from profiling | **Yes (after review)** | No (debug only) |
| `data/reports/mutual_funds/` | ~1 MB | HTML/CSV reports | No | Yes (human review) |
| `data/raw/mutual_funds/artifacts/` | **Does not exist** | Raw downloaded files (per new storage policy) | N/A | N/A |
| `/tmp/mf_portfolio/` | **Does not exist** | ArtifactCollector temp directory | N/A | N/A |
| PostgreSQL `raw_artifacts.local_path` | 456 records | Paths to downloaded files | **Paths invalid** — files not on disk | **Files deleted after ingestion** (current behavior) |

### Storage Policy Compliance

**Current behavior (from `ArtifactCollector`):** Downloads to temp, parses, **does NOT retain raw files by default** (`keep_raw_files=False`). This **matches the desired policy** — raw files are not permanently stored.

**However:** `raw_artifacts` table has 456 records with `local_path` pointing to temp files that no longer exist, and `checksum=NULL`, `retained=False`. The metadata exists but the content is gone (by design). For failed ingestions, files are also not retained (`keep_failed_raw_files=True` in config but not implemented).

**Gap:** `raw_artifacts.checksum` is NULL — deduplication cannot work. The `ArtifactStorageManager` computes SHA256 but the legacy `ArtifactCollector` does not populate it.

---

## J. Required Fixes (Prioritized)

### P0 — Correctness / Data-Loss / Data-Identity Issues

| # | Issue | Fix | Effort |
|---|-------|-----|--------|
| P0-1 | **AMC table empty** — No AMC master data; all FKs NULL | Load AMCs from `configs/amc_sources.yaml` into `amcs` table; run on `init-db` | 1 day |
| P0-2 | **Provenance chain broken** — `documents.raw_artifact_id`, `documents.checksum`, `nav_history.raw_artifact_id`, `raw_artifacts.checksum` all NULL | Fix `upserts.py` to link Document to RawArtifact; populate checksum in ArtifactCollector; pass raw_artifact_id through pipeline | 2 days |
| P0-3 | **Scheme identity fragmentation** — 7,622 NAV schemes vs 154 portfolio schemes, no reconciliation | Run `SchemeIdentityResolver` to merge; populate `scheme_code` for portfolio schemes via name matching; populate `amc_id` for all schemes | 2 days |
| P0-4 | **Debt fields not captured** — rating, coupon, maturity_date, asset_class, quantity all lost | Add columns to parser output; ensure `portfolio_holdings` upsert includes them; fix `COLUMN_ALIASES` mapping | 1 day |
| P0-5 | **Sector column misused** — Stores credit rating, not industry sector | Add `rating` column to `portfolio_holdings` (or use existing `rating` col); keep `sector` for industry; backfill from existing data | 1 day |
| P0-6 | **Invalid ISINs in instruments** — "Nil", "(Short)" stored | Add ISIN validation regex (12 alphanumeric); reject/quarantine invalid ISINs | 0.5 days |
| P0-7 | **Duplicate holdings (section headers)** — "Total", "Sub Total", "Direct Plan" stored as holdings | Filter out rows where `security_name` matches section header patterns in parser or validation | 0.5 days |
| P0-8 | **NAV parser drops 5 fields** — ISINs, scheme_name, plan, option not in output | Extend `parse_nav_text` output records to include all 8 columns | 0.5 days |

### P1 — Missing Major Ingestion Capability

| # | Issue | Fix | Effort |
|---|-------|-----|--------|
| P1-1 | **Scheme Master Monthly parser missing** — `scheme_master_excel_v1` needed for AMFI Monthly .xls/.xlsx | Implement Excel parser for scheme master (handles .xls via xlrd, .xlsx via openpyxl); map all columns | 2 days |
| P1-2 | **TER parser missing** — `ter_excel_v1` needed for AMFI TER data | Implement TER Excel parser; capture BER, brokerage, transaction cost, statutory levies breakdown | 2 days |
| P1-3 | **AUM parser missing** — `aum_excel_v1` needed for AMFI AUM datasets | Implement AUM Excel parser for category/geography/scheme-wise AUM | 2 days |
| P1-4 | **Coverage calculator not integrated** — Tables exist but never populated | Call `CoverageCalculator.update_all_coverage()` at end of each pipeline run; schedule daily | 1 day |
| P1-5 | **Historical NAV backfill not run** — Only 22 days of data | Run `NAVPipeline.run_backfill(start_date=2020-01-01)`; handle 90-day window iteration | 1 day (runtime: hours) |
| P1-6 | **47 AMCs not profiled/ingested** — Only 6 of 53 working | Use capability matrix to prioritize; deploy navigators for remaining | Ongoing |

### P2 — Quality / Coverage / Maintainability

| # | Issue | Fix | Effort |
|---|-------|-----|--------|
| P2-1 | **Raw artifact checksums not computed** — Deduplication broken | Fix `ArtifactCollector.download()` to compute SHA256; populate `raw_artifacts.checksum` | 0.5 days |
| P2-2 | **Validation results not written** — `validation_results` table empty | Ensure `UpsertManager.write_validation_result()` called in `ArtifactProcessor` | 0.5 days |
| P2-3 | **Retry queue not used** — Failed tasks not retried automatically | Integrate `retry_queue` processing in pipeline runners | 1 day |
| P2-4 | **Portfolio gap detection assumes monthly** — Incorrect for fortnightly | Enhance `PortfolioPipeline.detect_gaps()` to use scheme frequency from metadata | 1 day |
| P2-5 | **No Indian holiday calendar** — Gap detection marks holidays as missing | Add NSE/BSE holiday calendar; exclude from expected periods | 1 day |
| P2-6 | **Instrument enrichment missing** — issuer, instrument_type, sector not populated | Populate from holding data (sector→industry, rating→separate col) or external reference | 1 day |

### P3 — Optional Improvements

| # | Issue | Fix | Effort |
|---|-------|-----|--------|
| P3-1 | **GCS/Azure storage backends** — Extensible design exists, not implemented | Implement `GCSBackend`, `AzureBlobBackend` | 2 days |
| P3-2 | **Unified orchestrator CLI** — Pipelines run independently | Create single CLI commanding all pipelines | 1 day |
| P3-3 | **Prometheus/Grafana metrics export** | Add `/metrics` endpoint or pushgateway | 1 day |
| P3-4 | **Scheme merge/rename handling** — Identity layer tracks but doesn't auto-merge | Implement scheme lineage tracking in `SchemeMappingManager` | 2 days |
| P3-5 | **VLM integration for complex sites** — Ollama backend exists, not used in production | Enable VLM for Aditya Birla, HDFC, others | 1 day |

---

## Validation Commands (Run to Verify Fixes)

```bash
# 1. Verify AMC table populated
PGPASSWORD=vlmrouter psql -h localhost -U vlmrouter -d mutual_funds -c "SELECT count(*) FROM amcs;"

# 2. Verify provenance chain
PGPASSWORD=vlmrouter psql -h localhost -U vlmrouter -d mutual_funds -c "
SELECT d.id, d.raw_artifact_id, d.checksum, ra.checksum as artifact_checksum
FROM documents d
LEFT JOIN raw_artifacts ra ON d.raw_artifact_id = ra.id
WHERE d.document_type = 'portfolio_disclosure'
LIMIT 10;
"

# 3. Verify scheme linkage
PGPASSWORD=vlmrouter psql -h localhost -U vlmrouter -d mutual_funds -c "
SELECT COUNT(*) as total, COUNT(amc_id) as with_amc, COUNT(scheme_code) as with_code
FROM schemes;
"

# 4. Verify debt fields populated
PGPASSWORD=vlmrouter psql -h localhost -U vlmrouter -d mutual_funds -c "
SELECT 
  COUNT(*) as total,
  COUNT(rating) as with_rating,
  COUNT(coupon) as with_coupon,
  COUNT(maturity_date) as with_maturity,
  COUNT(asset_class) as with_asset_class
FROM portfolio_holdings;
"

# 5. Verify coverage tables populated
PGPASSWORD=vlmrouter psql -h localhost -U vlmrouter -d mutual_funds -c "
SELECT 'dataset_coverage' as t, count(*) FROM dataset_coverage
UNION ALL SELECT 'scheme_coverage', count(*) FROM scheme_coverage
UNION ALL SELECT 'amc_coverage', count(*) FROM amc_coverage
UNION ALL SELECT 'coverage_snapshots', count(*) FROM coverage_snapshots
UNION ALL SELECT 'coverage_alerts', count(*) FROM coverage_alerts;
"

# 6. Run full test suite
./financial_env/bin/python -m pytest tests/ -v --tb=short
# Target: ≥148 passed, 3 skipped (7 pre-existing failures)
```

---

## Documentation Updates Required

| Document | Required Update |
|----------|-----------------|
| `docs/02_architecture/database_schema.md` | Document actual table state (P0 fixes), add missing FKs, note empty tables |
| `docs/02_architecture/system_overview.md` | Update pipeline status (which are production-proven vs catalogued) |
| `docs/02_architecture/codebase_map.md` | Add P0/P1 modules, update parser registry status |
| `docs/01_status/MASTER_STATE.md` | Update test baseline, feature completion map, known blockers |
| `configs/amfi_dataset_census.yaml` | Update `parser_status` for each dataset (implemented/partial/not_implemented) |
| `configs/amc_capability_matrix.yaml` | Update working status for 6 AMCs; add parser_version, last_verified |
| `docs/06_plans/active/STORY_NOTEBOOK_SERIES_PLAN.md` | Add audit findings notebook task |
| `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb` | Update with actual DB state from this audit |

---

## Conclusion

The mutual fund ingestion system has **strong architectural foundations** — layered design, specialized pipelines, scheme identity, artifact storage, coverage framework — but **critical data integrity gaps** prevent it from being a trustworthy production system:

1. **No AMC master data** — The foundation for all attribution is missing
2. **Broken provenance** — Cannot audit any canonical record to its source
3. **Fragmented scheme identity** — Two disconnected scheme populations
4. **Incomplete field capture** — Debt-specific fields, NAV metadata, quantities all lost
5. **Coverage system inert** — Dashboards would show zeros

**Immediate priority:** Fix P0 issues (1-2 weeks) to establish data integrity baseline. Then run historical backfills (P1-5) to populate meaningful coverage. The 6 working AMCs prove the pipeline architecture works — the gaps are in data completeness and provenance, not pipeline design.
