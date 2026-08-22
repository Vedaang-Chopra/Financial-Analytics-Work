# Kickoff Prompt — Consensus Platform Completion (Wave 1)

Copy everything below the line into a fresh session.

---

We're building the consensus/dissent mutual-fund intelligence platform in this repo
(Financial Analytics Work). Read these three files before doing anything:

1. `docs/VISION.md` — the product: MF portfolio disclosures → stock×quarter consensus
   panel, joined to price outcomes. Small-cap dissent is the thesis.
2. `docs/plans/NEXT_SESSION_PLAN_consensus_completion.md` — **your task list**. The
   original EXECUTION_PLAN is ~80% done; this file has the verified gap register
   and the 4-wave plan.
3. `AGENTS.md` + `~/agent-governance/AGENTS.md` — standing rules.

Your job this session: execute **Wave 1 — three parallel agents**:

- **T1** Run the AMFI monthly portfolio backfill at scale
  (`scripts/backfill_amfi_monthly_portfolios.py`; smoke-run `--max-files 3` first,
  verify snapshots land with amfi_monthly provenance, then full history in polite
  background chunks). Today: only 18 AMCs / 39 months / 87K holdings — this must grow ~10×.
- **T2** Complete scheme category coverage (currently 41% of schemes categorized;
  target ≥90% of schemes that appear in `consensus_panel`). Diagnose why B1's backfill
  stopped, extend matching, re-run.
- **T3** Resume the screener.in crawl to 500 stocks
  (`python scripts/ingest_chunk.py --chunk-size 50 --delay 3`; universe + checkpoint
  already at `data/raw/screener/`, 111/462 done). While it runs in background, fix:
  growth_summary parser (0 rows), BSE/NSE code selector (all NULL), mark the stale
  Adani Power failed-run superseded.

Environment facts:
- venv: `source financial_env/bin/activate`
- MF DB: `postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds`
- Screener DB: `postgresql://vlmrouter:vlmrouter@localhost:5432/screener`
- Tests baseline: screener tests 13 passed; do not regress mutual_funds suite.

Rules: T1/T2/T3 are disjoint (different tables/DBs) so run them in parallel via
subagents. Polite crawling always (sequential, ≥1s AMFI, ≤1 req/s screener,
yfinance-only for Yahoo). History-preserving writes; backup before deletes.
Commit per task as `agent: <task-id> <description>`. Every task ends with SQL
verification counts shown, not prose claims. When Wave 1 finishes, proceed to
Wave 2 per the plan file (refresh consensus_panel + scheme_overlap, re-link
screener ISINs, freshness cron) — T4 gates on all of Wave 1 landing first.

Start by reading the three files, then dispatch Wave 1.
