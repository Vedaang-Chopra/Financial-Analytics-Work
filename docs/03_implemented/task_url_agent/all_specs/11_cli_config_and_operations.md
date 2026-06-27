# 11 — CLI, Configuration, and Operations

## Main CLI

Implement:

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/..." \
  --database-url "$DATABASE_URL" \
  --use-browser true \
  --use-vlm false \
  --vlm-endpoint "http://localhost:11434" \
  --max-pages 500 \
  --max-depth 5 \
  --max-files 200 \
  --keep-raw-files false
```

Also support multiple task URLs:

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/..." \
  --task-url "https://example.com/disclosures" \
  --database-url "$DATABASE_URL"
```

## Useful CLI Flags

```text
--task-url
--task-url-file
--database-url
--use-browser
--headless
--use-vlm
--vlm-endpoint
--vlm-model
--vlm-confidence-threshold
--max-pages
--max-depth
--max-files
--max-runtime-minutes
--max-file-size-mb
--allow-off-domain
--allowed-domain
--blocked-domain
--keep-raw-files
--keep-failed-raw-files
--raw-dir
--temp-dir
--log-level
--fail-fast
--dry-run
--dataset-type-priority
```

## Config File

Support YAML config as optional:

```yaml
agent:
  max_pages: 500
  max_depth: 5
  max_files: 200
  allow_off_domain: true
  headless: true

browser:
  timeout_seconds: 45
  wait_until: networkidle

vlm:
  enabled: false
  endpoint: http://localhost:11434
  model: null
  confidence_threshold: 0.7

storage:
  keep_raw_files: false
  keep_failed_raw_files: true
  max_retained_file_size_mb: 50

datasets:
  priority:
    - amc_provider_list
    - scheme_master
    - nav_history
    - portfolio_disclosure
    - factsheet
```

## Operational Commands

Suggested additional commands:

```bash
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"
python -m mutual_fund_ingestion retry-failed --database-url "$DATABASE_URL" --run-id "..."
python -m mutual_fund_ingestion inspect-run --database-url "$DATABASE_URL" --run-id "..."
python -m mutual_fund_ingestion export-run-summary --database-url "$DATABASE_URL" --run-id "..."
```

## Logging

Use structured logs.

Each log should include:

- run ID,
- URL/artifact ID where relevant,
- component,
- event type,
- status,
- error reason if any.

## Minimal Run Summary

At run completion, print:

```text
Run ID
Status
Pages visited
Dataset candidates found
Files downloaded
Artifacts parsed
Rows staged
Rows inserted/updated
Rows quarantined
Retry tasks created
Top failure reasons
```
