# EXECUTION PLAN — Consensus/Dissent Mutual-Fund Intelligence Platform

**Created:** 2026-08-22
**Purpose:** Self-contained build plan. A fresh agent session should be able to execute this top-to-bottom without re-doing any investigation.
**Source audit:** `docs/audits/2026-08-22_full_system_audit.md` (read it if context on WHY is needed — this file is the WHAT/HOW).

---

## 0. Mission Context (do not skip)

**The product vision:** Build a consensus/dissent panel over Indian mutual-fund portfolio disclosures.
For every **stock × time period**: how many funds held it, how much money (AUM-weighted), which fund categories agreed vs disagreed, how those patterns formed/dissolved historically — then join with actual stock price/fundamental data to test whether consensus patterns were predictive. Small-cap divergence is the primary area of interest.

**Why current state is insufficient:** Today only NAV + ~8 AMCs' portfolios are ingested. Missing: scheme categories, AUM, full-market prices, index benchmarks, and breadth (all-AMC holdings history). The instruments table is polluted and cannot serve as the cross-fund join key yet.

**Environment facts (verified 2026-08-22):**
- Repo root: `/Users/vedaangchopra/all_data/complete_technical_work/all_projects_implemented/Financial Analytics Work`
- Python venv: `./financial_env/bin/python`
- PostgreSQL: `postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds` (Docker container `vlmrouter-postgres`; start Docker.app then `docker start vlmrouter-postgres` if down after sleep)
- Screener DB (separate): `postgresql://vlmrouter:vlmrouter@localhost:5432/screener`
- Tests: `./financial_env/bin/python -m pytest tests/ -q` → baseline was **162 passed / 6 failed** (4 pre-existing DB-integration failures on fixture seeding; 2 live-network smoke). Do not let this number regress.
- AMFI historical NAV endpoint (discovered & working): `https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=DD-Mon-YYYY&todt=DD-Mon-YYYY` (90-day max window, data from 2006-04-01)
- Key existing code: `mutual_fund_ingestion/agent/parser/portfolio.py` (strong Excel parser — REUSE its column-alias logic), `agent/upserts.py`, `agent/db.py` (23 tables, NO migration system yet), `scripts/backfill_amfi_nav_history.py` (working pattern for windowed AMFI fetches)

**Rules of engagement:**
1. Read AGENTS.md before coding. No rewrites of working components. Incremental only.
2. Every task ends with: tests written+passing, verification query shown, honest status report.
3. Never delete data/files without explicit user approval.
4. Polite crawling: sequential requests, ≥1s sleep, real User-Agent, timeouts.
5. Sample files for parser development already exist at `data/datasets/Monthly Reports October 2024/` (AMFI monthly portfolio + scheme master workbooks).

---

## 1. Task Dependency Graph

```
TRACK A (correctness)          TRACK B (parsers)                TRACK C (prices/market data)
A1 validation-on-path                                          C1 schema migrations
A2 ISIN guard+dedup            B1 scheme_master_excel ──┐       C2 security_prices+bhavcopy
A3 holdings uniqueness fix     B2 AMFI monthly portfolio│       C3 index_prices
A4 snapshots.amc_id fix        B3 aum_excel ────────────┤
A5 documents index sync                                 │
A6 junk-row cleanup                                     ▼
        │                                        D1 Consensus panel view (SQL)
        └─────────────── depends on A1–A6 ────── D2 ISIN↔screener linkage
                                                 D3 Backtest sanity query set
```

- **Track A must finish before any new bulk ingestion writes to canonical tables** (otherwise garbage keeps flowing).
- Tracks B and C are fully parallelizable with each other once A is done.
- Track D is pure SQL/small scripts on top of A+B+C outputs.
- Subagent strategy: each numbered task below is sized for one subagent. Tasks within a track can run in parallel ONLY where marked ⚡PARALLEL-SAFE.

---

## TRACK A — Correctness Blockers (P0, do first, mostly serial)

### A1. Route production ingestion through validation
- **Problem:** `scripts/targeted_portfolio_ingestion.py:171` and `scripts/backfill_amfi_nav_history.py` call `UpsertManager.upsert_canonical()` directly, bypassing `validate_and_filter_records()` entirely. This is why garbage entered canonical tables.
- **Do:** Make both scripts call `ArtifactProcessor`'s validate→quarantine path (`mutual_fund_ingestion/agent/artifact_processor.py:170` shows the pattern). Quarantine rows must actually land in `quarantine_rows`.
- **Add validators** (in `agent/validate.py`):
  - ISIN format check: reject values not matching `^[A-Z]{2}[A-Z0-9]{9}[0-9]$` (reason: `invalid_isin`)
  - Snapshot-level pct-sum gate: after grouping a file's records by (scheme, reporting_date), flag groups whose pct-sum is outside 85–115 for review (warn-level, don't drop — log to validation_results)
- **Verify:** Run one small ingestion (e.g. `--amcs ppfas --max-files 2`); confirm quarantine_rows > 0 OR zero invalid rows inserted; run the invalid-ISIN query from A2 and confirm count does NOT grow.
- **Size:** S–M | ⚠ Do first; blocks all ingestion tasks

### A2. Instruments table repair (migration + backfill)
- **Problem:** 206,781 instrument rows but only 15,181 distinct ISINs; 2,807 garbage ISINs (numeric strings like `0.00059…`, `-`); no unique constraint on `instruments.isin`; upsert creates a new row whenever lookup misses (upserts.py:442–450).
- **Do:**
  1. One-off cleanup script (backup-first per project convention): delete/rename-to-placeholder instruments whose `isin` fails the regex; merge duplicate NULL-ISIN instruments where possible.
  2. Add unique partial index: `CREATE UNIQUE INDEX uq_instruments_isin ON instruments(isin) WHERE isin IS NOT NULL;`
  3. Fix `upserts.py::upsert_portfolio` instrument resolution: lookup by normalized_name fallback when ISIN missing instead of blind insert.
- **Verify:** `SELECT count(*) FROM instruments WHERE isin !~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$' AND isin IS NOT NULL;` → 0. Instrument count drops toward ~15K.
- **Size:** M | Depends on nothing; do alongside A1

### A3. Holdings uniqueness fix
- **Problem:** unique key `(snapshot_id, security_name, isin)` doesn't enforce when isin is NULL → 1,253 duplicate security rows inside snapshots.
- **Do:** Migration adds partial unique index `(snapshot_id, security_name) WHERE isin IS NULL`; dedupe existing rows first (keep latest created_at).
- **Verify:** dup-count query (in audit §12-G) returns 0.
- **Size:** S

### A4. Populate snapshots.amc_id in upsert
- **Problem:** `upserts.py::upsert_portfolio` never sets amc_id → 384/384 NULL.
- **Do:** Resolve AMC via the scheme's amc_id (or source URL domain via `configs/amc_sources.yaml`) and set on snapshot upsert. Write one-off backfill SQL for the 384 existing rows (join through schemes).
- **Verify:** `SELECT count(*) FROM portfolio_snapshots WHERE amc_id IS NULL;` → 0.
- **Size:** S

### A5. Sync documents unique index into db.py model
- **Problem:** Live DB has `documents_scheme_date_type_url_key` (needed by the ON CONFLICT upsert) but `db.py` defines no such constraint → a fresh `init-db` breaks document upserts silently.
- **Do:** Add `UniqueConstraint("scheme_id","reporting_date","document_type","source_url")` to the Document model in `agent/db.py`.
- **Verify:** create_all into a scratch SQLite DB shows the constraint.
- **Size:** S

### A6. Junk-row purge in holdings
- **Problem:** Section headers stored as holdings ("Total" ×4,026 in instruments; 'Net Current Assets', 'TREPS', 'Commercial Papers', etc.). Parser has JUNK_ROW_PATTERNS but leaks remain.
- **Do:** Extend `SECTION_HEADER_PATTERNS` in `parser/portfolio.py` with observed leaks; write one-off cleanup deleting matching canonical holdings (with backup).
- **Verify:** `SELECT count(*) FROM portfolio_holdings WHERE security_name ILIKE ANY(ARRAY['total','net current assets','total net assets','treps','commercial papers','government securities','certificate of deposits']);` → 0.
- **Size:** S | ⚡PARALLEL-SAFE with A4/A5

---

## TRACK B — Missing Parsers (the vision-critical datasets)

> All new parsers go in `mutual_fund_ingestion/agent/parser/`, return `ParserResult` (see `parser/models.py`), get registered in `parser/__init__.py::PARSER_ROUTER`, and need unit tests using sample files from `data/datasets/Monthly Reports October 2024/`. Reuse `_map_columns` / COLUMN_ALIASES patterns from `portfolio.py`. NO network calls in unit tests.

### B1. `scheme_master_excel` — AMFI Monthly Scheme Master XLSX
- **Unlocks:** `schemes.category` / `sub_category` (currently NULL) → enables "small-cap managers agreed" segmentation.
- **Input:** AMFI monthly scheme-master workbook (samples on disk; also downloadable from amfiindia.com monthly reports page).
- **Extract:** scheme_code, scheme_name, amc_name, plan/option split, category/type, launch date if present.
- **Wire to:** `UpsertManager.upsert_schemes` (already handles category columns; conflict target = scheme_code).
- **Tests:** parse both provided sample workbooks; assert category extraction rate ≥80% of rows.
- **Then:** one-off backfill script `scripts/backfill_scheme_master.py` fetching last N months, populating categories for all schemes.
- **Verify:** `SELECT count(*) FILTER (WHERE category IS NOT NULL)::float / count(*) FROM schemes;` → ≥0.8.
- **Size:** M | ⚡PARALLEL-SAFE (after A1) | Can be one subagent while another does C-track

### B2. `portfolio_monthly_amfi` — AMFI all-AMC monthly portfolio files ⭐ CORE DATASET
- **Unlocks:** The consensus panel itself — hundreds of funds × multi-year monthly holdings, survivorship-safe (includes exited stocks).
- **Input:** AMFI monthly portfolio disclosure workbooks (one per month, all AMCs). Samples: `data/datasets/Monthly Reports October 2024/*.xlsx|xls`.
- **Parser notes:** Different layout from per-AMC files — typically grouped by AMC section with scheme sub-headers. Reuse column aliases; detect AMC/scheme boundaries from section rows rather than sheet names.
- **New fetcher:** `scripts/backfill_amfi_monthly_portfolios.py` following the windowed pattern of `backfill_amfi_nav_history.py` (polite: sequential, sleep 1s).
- **Schema consideration:** keep writing into existing `portfolio_snapshots`/`portfolio_holdings`; ensure reporting_date = month-end date from filename/header. Add `source_dataset='amfi_monthly'` in metadata_json to distinguish from per-AMC crawls.
- **Quarter bucketing:** store raw reporting_date now; quarter normalization happens in view D1 (do NOT transform at write time).
- **Tests:** parse Oct-2024 sample end-to-end; assert ≥500 schemes and every holding has valid ISIN or explicit None; assert AMC boundary detection correct on 3 known AMCs.
- **Verify:** holdings count grows by hundreds of thousands; distinct scheme_ids with snapshots > 1000; spot-check 5 random schemes against live AMFI site.
- **Size:** L (largest single task — give it a dedicated subagent, expect iteration on format quirks)

### B3. `aum_excel` — AMFI AUM/AAUM monthly
- **Unlocks:** conviction weighting ("₹X of managed money holds this").
- **Schema (needs migration):**
  ```sql
  CREATE TABLE scheme_aum_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_id UUID REFERENCES schemes(id),
    month_start DATE NOT NULL,
    avg_aum_cr NUMERIC,
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (scheme_id, month_start)
  );
  ```
- **Parser:** simple tabular read; AMFI publishes average AUM per scheme monthly.
- **Verify:** AUM rows exist for ≥80% of schemes with portfolio snapshots; join query `holdings.pct_to_nav * aum/100` returns sane rupee weights.
- **Size:** M | ⚡PARALLEL-SAFE (after A1)

### B4. (Deferred, explicitly out of scope for now) TER, factsheets, SID/KIM PDFs, fund-manager names
Do NOT build these. They don't feed the consensus signal. If tempted, re-read §0.

---

## TRACK C — Market Data (outcome variable) ⚡FULLY PARALLEL WITH TRACK B

### C1. Schema migrations foundation
- **Problem:** No migration system — schema is `Base.metadata.create_all()` only.
- **Do (minimal, pragmatic):** Adopt Alembic. Baseline revision = current live schema (introspect with alembic autogen against the live DB, then hand-fix drift — note the `documents` unique index exists only live, fixed by A5 in models).
- **All later table additions (C2, C3, B3) go through Alembic revisions.**
- **Verify:** `alembic upgrade head` on empty DB produces schema matching live; `alembic downgrade base` clean.
- **Size:** M | Do before C2/C3/B3 table creation

### C2. Full-market stock prices (bhavcopy)
- **Unlocks:** the outcome variable — did consensus stocks perform?
- **Source:** NSE bhavcopy (free daily CSV, all listed equities). Alternative/complement: BSE bhavcopy. Use close price + volume; adjust nothing yet (corporate-action adjustment is a later concern — record raw).
- **Schema:**
  ```sql
  CREATE TABLE security_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    isin TEXT NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC NOT NULL,
    volume BIGINT,
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (isin, trade_date)
  );
  CREATE INDEX ix_security_prices_isin_date ON security_prices(isin, trade_date);
  ```
- **Fetcher:** `market_data/bhavcopy.py` — daily download, idempotent upsert. Backfill script for ~10 years (bhavcopy archive allows historical pulls; if NSE archive rate-limits, prioritize 2018→now first).
- **Scope control:** you need prices only for ISINs that ever appear in `portfolio_holdings` (~2–4K expected) plus indices — but ingesting full bhavcopy costs the same effort, so ingest all.
- **Verify:** `SELECT count(DISTINCT isin) FROM security_prices;` ≥ 1500; price continuity check for 3 known large-caps.
- **Size:** M–L | ⚡PARALLEL-SAFE

### C3. Benchmark index closes
- **Schema:** `index_prices(index_symbol TEXT, trade_date DATE, close NUMERIC, UNIQUE(index_symbol, trade_date))`
- **Indices:** NIFTY 50, NIFTY 500, NIFTY SMALLCAP 250 (the smallcap benchmark matters most for the thesis), NIFTY MIDCAP 150.
- **Source:** NSE indices CSV endpoints (deterministic, no scraping needed).
- **Verify:** 10 years of daily closes per index, no gaps > 5 days.
- **Size:** S | ⚡PARALLEL-SAFE

### C4. ISIN ↔ screener linkage
- **Unlocks:** joins MF consensus signals to the fundamentals you already collect in the `screener` DB.
- **Do:** `screener_ingestion` stocks have names/slugs; add `isin TEXT` column to `stocks` there (Alembic or manual ALTER given that stack's simplicity), populate via match against `instruments.isin` + name fuzzy fallback; persist confidence + method.
- **Verify:** ≥70% of screener stocks get an ISIN; spot-check 10 mappings manually.
- **Size:** S–M | ⚡PARALLEL-SAFE (after A2 so instruments are trustworthy)

---

## TRACK D — Analysis Layer (after A+B+C)

### D1. Consensus panel materialized view
Pure SQL, e.g.:
```sql
CREATE MATERIALIZED VIEW consensus_panel AS
WITH q AS (
  SELECT h.snapshot_id, ps.scheme_id, s.category,
         date_trunc('quarter', ps.reporting_date) AS qtr,
         ph.isin,
         count(DISTINCT ps.scheme_id)                            AS n_holders,
         avg(ph.percentage_to_nav)                               AS avg_pct
  FROM portfolio_holdings ph
  JOIN portfolio_snapshots ps USING (snapshot_id)
  JOIN schemes s ON s.id = ps.scheme_id
  GROUP BY 3, 2, 4, 5  -- adjusted per final design
)
SELECT isin, qtr,
       count(DISTINCT scheme_id)                       AS holders_total,
       count(*) FILTER (WHERE category ILIKE '%small%') AS holders_smallcap,
       ... 
FROM q GROUP BY isin, qtr;
```
Refine during implementation. Refresh via cron after each ingestion.
- **Verify:** known case — pick a famous multi-holder smallcap and confirm counts match manual AMFI check.
- **Size:** M

### D2. Fund-similarity primitives
Overlap coefficient between scheme pairs per quarter (SQL function or scheduled computation into a `scheme_overlap(qtr, scheme_a, scheme_b, overlap_pct)` table).
- **Size:** M | ⚡PARALLEL-SAFE with D1 once data lands

### D3. Backtest sanity queries
Set of notebook queries: for each quarter t, bucket stocks by holders_total decile; compute t→t+4q forward return from `security_prices` vs `index_prices` smallcap benchmark; output table + plot. This validates the whole pipeline end-to-end and gives the first thesis signal read.
- Deliverable: one notebook under `notebooks/mutual_fund_ingestion/06_consensus_backtest.ipynb` calling SQL views only (no business logic in cells).
- **Size:** M

---

## 2. Recommended Execution Order (subagent orchestration)

| Wave | Tasks | Mode |
|---|---|---|
| 1 | A1 + A2 (parallel: two agents, different files) | 2 parallel |
| 2 | A3 + A4 + A5 + A6 (all small, independent) | 4 parallel or one agent serially (~half day) |
| 3 | C1 (Alembic baseline) | 1 agent — gates B3/C2/C3 |
| 4 | B1 ‖ B2 ‖ C2 ‖ C3 ‖ C4 | 5-way parallel (B2 gets strongest agent; biggest task) |
| 5 | B3 (needs C1 + B1 done) | 1 agent |
| 6 | D1 ‖ D2 | 2 parallel |
| 7 | D3 (single integrator, human reviews output) | 1 agent |

**Wave-4 caution:** B2 (AMFI monthly portfolios) will hit format surprises. Instruct that subagent to iterate parser against ALL sample months on disk before running the live backfill, and to run the live backfill with `--max-files 3` first, verify against DB expectations, then unleash full history.

## 3. Definition of Done (whole plan)

You can run ONE query that answers: *"In Q1-2023, which 20 small-cap-focused schemes held stock X, what fraction of their AUM did it represent, and what did X return over the following 12 months versus the Nifty Smallcap 250?"* — in under 5 seconds, with numbers that spot-check correctly against AMFI/NSE sources. Everything before that moment is intermediate.

## 4. Standing Warnings for Executing Agents

1. The NAV history backfill may still be running (`ps aux | grep backfill_amfi`) — coordinate, don't double-write nav_history (it's idempotent-safe anyway, but don't restart it).
2. ICICI navigator selector is broken post-site-change (known issue) — don't debug it inside these tasks; per-AMC crawling is deliberately deprioritized vs AMFI monthly files.
3. `MASTER_STATE.md` and several docs are materially stale — trust code + DB, update docs only in a dedicated docs pass AFTER waves 1–2.
4. If any migration would drop/rename existing columns, stop and ask the user first.
5. Commit after each completed task (`git commit -m "agent: <task-id> <description>"`), per global rules.
