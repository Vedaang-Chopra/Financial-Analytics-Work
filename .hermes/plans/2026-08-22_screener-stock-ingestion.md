# Screener.in Stock Data Ingestion — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a parser + ingestion pipeline that, given any stock (e.g. HAL, ITC), fetches its screener.in company page and saves every disclosed data block into PostgreSQL.

**Architecture:** A new `screener_ingestion/` package following the same conventions as `mutual_fund_ingestion/` (SQLAlchemy models in `db.py`, CLI subcommands, tests under `tests/`, raw artifacts on disk). Screener company pages are fully server-rendered static HTML — verified live — so a single `requests` fetch captures everything except the peers table, which is lazy-loaded via an internal AJAX endpoint (`/api/company/<slug>/peers/`) and fetched with one extra request. No Playwright needed.

**Tech Stack:** Python 3, requests, lxml/BeautifulSoup, SQLAlchemy (existing dep), PostgreSQL, pytest.

---

## Verified page structure (from live HTML of /company/HAL/consolidated/)

| # | Data block | DOM anchor | Notes |
|---|---|---|---|
| 1 | Header ratios | `<ul id="top-ratios">` | Market Cap, Current Price, High/Low, Stock P/E, Book Value, Dividend Yield, ROCE, ROE, Face Value — values in `span.number` |
| 2 | Quarterly Results | `<section id="quarters">` → `table.data-table` | Column dates in `th[data-date-key="2026-06-30"]` |
| 3 | Profit & Loss | `<section id="profit-loss">` | Annual, same table pattern; "Figures in Rs. Crores" |
| 4 | Compounded Sales Growth etc. | tables inside `#profit-loss` | "ranges-table" rows: TTM / 10 Years / 5 Years / 3 Years |
| 5 | Balance Sheet | `<section id="balance-sheet">` | Annual columns Mar 2015…Mar 2026 |
| 6 | Cash Flow Statements | `<section id="cash-flow">` | Annual columns |
| 7 | Ratios | `<section id="ratios">` | Debtor Days, Inventory Days, Days Payable, ROCE %, etc. |
| 8 | Shareholding | `<section id="shareholding">` | TWO tables: quarterly (% — Sep 2023…) and yearly (Mar 2018…); rows = Promoters/FIIs/DIIs/Government/Public/Others |
| 9 | Peers | lazy-loaded | Placeholder div `#peers-table-placeholder`; served by internal endpoint `/api/company/<slug>/peers/`; sector hierarchy (Industrials → Capital Goods → Aerospace & Defense) IS in static HTML |
| 10 | Documents | `<section id="documents">` links | BSE announcement PDF URLs + annual reports |
| 11 | About / meta | `.company-info`, `<h1>`, `.sub.company-links` | Name, BSE/NSE codes, sector tags |

All numbers use Indian digit grouping (`3,34,388`) → strip commas before float conversion. Percent rows carry `%`; currency rows are Rs Crores unless the row name says otherwise (EPS is ₹, Face Value is ₹).

## Target schema (PostgreSQL)

```
stocks            (id PK, slug UNIQUE, name, bse_code, nse_code, sector_broad,
                   sector, industry_broad, industry, about_text, is_consolidated_default,
                   first_seen_at, last_fetched_at)
stock_snapshots   (id PK, stock_id FK, fetched_at, market_cap_cr, current_price,
                   high_52w, low_52w, stock_pe, book_value, dividend_yield,
                   roce_pct, roe_pct, face_value)          -- append-only history
financial_periods (id PK, stock_id FK, statement_type CHECK IN
                   ('quarters','profit_loss','balance_sheet','cash_flow','ratios',
                    'shareholding_quarterly','shareholding_annual'),
                   period_end DATE, UNIQUE(stock_id, statement_type, period_end))
financial_line_items (id PK, period_id FK, line_item TEXT, value NUMERIC,
                      unit TEXT ('cr'|'pct'|'rs'|'ratio'), raw_text TEXT,
                      UNIQUE(period_id, line_item))
growth_summary    (id PK, stock_id FK, metric ('compounded_sales_growth',
                   'compounded_profit_growth','stock_price_cagr','return_on_equity'),
                   window ('ttm','10y','5y','3y'), value_pct)
shareholding      -- modeled via financial_periods+items above (statement_type distinguishes)
peer_rows         (id PK, stock_id FK, peer_slug, peer_name, price_cmp, pe_cmp,
                   market_cap_cr, dividend_yield_pct, np_qtr, qtr_sales, roce_pct,
                   fetched_at, UNIQUE(stock_id, peer_slug, fetched_at))
documents         (id PK, stock_id FK, doc_type ('announcement','annual_report','credit_rating'),
                   title, source_url, published_on DATE, fetched_at,
                   UNIQUE(stock_id, source_url))
ingestion_runs    (id PK, run_uuid, stock_slug, started_at, finished_at, status,
                   sections_parsed JSONB, error)
raw_artifacts     (path to saved HTML per fetch: data/raw/screener/<slug>/<date>.html)
```

Idempotency: re-ingesting a stock upserts periods/items (no duplicates); snapshots and runs are append-only history.

## Repo layout

```
screener_ingestion/
├── __init__.py
├── fetch.py        # polite GET (UA header, timeout, retry/backoff), raw-HTML caching
├── parse.py        # section parsers returning plain dicts
├── db.py           # SQLAlchemy models + upsert helpers (mirrors mutual_fund_ingestion style)
└── cli.py          # argparse subcommands (mirrors mutual_fund_ingestion/cli.py)
tests/
└── test_screener_parse.py   # fixtures built from saved HAL + ITC HTML
data/raw/screener/<slug>/YYYY-MM-DD.html   # raw pages never modified
notebooks/screener_ingestion/review.ipynb  # post-run QA notebook (project policy)
```

CLI:
```bash
python -m screener_ingestion.cli init-db --database-url "$DATABASE_URL"
python -m screener_ingestion.cli ingest --stock HAL --consolidated --database-url ...
python -m screener_ingestion.cli ingest-batch --stocks-file configs/screener_stocks.yaml
python -m screener_ingestion.cli inspect --stock HAL --database-url ...
```

## Tasks

### Task 1: Save test fixtures from live site (read-only capture)
- Fetch `/company/HAL/consolidated/` and `/company/ITC/consolidated/` once each; save to
  `tests/fixtures/screener/hal_consolidated.html`, `itc_consolidated.html`.
- Verify: files >150KB, contain `id="top-ratios"`.

### Task 2: `screener_ingestion/fetch.py`
- `fetch_company(slug, consolidated=True, cache_dir=...) -> str` — UA header, 15s timeout,
  2 retries w/ backoff, writes raw HTML to `data/raw/screener/<slug>/<date>.html`.
- Test: parses fixture without network (mock requests.get).

### Task 3: `parse.py` — top ratios + company metadata (TDD)
- Failing test: `parse_top_ratios(hal_html)` returns dict with market_cap ≈ 334388, stock_pe ≈ 35.9.
- Implement: regex-free BeautifulSoup over `ul#top-ratios li`; number cleaner strips commas/₹/%.
- Also `parse_company_meta`: h1 name, BSE/NSE codes from `.sub.company-links`, sector chain from peers `.sub` links, about text.

### Task 4: `parse.py` — generic financial-table parser (TDD)
- One function handles all `table.data-table` sections: reads `th[data-date-key]` for period_end,
  row label from first cell (strip `&nbsp; +` schedule buttons), values per column.
- Tests: quarters (Sales row, Jun 2023 col), profit-loss annual (Mar 2026), balance sheet, cash flow.
- Handle missing/blank cells as NULL, never zero.

### Task 5: `parse.py` — growth/ranges tables + shareholding + documents (TDD)
- `parse_growth_tables` (profit-loss ranges-tables → metric/window/value),
- `parse_shareholding` → two statement_types, values as pct floats,
- `parse_documents` → list of {title, url, date}.
- Fixtures assert against known HAL values captured in Task 1.

### Task 6: Peers via internal endpoint
- In fetch.py: `fetch_peers(slug)` hitting `/api/company/<slug>/peers/` (verify exact path/shape live during implementation;
  fallback: skip peers with logged warning — never fail the run for one section).
- Parse rows into dicts; test against saved fixture of that response.

### Task 7: `db.py` models + upserts
- Tables exactly as schema above; `upsert_stock_and_data(engine, parsed)` doing
  begin → upsert stock → insert snapshot → upsert periods/items → peers/documents → commit.
- Idempotency test: run twice against SQLite in-memory copy of schema, assert no duplicate line items.

### Task 8: `cli.py`
- Subcommands init-db / ingest / ingest-batch / inspect mirroring existing cli.py patterns;
  `--database-url` flag; ingestion_runs row per execution with status + counts.
- Test: `ingest --stock HAL` end-to-end against local Postgres (docker) or skipped-if-unavailable marker.

### Task 9: End-to-end validation + notebook + docs
- Ingest HAL, ITC, TCS into real DB; spot-check 5 numbers against the website manually;
  write `docs/03_implemented/screener_ingestion.md` (per project convention);
  add review notebook calling production code only.
- Re-run ingest for HAL: confirm idempotent update (no dup rows).

## Politeness / compliance
- Sequential requests only, ≥2s sleep between stocks, honest User-Agent, cache raw HTML.
- Only public investor-disclosure data. Respect screener.in ToS; keep volumes low (tens of stocks/day, not thousands).

## Risks / open questions
- Markup drift: all selectors centralized in parse.py constants so fixes stay one-place.
- Peers endpoint shape unverified until Task 6 (designed to degrade gracefully).
- Standalone vs consolidated: ingest stores which variant was fetched (URL suffix recorded in ingestion_runs);
  both variants can coexist if we later add a `variant` column — out of scope now, one stock variant at a time.
- Rate limiting/blocks: back off on HTTP 429; do not bypass.
