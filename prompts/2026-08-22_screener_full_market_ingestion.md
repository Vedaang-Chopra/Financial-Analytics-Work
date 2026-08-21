# Prompt: Full-Market Screener.in Ingestion (~5,000 Indian stocks)

Copy everything below the line into a fresh Hermes session (or a cron job). It is
self-contained and safe to run repeatedly in the background — it resumes where it
left off and never hammers the site.

---

## Task: Ingest the broadest possible set of Indian stocks from screener.in into our PostgreSQL database

You are working in an existing codebase that already has a complete, tested
ingestion engine for screener.in company pages. Your job is NOT to build anything
new — it is to run the existing engine at scale, politely and incrementally, until
we cover roughly the top 5,000 Indian listed stocks (or as many as screener.in
covers).

### Environment (all verified working)

- Repo root: current workspace (`Financial Analytics Work`)
- Python venv: `source financial_env/bin/activate`
- Engine package: `screener_ingestion/` (fetch.py, parse.py, db.py, cli.py)
- Tests: `pytest tests/test_screener_parse.py` (13 must pass before you start)
- Database: `postgresql://vlmrouter:vlmrouter@localhost:5432/screener` (Postgres in docker, container `vlmrouter-postgres`)
- One stock ingested = its full page captured: header ratios, quarterly results,
  P&L, balance sheet, cash flow, ratios, shareholding (quarterly+annual), peers,
  documents, and 5-year weekly price history (~650 line items + ~1,044 price points)

### Phase 0 — Preflight (do not skip)

1. `source financial_env/bin/activate && pytest tests/test_screener_parse.py -q`
2. Confirm DB reachable: `python -m screener_ingestion.cli inspect --stock HAL --database-url $DB`
3. If either fails, stop and report. Do not attempt repairs beyond obvious env issues.

### Phase 1 — Build the stock universe (target: 4,000–5,000+ candidates)

Assemble the universe from public index/market lists OUTSIDE screener first, so we
don't crawl screener just to discover names:

1. NSE listed equities: `https://archives.nseindia.com/content/equities/EQUITY_L.csv`
   (~2,000 rows; columns include SYMBOL, NAME OF COMPANY)
2. Additional liquid/large names: NIFTY 500 + NIFTY Next 250 constituent lists
   (CSV endpoints on nseindia.com / niftyindices.com), and BSE 500 if reachable.
3. Combine, normalize names, dedupe. Save to
   `data/raw/screener/universe.csv` with columns: `name, symbol, source`.
4. Resolve each name to its screener slug using screener's own search API:
   `GET https://www.screener.in/api/company/search/?q=<urlencoded name>`
   Response is JSON: `[{"id": ..., "name": ..., "url": "/company/<SLUG>/consolidated/"}]`.
   Take the best match (prefer exact/consolidated), cache the mapping to
   `data/raw/screener/slug_map.csv`, and REUSE this cache on every re-run —
   never re-resolve names that are already mapped.
5. Note: some entities have been renamed/demerger-split (e.g. TATAMOTORS is now
   TMCV + TMPV on screener). Search-API resolution handles this naturally;
   log any name with no confident match into `data/raw/screener/unresolved.csv`
   and move on. Do not guess slugs.

### Phase 2 — Batched, polite ingestion (the long part)

Use the existing CLI. Core command:

```bash
DB=postgresql://vlmrouter:vlmrouter@localhost:5432/screener
python -m screener_ingestion.cli ingest-batch --stocks SLUG1,SLUG2,... \
  --delay 3 --database-url $DB
```

Rules that make the load look like normal browsing (non-negotiable):

- **Sequential requests only**, single process, honest browser User-Agent (already built in).
- **3 seconds between stocks** (`--delay 3`). Each stock costs ~3 HTTP requests
  (company page, peers AJAX, chart AJAX) — total sustained rate stays under
  ~1 request/second, comparable to a person browsing.
- **Chunk size: 75–100 stocks per execution.** After each chunk, append progress
  to the checkpoint file `data/raw/screener/ingest_checkpoint.json`
  (`{completed: [...], failed: {...}, next_index: N}`).
- **Back off hard on any HTTP 429 or block page**: sleep 120s and retry once;
  if it happens again, STOP the run entirely, record the checkpoint, and report.
  Never rotate IPs/user-agents, never bypass rate limits or CAPTCHAs.
- **Idempotent resume**: before ingesting a slug, check `ingestion_runs` in Postgres —
  if its last run succeeded within the past 24 hours, skip it. Re-running this
  prompt never duplicates work.
- **Failures are fine**: a 404 (delisted/renamed) or parse error gets logged by the
  engine into `ingestion_runs` and the run continues. Collect failures for the report.

### Phase 3 — Execution pattern (background-friendly)

Estimated volume: ~5,000 stocks x ~3 requests x 3s spacing ≈ 12–13 hours of pure
crawl time. Do NOT try to do it in one sitting. Instead:

- Run one chunk (75–100 stocks) per background execution, updating the checkpoint.
- Between chunks, verify: row counts rising, no error spike, memory/CPU nominal.
- If invoked as a recurring job: read the checkpoint first, process the next
  pending chunk, write the updated checkpoint, print a one-line progress summary
  ("chunk 14/55 done, 1,283/5,000 stocks, 41 skipped-fresh, 6 failed").
- When the checkpoint says complete, do Phase 4 once.

### Phase 4 — Final verification and coverage report

1. SQL audit against Postgres:
   - total stocks, periods, line items, price points, peers, documents
   - distribution of line items per stock (flag any stock with <400 items for review)
   - failed-run list from `ingestion_runs`
2. Re-run `scripts/verify_db_vs_live.py` logic on a random sample of 25 stocks —
   stored values must match live values exactly (this held at 100% on the pilot 10).
3. Write `data/reports/screener/full_market_coverage.md` (and .html):
   totals, coverage vs universe, failure breakdown, runtime, and any anomalies.

### Hard constraints

- Public investor-disclosure data only; nothing behind login walls.
- This data powers analytics; accuracy matters more than speed. Never fabricate,
  estimate, or interpolate values — the engine stores exactly what screener shows.
- If the site introduces breakage (markup change, blocks), stop cleanly, keep the
  checkpoint consistent, and report what happened with examples. Do not improvise
  scraping hacks around their defenses.
