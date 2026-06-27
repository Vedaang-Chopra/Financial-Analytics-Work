# 13 — Testing and Acceptance Criteria

## Testing Philosophy

Tests should prove the agent can discover, extract, parse, validate, and load data without requiring a full live crawl every time.

Use fixtures for deterministic tests and small live smoke tests for integration.

## Unit Tests

Add tests for:

- URL normalization,
- domain allow/block logic,
- relevance scoring,
- dataset type classification,
- file type detection,
- checksum computation,
- raw artifact metadata creation,
- parser routing,
- NAV parser,
- Excel portfolio parser on fixtures,
- validation rules,
- database upsert logic,
- quarantine handling.

## Browser Tests

Use small static/local HTML fixtures where possible.

Test that Playwright can:

- extract rendered links,
- detect buttons/forms,
- intercept downloads,
- capture screenshots,
- capture network logs where feasible.

Live browser tests should be opt-in or marked separately.

## VLM Tests

Do not require a real VLM for CI.

Create a fake VLM backend that returns structured decisions.

Test:

- parse valid VLM JSON,
- reject invalid JSON,
- reject unsafe action,
- apply safe action when target exists,
- log VLM decision artifacts.

## Database Tests

Use a test PostgreSQL database if available. Otherwise use isolated database tests that can be skipped when `DATABASE_URL` is absent.

Test:

- schema creation/migrations,
- insertion into discovery tables,
- staging rows,
- NAV upserts,
- portfolio snapshot/holdings insert,
- quarantine insert,
- retry queue insert.

## Smoke Test

Add a small smoke command:

```bash
python -m mutual_fund_ingestion run-agent \
  --task-url "<AMFI URL>" \
  --database-url "$DATABASE_URL" \
  --max-pages 5 \
  --max-depth 1 \
  --use-browser true \
  --use-vlm false
```

Expected:

- run is created,
- source pages are stored,
- links are discovered,
- at least some dataset candidates are stored,
- no uncaught crash.

## Acceptance Criteria

Codex implementation is acceptable when:

1. There is a runnable command accepting task URLs.
2. PostgreSQL schema is created or migrated.
3. Run metadata is stored.
4. Source pages and discovered links are stored.
5. Dataset candidates are classified.
6. At least one supported dataset type can be parsed and loaded.
7. NAV data can be loaded when an AMFI NAV URL is provided.
8. At least one Excel/CSV portfolio disclosure fixture can be parsed into holdings.
9. Failures go to quarantine/retry, not silent logs only.
10. VLM integration is pluggable and optional.
11. Existing Phase 1A/1B code is reused where compatible or explicitly bypassed with reason.
