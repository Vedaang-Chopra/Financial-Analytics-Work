# Data Artifacts and Storage Specification

## Purpose

This document defines where ingestion artifacts should be stored.

The system should preserve raw files, machine-readable metadata, human-readable reports, and debug artifacts separately.

The storage layout should make every phase reproducible and inspectable.

## Root Data Layout

Use this structure unless the existing repository already has a strong convention.

```text
data/
  raw/
    mutual_funds/
      provider_profiles/
      source_registry/
      links/
      files/
  debug/
    mutual_funds/
      provider_profiles/
      crawler_failures/
      playwright/
      vlm/
  reports/
    mutual_funds/
  processed/
    mutual_funds/
```

## Phase 1 Artifact Layout

Phase 1 should write:

```text
configs/amc_sources.yaml
data/raw/mutual_funds/source_registry/source_registry_candidates.jsonl
data/raw/mutual_funds/source_registry/source_registry.latest.json
data/reports/mutual_funds/source_registry_report.html
data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
data/reports/mutual_funds/provider_profile_report.html
data/reports/mutual_funds/provider_profile_summary.csv
data/debug/mutual_funds/provider_profiles/<safe_amc_name>/
```

Phase 1A candidate JSONL preserves source evidence and provenance. The latest
JSON snapshot and YAML registry contain merged entries. YAML and latest
snapshots are written atomically.

Per-AMC debug folder:

```text
data/debug/mutual_funds/provider_profiles/<safe_amc_name>/
  static.html
  rendered.html
  screenshot.png
  network_log.jsonl
  accessibility_snapshot.json
  profiler_error.json
```

Not every file is required for every AMC. Save what is available.

## Future Phase Artifact Layout

Phase 2 document discovery/download:

```text
data/raw/mutual_funds/links/discovered_documents.jsonl
data/raw/mutual_funds/files/<safe_amc_name>/<yyyy-mm>/<filename>
data/raw/mutual_funds/files/<safe_amc_name>/<yyyy-mm>/<filename>.metadata.json
```

Phase 3 classification:

```text
data/processed/mutual_funds/document_classification.jsonl
data/reports/mutual_funds/document_classification_report.html
```

Phase 4 parsing:

```text
data/processed/mutual_funds/staging_portfolio_rows.parquet
data/processed/mutual_funds/parse_runs.jsonl
data/processed/mutual_funds/parse_errors.jsonl
data/reports/mutual_funds/parser_preview_report.html
```

Phase 5+ database artifacts:

```text
data/reports/mutual_funds/db_summary.html
data/reports/mutual_funds/validation_quality_report.html
```

## File Naming Rules

Use deterministic safe names.

Rules:

- lowercase when practical
- replace spaces with underscores
- remove unsafe characters
- include short URL hash when needed
- do not overwrite existing files unless force is supplied

Example:

```text
hdfc_mutual_fund_2026_05_portfolio_disclosure_ab12cd34.xlsx
```

## JSONL Principles

Use JSONL for appendable machine artifacts.

Each line should be valid JSON.

Each record should include:

```text
created_at
source_url
amc_name
run_id
schema_version
```

## Run IDs

Every CLI run should have a run ID.

Suggested format:

```text
YYYYMMDD_HHMMSS_<short_hash>
```

The run ID should appear in:

- logs
- provider profile records
- reports
- debug artifacts

## Raw File Preservation

Never modify raw downloaded files.

If parsed or cleaned versions are needed, write them under `processed/`.

## Debug Artifact Principle

Failures should produce artifacts that allow later diagnosis.

A failed provider profile should include:

- error message
- URL
- strategy attempted
- screenshot if browser was used
- HTML snapshot if available
- network log if available
- timestamp

## Reports

Human-readable reports should be generated for every phase.

For Phase 1:

- HTML is preferred
- CSV summary is acceptable
- Markdown summary is acceptable as fallback

## PostgreSQL Storage

PostgreSQL is out of scope for Phase 1 but should be planned for later phases.

Later database layers should follow:

```text
raw metadata
→ staging tables
→ validation
→ canonical tables
→ quarantine
```

Do not insert unvalidated parsed rows directly into canonical tables.
