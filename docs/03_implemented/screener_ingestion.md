# Screener.in Stock Ingestion (Implemented)

**Status:** Working. 10 stocks ingested into PostgreSQL (`screener` DB on `vlmrouter-postgres`).
**Package:** `screener_ingestion/` — fetch.py, parse.py, db.py, cli.py
**Tests:** `tests/test_screener_parse.py` (13 passed, offline against saved fixtures)

## What it does

For any stock slug (e.g. `HAL`, `ITC`, `TCS`), fetches
`https://www.screener.in/company/<SLUG>/consolidated/` (server-rendered static HTML —
no JS rendering needed), parses every data block, and upserts into Postgres:

| Block | Source | Table |
|---|---|---|
| Header ratios (M-Cap, P/E, ROCE, ROE…) | `ul#top-ratios` | `stock_snapshots` (append-only history) |
| Quarterly Results | `section#quarters`, dates from `th[data-date-key]` | `financial_periods` + `financial_line_items` |
| P&L / Balance Sheet / Cash Flow / Ratios | `section#profit-loss` etc. | same |
| Shareholding (quarterly % + annual %) | two tables in `section#shareholding` | same (`statement_type` distinguishes) |
| Peers | AJAX `GET /api/company/{warehouse_id}/peers/` (id from `data-warehouse-id` attr) | `peer_rows` |
| Documents (BSE announcements, annual reports) | links in `section#documents` | `documents` |
| Sector hierarchy, BSE/NSE codes, about | page meta | `stocks` |

## Commands

```bash
source financial_env/bin/activate
DB=postgresql://vlmrouter:vlmrouter@localhost:5432/screener

python -m screener_ingestion.cli init-db --database-url $DB
python -m screener_ingestion.cli ingest --stock HAL --database-url $DB
python -m screener_ingestion.cli ingest-batch --stocks HAL,ITC,TCS --database-url $DB
python -m screener_ingestion.cli inspect --stock HAL --database-url $DB
pytest tests/test_screener_parse.py -q
python scripts/verify_screener_db.py   # DB audit
```

## Verified results (2026-08-22 run)

10/10 stocks: HAL, ITC, TCS, RELIANCE, HDFCBANK, INFY, SBIN, LT, SUNPHARMA, TMCV.
~620–680 line items each; 83–84 periods each (TMCV 21 — recently listed post-demerger);
5–7 peers each; 15–85 documents each. Idempotency verified: re-ingesting HAL left
line-item count unchanged (650) while appending a new snapshot.

**Slug note:** `TATAMOTORS` no longer exists on screener.in after the 2025 demerger —
the entity is now `TMCV` (Tata Motors Ltd, CV) and `TMPV` (Passenger Vehicles).
Use screener's search API to resolve names → slugs:
`GET https://www.screener.in/api/company/search/?q=<name>` → `[{"id", "name", "url"}]`.

## Design decisions

- **Deterministic strategy: `static_html`** (matches project strategy order). Only the
  peers table is lazy-loaded; it uses one extra plain HTTP call, no Playwright.
- **Periods**: `data-date-key` attributes give exact ISO period ends; shareholding
  tables lack them, so period keys are stored as text ("Sep 2023") with `is_date=false`.
- **Numbers**: Indian digit-grouping normalized (`3,34,388` → 334388.0); blank cells
  stay NULL (never zero) — verified with Aequs' blank P/E.
- **Idempotency**: unique constraints `(stock, statement_type, period_key)` and
  `(period_id, line_item)`; upserts update values in place. `stock_snapshots` and
  `peer_rows` (per day) are append-only by design.
- **Politeness**: sequential requests, 2s delay between stocks, honest UA, retries with
  backoff on 429/5xx, raw HTML cached to `data/raw/screener/<slug>/`.
- **Failures never corrupt**: each run is one transaction; failed runs recorded in
  `ingestion_runs` with error text; peers failure alone never fails a stock.

## Known limitations / next steps

- Standalone vs consolidated: currently one variant per stock (default consolidated).
  Add a `variant` column to periods/snapshots to store both.
- `growth_summary` (compounded sales/profit growth tables) parsed but returned 0 rows —
  the ranges-tables markup differs from the assumed pattern; low priority.
- Slug resolution by company name (search API) not yet wired into the CLI.
- BSE/NSE codes: `parse_company_meta` returns None for these on current markup —
  codes appear inside `.sub.company-links` in a different shape than expected; fix selector.
