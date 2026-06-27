# 00 — Codex Entrypoint

## Build Target

Build an end-to-end **Task-URL Driven Mutual Fund Ingestion Agent**.

The user provides one or more URLs. The agent must automatically discover relevant Indian mutual fund datasets from those URLs and linked pages, extract the data using the appropriate method, parse it, validate it, and load usable records into PostgreSQL.

The first seed/task URLs will likely be AMFI pages. AMFI may link to AMC/provider websites. Those linked provider sites must be followed when relevant because portfolio disclosures, factsheets, statutory documents, and other raw files may live there.

## Primary Success Criterion

The system is successful only when real rows are written into PostgreSQL tables.

Reports, notebooks, JSONL artifacts, and debug traces are useful, but they are secondary. Do not optimize for documentation-only output.

## Main Command

Implement a command similar to:

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "https://www.amfiindia.com/..." \
  --database-url "$DATABASE_URL" \
  --use-browser true \
  --use-vlm false \
  --vlm-endpoint "http://localhost:11434" \
  --max-pages 500 \
  --max-depth 5 \
  --keep-raw-files false
```

The exact CLI shape can follow the existing repository conventions, but the command must support task URLs, PostgreSQL connection, browser usage, optional VLM usage, crawl limits, and raw-file retention policy.

## Required Behavior

For each task URL, the agent must:

1. Fetch/open the page.
2. Determine if the page contains relevant mutual fund data or links.
3. Discover linked AMFI pages, AMC/provider pages, downloadable files, APIs, forms, and rendered browser controls.
4. Select extraction strategy automatically: static HTTP, HTML parsing, Playwright/Chromium, network/API interception, form interaction, file download, or local VLM-guided navigation.
5. Retrieve raw data or raw files.
6. Classify dataset/document type.
7. Parse supported datasets.
8. Load records into staging tables.
9. Validate records.
10. Upsert trusted records into canonical PostgreSQL tables.
11. Store provenance for every source, file, parser run, and loaded record.
12. Quarantine failures and add retryable tasks to a retry queue.

## Existing Codebase Requirement

Before implementing, inspect the existing repository. Look for:

- Phase 1A / Phase 1B implementation,
- provider profiling code,
- source registry code,
- crawler/discovery utilities,
- Playwright/browser utilities,
- parser utilities,
- PostgreSQL/SQLAlchemy/Alembic code,
- tests,
- notebooks,
- config files,
- previous design docs.

Reuse compatible pieces. Replace or bypass code that is too phase-specific or blocks the end-to-end goal.

## Non-Goals

Do not build investment advice.
Do not build a dashboard first.
Do not require the user to manually maintain all provider URLs.
Do not require manual classification of every site before ingestion.
Do not make notebooks the main output.
Do not build an unbounded autonomous web crawler.

## Implementation Priority

Prioritize data in this order:

1. AMC/provider list
2. Scheme metadata / scheme master
3. NAV history and latest NAV
4. Portfolio disclosure holdings
5. Factsheet metadata
6. TER, SID, KIM, statutory disclosures, AUM/AAUM, and other documents
