# Database Schema — Mutual Fund Ingestion System (Updated)

_Updated: 2026-08-21. Source: `mutual_fund_ingestion/agent/db.py` + `coverage.py` — 20 SQLAlchemy tables._

---

## Database Connection

- **Host:** `localhost`
- **Port:** `5432`
- **Driver:** PostgreSQL 18 (pgvector)
- **Verified URL:** `postgresql://vlmrouter:***@localhost:5432/mutual_funds`
- **CLI init:** `python -m mutual_fund_ingestion init-db --database-url postgresql://vlmrouter:***@localhost:5432/mutual_funds`

---

## Table Inventory

### Core Canonical Tables (1–7)

#### 1. `ingestion_runs`

**Purpose:** Top-level record for each agent run. Tracks overall run status, counts, and error summary.
**Key columns:** `id` (UUID, PK), `started_at`, `finished_at`, `status` (running/completed/failed), `config_json`, `pages_seen`, `files_seen`, `rows_inserted`, `rows_rejected`, `error_summary` (JSON)

#### 2. `task_urls`

**Purpose:** Input URLs provided to the agent run.
**Key columns:** `run_id` (FK → ingestion_runs), `url`, `status` (pending/completed/failed), `notes`

#### 3. `source_pages`

**Purpose:** Every HTTP page the discovery engine fetched.
**Key columns:** `run_id` (FK), `url`, `canonical_url`, `parent_url`, `domain`, `status_code`, `page_relevance`, `html_snapshot_path`, `screenshot_path`
**Indexes:** `ix_source_pages_run_id`, `ix_source_pages_domain`

#### 4. `discovered_links`

**Purpose:** Every URL extracted from HTML `<a>` tags on a source page.
**Key columns:** `run_id` (FK), `source_page_id` (FK), `url`, `anchor_text`, `link_type`, `dataset_type_hint`, `file_type_hint`, `should_follow`, `relevance_score`, `reason`
**Indexes:** `ix_discovered_links_run_id`

#### 5. `dataset_candidates`

**Purpose:** High-relevance file URLs flagged for download.
**Key columns:** `run_id` (FK), `source_page_id` (FK), `url`, `dataset_type`, `provider_hint`, `download_method`, `file_type`, `requires_browser`, `requires_form`, `requires_vlm`, `confidence`, `status`
**Status flow:** `discovered` → `downloaded` → `processed` / `download_failed` / `parse_failed` / `no_parser`
**Indexes:** `ix_dataset_candidates_dataset_type`
**Dataset types:** `nav_history`, `portfolio_disclosure`, `scheme_master`, `amc_provider_list`, `factsheet`, `sid`, `kim`, `ter`, `aum`

#### 6. `raw_artifacts`

**Purpose:** Raw downloaded file metadata and retention tracking.
**Key columns:** `run_id` (FK), `dataset_candidate_id` (FK), `source_url`, `artifact_type`, `file_type`, `checksum` (SHA256), `size_bytes`, `local_path`, `retained` (bool), `fetch_timestamp`
**Indexes:** `ix_raw_artifacts_checksum`

#### 7. `amcs`

**Purpose:** Canonical AMC (Asset Management Company) records.
**Key columns:** `id` (UUID, PK), `name`, `normalized_name` (unique — used for upsert), `amfi_code`, `website_url`, `source_url`
**Indexes:** `ix_amcs_normalized_name` (unique)

---

### Scheme & NAV Tables (8–9)

#### 8. `schemes`

**Purpose:** Canonical scheme (mutual fund plan) records.
**Key columns:** `amc_id` (FK → amcs), `scheme_code` (unique), `scheme_name`, `normalized_scheme_name`, `category`, `sub_category`, `scheme_type`, `benchmark`
**Indexes:** `ix_schemes_scheme_code` (unique), `ix_schemes_normalized_sname`

#### 9. `nav_history`

**Purpose:** Daily NAV (Net Asset Value) records per scheme — the core time-series data.
**Key columns:** `scheme_id` (FK → schemes), `scheme_code`, `nav_date`, `nav_value` (Numeric), `repurchase_price`, `sale_price`, `source_url`, `raw_artifact_id` (FK)
**Indexes:** `ix_nav_history_scheme_code_nav_date`, `uq_nav_history_scheme_code_nav_date` (unique)
**Notes:** Unique constraint `(scheme_code, nav_date)` enables `ON CONFLICT DO UPDATE` upserts.

---

### Document & Portfolio Tables (10–13)

#### 10. `documents`

**Purpose:** Abstract document record linking a raw artifact to a reporting entity.
**Key columns:** `raw_artifact_id` (FK), `document_type`, `amc_id` (FK), `scheme_id` (FK), `reporting_date`, `source_url`, `file_type`, `checksum`

#### 11. `instruments`

**Purpose:** Securities referenced in portfolio holdings. Looked up by ISIN.
**Key columns:** `isin` (nullable), `name`, `normalized_name`, `instrument_type`, `issuer`, `sector`

#### 12. `portfolio_snapshots`

**Purpose:** One portfolio disclosure event — one date, one scheme, one document.
**Key columns:** `amc_id` (FK), `scheme_id` (FK), `reporting_date`, `document_id` (FK), `source_url`, `parser_version`, `validation_status`
**Indexes:** `ix_portfolio_snapshots_scheme_id_reporting_date`

#### 13. `portfolio_holdings`

**Purpose:** Individual securities in a portfolio snapshot.
**Key columns:** `snapshot_id` (FK), `instrument_id` (FK), `security_name`, `isin`, `sector`, `asset_class`, `quantity`, `market_value`, `market_value_currency` (default INR), `percentage_to_nav`, `coupon`, `maturity_date`, `rating`
**Indexes:** `ix_portfolio_holdings_isin`, `ix_portfolio_holdings_security_name`

---

### Staging & Quality Tables (14–17)

#### 14. `staging_rows`

**Purpose:** Pre-validation parsed records. Every row from every parsed file.
**Key columns:** `run_id` (FK), `raw_artifact_id` (FK), `document_id` (FK), `dataset_type`, `sheet_name`, `row_number`, `raw_row_json`, `parsed_fields_json`, `parser_name`, `parser_confidence`

#### 15. `validation_results`

**Purpose:** Audit log of every validation check run on every record.
**Key columns:** `run_id` (FK), `entity_type`, `entity_id`, `check_name`, `severity` (info/warning/error), `status` (passed/failed), `message`

#### 16. `quarantine_rows`

**Purpose:** Rejected records that failed validation. Stored with reason for triage.
**Key columns:** `run_id` (FK), `raw_artifact_id` (FK), `dataset_type`, `reason`, `raw_data_json`, `parser_error`, `retryable`
**Reason codes:** `missing_scheme_code`, `nav_value_not_positive`, `unsupported_dataset_type`, `unknown_schema`, etc.

#### 17. `retry_queue`

**Purpose:** Failed tasks eligible for retry. Consumed by `retry-failed` CLI.
**Key columns:** `run_id` (FK), `url`, `task_type` (fetch/download/parse), `failure_reason`, `retry_count`, `next_retry_at`, `status` (pending/retrying/completed/failed), `retryable`
**Indexes:** `ix_retry_queue_status`

---

### Coverage & Quality Tables (18–22) — NEW

#### 18. `coverage_snapshots`

**Purpose:** Daily coverage snapshot for the entire dataset at multiple granularities.
**Key columns:** `snapshot_date`, `dataset_type`, `amc_id` (FK), `scheme_id` (FK), `expected_count`, `actual_count`, `missing_count`, `coverage_pct`, `earliest_date`, `latest_date`, `expected_start`, `expected_end`
**Unique constraint:** `(snapshot_date, dataset_type, amc_id, scheme_id)`
**Indexes:** `ix_coverage_snapshot_date_type`, `ix_coverage_snapshot_amc`, `ix_coverage_snapshot_scheme`

#### 19. `scheme_coverage`

**Purpose:** Per-scheme coverage tracking for each dataset type.
**Key columns:** `scheme_id` (FK, unique per dataset_type), `dataset_type`, `earliest_source_date`, `latest_source_date`, `earliest_stored_date`, `latest_stored_date`, `expected_observations`, `stored_observations`, `missing_observations`, `coverage_pct`, `missing_periods_json`, `last_gap_check`, `status` (active/discontinued/merged/missing)
**Unique constraint:** `(scheme_id, dataset_type)`
**Indexes:** `ix_scheme_coverage_status`, `ix_scheme_coverage_pct`

#### 20. `amc_coverage`

**Purpose:** Per-AMC coverage aggregation for each dataset type.
**Key columns:** `amc_id` (FK, unique per dataset_type), `dataset_type`, `total_schemes`, `schemes_with_data`, `total_expected`, `total_stored`, `total_missing`, `coverage_pct`, `earliest_date`, `latest_date`
**Unique constraint:** `(amc_id, dataset_type)`
**Indexes:** `ix_amc_coverage_pct`

#### 21. `dataset_coverage`

**Purpose:** Global dataset-level coverage summary.
**Key columns:** `dataset_type` (unique), `total_amcs`, `total_schemes`, `total_expected`, `total_stored`, `total_missing`, `coverage_pct`, `global_earliest`, `global_latest`, `amcs_complete`, `amcs_partial`, `amcs_minimal`, `amcs_empty`
**Indexes:** `ix_dataset_coverage_pct`

#### 22. `coverage_alerts`

**Purpose:** Automated alerts for coverage issues.
**Key columns:** `alert_type` (gap_detected/coverage_drop/new_scheme_missing/stale_data), `severity` (info/warning/critical), `dataset_type`, `amc_id` (FK), `scheme_id` (FK), `message`, `details_json`, `status` (open/acknowledged/resolved), `acknowledged_by`, `acknowledged_at`, `resolved_at`
**Indexes:** `ix_coverage_alert_status`, `ix_coverage_alert_type`, `ix_coverage_alert_scheme`

#### 23. `ingestion_quality_metrics`

**Purpose:** Quality metrics per ingestion run.
**Key columns:** `run_id` (FK, unique), `dataset_type`, `sources_discovered`, `files_discovered`, `files_downloaded`, `files_skipped_duplicate`, `files_failed`, `artifacts_parsed`, `rows_parsed`, `rows_valid`, `rows_quarantined`, `rows_upserted`, `rows_updated`, `parse_success_rate`, `validation_pass_rate`, `upsert_success_rate`, `errors_by_type`, `errors_by_provider`, `started_at`, `finished_at`, `duration_seconds`
**Indexes:** `ix_quality_metrics_run`, `ix_quality_metrics_dataset`

---

## Upsert Strategy

All canonical tables use PostgreSQL `ON CONFLICT DO UPDATE` (upsert):

| Table | Conflict Key | Notes |
|-------|--------------|-------|
| `amcs` | `normalized_name` | Name normalization dedups AMC duplicates |
| `schemes` | `scheme_code` or `normalized_scheme_name` | `scheme_code` preferred |
| `nav_history` | `(scheme_code, nav_date)` | Composite unique; enables daily refresh |
| `portfolio_snapshots` | `(scheme_id, reporting_date)` | One snapshot per scheme per date |
| `portfolio_holdings` | `(snapshot_id, security_name, isin)` | Handles same security multiple times |
| `coverage_snapshots` | `(snapshot_date, dataset_type, amc_id, scheme_id)` | Daily granularity |
| `scheme_coverage` | `(scheme_id, dataset_type)` | One per scheme per dataset |
| `amc_coverage` | `(amc_id, dataset_type)` | One per AMC per dataset |
| `dataset_coverage` | `dataset_type` | Global singleton per dataset |

---

## Connection Management

```python
from mutual_fund_ingestion.agent.db import create_tables, get_session_maker

# Initialize schema (creates all 23 tables)
create_tables("postgresql://vlmrouter:***@localhost:5432/mutual_funds")

# Create a session
session_maker = get_session_maker("postgresql://vlmrouter:***@localhost:5432/mutual_funds")
session = session_maker()
try:
    # work
    session.commit()
finally:
    session.close()
```

**Tests use SQLite** (`sqlite:///tmp/test.db`). Models are database-agnostic — no PostgreSQL-specific features prevent SQLite compatibility.

---

## Migration Notes

### From 17 to 23 Tables (2026-08-21)

Added coverage and quality tables:
- `coverage_snapshots` — Daily snapshots
- `scheme_coverage` — Per-scheme metrics
- `amc_coverage` — Per-AMC aggregation
- `dataset_coverage` — Global summary
- `coverage_alerts` — Automated alerts
- `ingestion_quality_metrics` — Per-run quality

**Migration approach:** These are additive — no existing tables modified. Run `create_tables()` to add new tables to existing database.

### Scheme Identity

The `schemes` table now supports:
- `scheme_code` (AMFI official code) — primary key
- `metadata_json` stores: `plan`, `option`, `isin_div_payout`, `isin_div_reinvestment`, `source_mappings`
- Foreign key to `amcs` for AMC-scoped resolution

### Raw Artifact Provenance

`raw_artifacts` tracks:
- `checksum` (SHA256) for deduplication
- `local_path` — storage backend path (local/S3)
- `retained` — boolean for retention policy
- `fetch_timestamp` — for tiered retention calculations

---

## Entity Relationship Diagram (Simplified)

```
amcs (1) ────< schemes (>1)
    │              │
    │              ├< nav_history (>1)
    │              ├< portfolio_snapshots (>1)
    │              └< documents (>1)
    │
    ├< amc_coverage (>1)
    └< coverage_alerts (>1)

schemes (1) ──< nav_history
    │
    ├< portfolio_snapshots (>1)
    │      └< portfolio_holdings (>1)
    │              └> instruments (1)
    │
    ├< scheme_coverage (>1)
    └< coverage_alerts (>1)

ingestion_runs (1) ──< task_urls
    ├< source_pages
    ├< discovered_links
    ├< dataset_candidates
    ├< raw_artifacts
    ├< staging_rows
    ├< validation_results
    ├< quarantine_rows
    ├< retry_queue
    ├< coverage_snapshots
    └< ingestion_quality_metrics

raw_artifacts (1) ──< dataset_candidates
    ├< staging_rows
    └< documents
```

---

## Key Queries

### Latest NAV for a Scheme
```sql
SELECT nav_date, nav_value
FROM nav_history
WHERE scheme_code = '120503'
ORDER BY nav_date DESC
LIMIT 1;
```

### Portfolio Holdings for Scheme on Date
```sql
SELECT h.security_name, h.isin, h.percentage_to_nav, h.market_value, h.sector
FROM portfolio_holdings h
JOIN portfolio_snapshots s ON h.snapshot_id = s.id
JOIN schemes sch ON s.scheme_id = sch.id
WHERE sch.scheme_code = '120503' AND s.reporting_date = '2026-06-16';
```

### Coverage Report for AMC
```sql
SELECT dataset_type, total_schemes, schemes_with_data, coverage_pct
FROM amc_coverage
WHERE amc_id = (SELECT id FROM amcs WHERE normalized_name = 'ppfas_mutual_fund');
```

### Schemes with Low NAV Coverage
```sql
SELECT s.scheme_code, s.scheme_name, sc.coverage_pct, sc.missing_observations
FROM scheme_coverage sc
JOIN schemes s ON sc.scheme_id = s.id
WHERE sc.dataset_type = 'nav_history' AND sc.coverage_pct < 50
ORDER BY sc.coverage_pct ASC;
```

### Open Quality Alerts
```sql
SELECT alert_type, severity, message, created_at
FROM coverage_alerts
WHERE status = 'open'
ORDER BY severity DESC, created_at DESC;
```