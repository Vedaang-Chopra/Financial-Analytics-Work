# P0/P1 Fixes Applied - Summary

## P0 Fixes (Critical Data Integrity)

### P0-1: AMC Table Empty ✅ FIXED

- **Script**: `scripts/load_amcs.py`
- **Result**: 55 AMCs loaded from `configs/amc_sources.yaml` into `amcs` table
- **Verification**: `SELECT count(*) FROM amcs;` returns 55

### P0-2: Provenance Chain Broken ✅ FIXED

- **Files Modified**:
  - `mutual_fund_ingestion/agent/upserts.py` - Document upsert now includes `raw_artifact_id` and `checksum`
  - `mutual_fund_ingestion/agent/artifact_processor.py` - Passes checksum to upsert
  - `mutual_fund_ingestion/agent/nav_pipeline.py` - Computes SHA256 checksum for NAV downloads
- **Verification**: Documents now linked to raw artifacts with checksums

### P0-3: Scheme Identity Fragmentation ✅ PARTIALLY FIXED

- **Script**: `scripts/reconcile_schemes.py` + `scripts/populate_scheme_amc.py`
- **Result**:
  - 154 portfolio schemes now have `scheme_code` populated (matched with NAV schemes)
  - 154 portfolio schemes have `amc_id` populated (from source URL domain)
  - 836 portfolio snapshots have `amc_id` populated
  - 7,468 NAV schemes still lack `amc_id` (no scheme_code match with portfolio)

### P0-4: Debt Fields Not Captured ✅ FIXED

- **File Modified**: `mutual_fund_ingestion/agent/parser/portfolio.py`
- **Fields Added**: `rating`, `coupon`, `maturity_date`, `asset_class`, `quantity`
- **Verification**: Parser now extracts all debt-specific columns

### P0-5: Sector Column Misused ✅ FIXED

- **File Modified**: `mutual_fund_ingestion/agent/parser/portfolio.py` + `upserts.py`
- **Fix**: Separated `rating` from `sector` - rating now goes to dedicated `rating` column
- **Verification**: Credit ratings (CRISIL AAA, SOV) now in `rating` column, sector for industry

### P0-6: Invalid ISINs in Instruments ✅ FIXED

- **File Modified**: `mutual_fund_ingestion/agent/parser/portfolio.py`
- **Fix**: Added ISIN regex validation (`^[A-Z]{2}[A-Z0-9]{9}\d$`), rejects "Nil", "(Short)"
- **Verification**: Invalid ISINs filtered out during parsing

### P0-7: Duplicate Holdings (Section Headers) ✅ FIXED

- **File Modified**: `mutual_fund_ingestion/agent/parser/portfolio.py`
- **Fix**: Added `_is_section_header()` to filter out "Total", "Sub Total", "Direct Plan", etc.
- **Verification**: Section headers no longer stored as holdings

### P0-8: NAV Parser Drops 5 Fields ✅ FIXED

- **File Modified**: `mutual_fund_ingestion/agent/parser/nav.py`
- **Fields Added**: `isin_div_payout`, `isin_div_reinvestment`, `scheme_name`, `plan`, `option`
- **Verification**: All 8 AMFI NAVAll.txt columns now extracted

## P1 Fixes (Missing Major Capabilities)

### P1-4: Coverage Calculator Not Integrated ✅ FIXED

- **Files Modified**:
  - `mutual_fund_ingestion/agent/nav_pipeline.py` - Calls `CoverageCalculator.update_all_coverage()`
  - `mutual_fund_ingestion/agent/portfolio_pipeline.py` - Calls `CoverageCalculator.update_all_coverage()`
  - `mutual_fund_ingestion/agent/coverage.py` - Fixed upsert logic with proper ON CONFLICT
  - `mutual_fund_ingestion/agent/db.py` - Added coverage models (CoverageSnapshot, SchemeCoverage, AMCoverage, DatasetCoverage, CoverageAlert, IngestionQualityMetrics)
  - Dropped duplicate unique constraint `amc_coverage_amc_id_key`
- **Result**: Coverage tables now populated
  - `dataset_coverage`: 2 datasets
  - `amc_coverage`: 12 AMC-dataset combinations
  - `coverage_alerts`: 2 alerts for low-coverage schemes
  - `scheme_coverage`: 7,622 scheme records

## Test Results

- **Baseline**: 139 passed, 9 failed (pre-existing: Playwright, DB integration, smoke tests)
- **After Fixes**: 139 passed, 9 failed (no regressions)

## Remaining Issues

### P0-3 (Partial): NAV Schemes Missing AMC ID

- 7,468 NAV schemes still lack `amc_id` because they don't match portfolio schemes by `scheme_code`
- Need to implement fuzzy matching or use AMFI scheme master data

### P1-5: Historical NAV Backfill Not Run

- Only 22 days of NAV data (2026-07-30 to 2026-08-20)
- Need to run `NAVPipeline.run_backfill(start_date=2020-01-01)`

### P1-1/2/3: Missing Parsers

- `scheme_master_excel_v1` - for AMFI Monthly scheme master
- `ter_excel_v1` - for AMFI TER data
- `aum_excel_v1` - for AMFI AUM data

### P2-5: No Indian Holiday Calendar

- Gap detection marks market holidays as missing
- Need NSE/BSE holiday calendar integration
