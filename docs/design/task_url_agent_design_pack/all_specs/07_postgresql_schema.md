# 07 — PostgreSQL Schema

## Schema Philosophy

Use PostgreSQL with normalized canonical tables and flexible JSONB metadata.

The schema should evolve as new datasets are discovered. Do not overfit to one website format.

All parsed data should pass through staging before canonical loading.

## Minimum Required Tables

```text
ingestion_runs
task_urls
source_pages
discovered_links
source_entities
dataset_candidates
raw_artifacts
documents
amcs
schemes
scheme_aliases
nav_history
portfolio_snapshots
portfolio_holdings
instruments
sector_allocations
staging_rows
validation_results
quarantine_rows
retry_queue
```

## Discovery and Provenance Tables

### ingestion_runs

```sql
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    pages_seen INTEGER NOT NULL DEFAULT 0,
    files_seen INTEGER NOT NULL DEFAULT 0,
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    error_summary JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

### task_urls

```sql
CREATE TABLE IF NOT EXISTS task_urls (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### source_pages

```sql
CREATE TABLE IF NOT EXISTS source_pages (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    url TEXT NOT NULL,
    canonical_url TEXT,
    parent_url TEXT,
    domain TEXT,
    title TEXT,
    status_code INTEGER,
    content_type TEXT,
    page_relevance TEXT,
    source_authority_type TEXT,
    html_snapshot_path TEXT,
    screenshot_path TEXT,
    network_log_path TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### discovered_links

```sql
CREATE TABLE IF NOT EXISTS discovered_links (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    source_page_id UUID REFERENCES source_pages(id),
    url TEXT NOT NULL,
    anchor_text TEXT,
    link_type TEXT,
    dataset_type_hint TEXT,
    file_type_hint TEXT,
    should_follow BOOLEAN NOT NULL DEFAULT false,
    relevance_score NUMERIC,
    reason TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### dataset_candidates

```sql
CREATE TABLE IF NOT EXISTS dataset_candidates (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    source_page_id UUID REFERENCES source_pages(id),
    url TEXT NOT NULL,
    dataset_type TEXT,
    provider_hint TEXT,
    download_method TEXT,
    file_type TEXT,
    requires_browser BOOLEAN NOT NULL DEFAULT false,
    requires_form BOOLEAN NOT NULL DEFAULT false,
    requires_vlm BOOLEAN NOT NULL DEFAULT false,
    confidence NUMERIC,
    status TEXT NOT NULL DEFAULT 'discovered',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### raw_artifacts

```sql
CREATE TABLE IF NOT EXISTS raw_artifacts (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    dataset_candidate_id UUID REFERENCES dataset_candidates(id),
    source_url TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    file_type TEXT,
    content_type TEXT,
    checksum TEXT,
    size_bytes BIGINT,
    local_path TEXT,
    retained BOOLEAN NOT NULL DEFAULT false,
    fetch_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

## Canonical Financial Tables

### amcs

```sql
CREATE TABLE IF NOT EXISTS amcs (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    amfi_code TEXT,
    website_url TEXT,
    source_url TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(normalized_name)
);
```

### schemes

```sql
CREATE TABLE IF NOT EXISTS schemes (
    id UUID PRIMARY KEY,
    amc_id UUID REFERENCES amcs(id),
    scheme_code TEXT,
    scheme_name TEXT NOT NULL,
    normalized_scheme_name TEXT NOT NULL,
    category TEXT,
    sub_category TEXT,
    scheme_type TEXT,
    benchmark TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(scheme_code)
);
```

### nav_history

```sql
CREATE TABLE IF NOT EXISTS nav_history (
    id UUID PRIMARY KEY,
    scheme_id UUID REFERENCES schemes(id),
    scheme_code TEXT NOT NULL,
    nav_date DATE NOT NULL,
    nav_value NUMERIC NOT NULL,
    repurchase_price NUMERIC,
    sale_price NUMERIC,
    source_url TEXT NOT NULL,
    raw_artifact_id UUID REFERENCES raw_artifacts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(scheme_code, nav_date)
);
```

### documents

```sql
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    raw_artifact_id UUID REFERENCES raw_artifacts(id),
    document_type TEXT NOT NULL,
    amc_id UUID REFERENCES amcs(id),
    scheme_id UUID REFERENCES schemes(id),
    reporting_date DATE,
    source_url TEXT NOT NULL,
    file_type TEXT,
    checksum TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### instruments

```sql
CREATE TABLE IF NOT EXISTS instruments (
    id UUID PRIMARY KEY,
    isin TEXT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    instrument_type TEXT,
    issuer TEXT,
    sector TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### portfolio_snapshots

```sql
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY,
    amc_id UUID REFERENCES amcs(id),
    scheme_id UUID REFERENCES schemes(id),
    reporting_date DATE NOT NULL,
    document_id UUID REFERENCES documents(id),
    source_url TEXT NOT NULL,
    parser_version TEXT,
    validation_status TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### portfolio_holdings

```sql
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id UUID PRIMARY KEY,
    snapshot_id UUID NOT NULL REFERENCES portfolio_snapshots(id),
    instrument_id UUID REFERENCES instruments(id),
    security_name TEXT NOT NULL,
    isin TEXT,
    sector TEXT,
    asset_class TEXT,
    quantity NUMERIC,
    market_value NUMERIC,
    market_value_currency TEXT DEFAULT 'INR',
    percentage_to_nav NUMERIC,
    coupon NUMERIC,
    maturity_date DATE,
    rating TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Staging and Failure Tables

### staging_rows

```sql
CREATE TABLE IF NOT EXISTS staging_rows (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    raw_artifact_id UUID REFERENCES raw_artifacts(id),
    document_id UUID REFERENCES documents(id),
    dataset_type TEXT NOT NULL,
    sheet_name TEXT,
    row_number INTEGER,
    raw_row_json JSONB NOT NULL,
    parsed_fields_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    parser_name TEXT,
    parser_confidence NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### validation_results

```sql
CREATE TABLE IF NOT EXISTS validation_results (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    entity_type TEXT NOT NULL,
    entity_id UUID,
    check_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### quarantine_rows

```sql
CREATE TABLE IF NOT EXISTS quarantine_rows (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    raw_artifact_id UUID REFERENCES raw_artifacts(id),
    dataset_type TEXT,
    reason TEXT NOT NULL,
    raw_data_json JSONB,
    parser_error TEXT,
    retryable BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### retry_queue

```sql
CREATE TABLE IF NOT EXISTS retry_queue (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    url TEXT NOT NULL,
    task_type TEXT NOT NULL,
    failure_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Indexes

Add indexes on:

```text
source_pages(run_id)
source_pages(domain)
discovered_links(run_id)
dataset_candidates(dataset_type)
raw_artifacts(checksum)
amcs(normalized_name)
schemes(scheme_code)
schemes(normalized_scheme_name)
nav_history(scheme_code, nav_date)
portfolio_snapshots(scheme_id, reporting_date)
portfolio_holdings(isin)
portfolio_holdings(security_name)
retry_queue(status)
```
