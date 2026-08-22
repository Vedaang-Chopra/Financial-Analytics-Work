# NEXT SESSION PLAN — Finish the Consensus Platform

**Created:** 2026-08-22 (end of stock-pipeline session)
**Reads first:** `docs/VISION.md` (product) → `docs/plans/EXECUTION_PLAN_consensus_platform.md` (original plan, now ~80% executed) → this file (what's left, sequenced for parallel execution)

---

## 0. Where We Actually Are (verified against live DBs, not docs)

The original execution plan is **mostly DONE** — a parallel agent wave executed Tracks A–D:

| Task | Status | Evidence |
|---|---|---|
| A1–A6 (validation, instruments repair, dedup, amc_id, documents index, junk purge) | ✅ Done | commits 4a9250e…3cd4d63; instruments clean, quarantine on-path |
| C1 Alembic | ✅ Done | 6b2869b; live DB stamped |
| B1 scheme categories | ✅ Parser done; ⚠️ **only 41.2% of schemes categorized** (15,830/38,409) — backfill incomplete |
| B2 AMFI monthly portfolios | ✅ Parser + fetcher built (1f558aa); ⚠️ **0 snapshots from amfi_monthly source** — parser exists but the live backfill never ran to completion. Breadth still 18 AMCs / 39 months / 87K holdings |
| B3 AUM history | ✅ Done | 69,495 rows in scheme_aum_history |
| C2 full-market prices | ✅ Done | 5.14M rows / 4,094 ISINs, 2016–2026 |
| C3 benchmark indices | ✅ Done | NIFTY 50/500, MIDCAP 150, SMALLCAP 250 |
| C4 ISIN↔screener linkage | ✅ Done | 94/111 screener stocks linked (85%), provenance kept |
| D1 consensus_panel | ✅ Built | 18,251 rows, 21 quarters, 7,730 ISINs, category segments |
| D2 scheme_overlap | ✅ Built | 45,688 pairs / 21 quarters |
| D3 backtest notebook | ✅ Executed | 06_consensus_backtest.ipynb |
| Screener fundamentals (this session) | ✅ Working | 111 stocks, 100% accuracy audit, 10y weekly + daily-to-1996 prices |

**The panel EXISTS but is starved:** its two food sources — scheme categories (41%) and all-AMC monthly holdings (18 AMCs) — are the bottleneck for every analytical question in the vision.

---

## 1. Gap Register (everything outstanding, with severity for the thesis)

| # | Gap | Blocks | Severity |
|---|---|---|---|
| G1 | **B2 backfill not run at scale** — all-AMC monthly portfolio history (AMFI monthly files, ~10+ years) is the CORE dataset; today: 18 AMCs, 87K holdings | Q1,2,4,5 + panel breadth | **P0** |
| G2 | **Scheme category coverage 41%** → panel rows with NULL category segments; dissent-by-category (small vs large cap) unreliable | Q4 (the core thesis question) | **P0** |
| G3 | **Screener crawl stopped at 111/462 stocks** (NIFTY-500 universe resolved, checkpointed) — fundamentals enrichment missing for most mid/smallcaps, exactly where the thesis lives | enrichment of panel | **P1** |
| G4 | Screener `growth_summary` parser broken (0 rows) — compounded growth tables unparsed | later-stage enrichment | P2 |
| G5 | Screener BSE/NSE codes NULL for all stocks (broken selector) | robust symbol matching | P2 |
| G6 | No standalone-variant support in screener DB (consolidated only) | completeness | P3 |
| G7 | Panel freshness automation — nothing refreshes `consensus_panel` after new ingestions | ongoing ops | P1 |
| G8 | D3 backtest is a single snapshot; needs re-run + sensitivity checks after G1/G2 land | thesis validation | P1 |
| G9 | Docs stale: MASTER_STATE, session_state, codebase_map don't reflect post-wave reality | agent onboarding | P2 |
| G10 | Screener ingestion_runs: 1 stale failed-run row (Adani Power volume overflow, already fixed+re-ingested) | hygiene | P3 |

---

## 2. Execution Plan — 4 Waves, Parallel Where Safe

### WAVE 1 — Data Breadth (the P0s) — start immediately, 3 parallel agents

**T1. Run the B2 backfill at scale** *(agent A — mostly operational, light coding)*
- Script exists: `scripts/backfill_amfi_monthly_portfolios.py`.
- Sequence: `--max-files 3` smoke run → verify snapshots land (`source_dataset='amfi_monthly'` marker present, holdings counts plausible) → then full-history run in background chunks, checkpointing monthly.
- Politeness: sequential, ≥1s sleep; if AMFI throttles, back off 60s and continue.
- **Verify:** snapshots from amfi_monthly > 100K; distinct months ≥ 120; AMCs covered ≥ 40; spot-check 5 schemes vs live AMFI site.
- Size: M (wall-clock heavy, code-light)

**T2. Complete scheme category coverage** *(agent B — parallel with T1, different tables)*
- Diagnose why B1 backfill stopped at 41%: unmatched scheme names? older months? defunct schemes?
- Extend `scheme_master` matching (fuzzy/normalized-name fallback, AMCI plan/option normalization) and re-run backfill over more months.
- **Verify:** category coverage ≥ 80% of ALL schemes AND ≥ 90% of schemes that actually appear in `consensus_panel` (that's the number that matters).
- Size: M

**T3. Resume screener 500-stock crawl** *(agent C — fully independent, different DB)*
- Universe already resolved: `data/raw/screener/universe_nifty500.csv` (462 slugs), checkpoint at `data/raw/screener/ingest_checkpoint.json` (100 done).
- Continue `python scripts/ingest_chunk.py --chunk-size 50 --delay 3` per chunk in background; ~8 chunks.
- Also fix while crawling: G4 (growth tables parser), G5 (exchange-code selector), G10 (mark stale failed run superseded).
- **Verify:** ≥450 stocks in screener DB, each with 7 statement types + weekly + daily prices; ISIN linkage re-run → ≥350 linked stocks.
- Size: M (wall-clock heavy) | ⚡ fully parallel with T1/T2 (separate DB, separate site)

### WAVE 2 — Refresh & Rebuild (after Wave 1 lands; mostly serial, some parallel)

**T4. Refresh derived layers** *(one agent, serial SQL)*
- `REFRESH MATERIALIZED VIEW consensus_panel;` + rebuild `scheme_overlap` + re-link screener ISINs for newly crawled stocks (C4 script re-run).
- **Verify:** panel rows grow ~5–10×; NULL-category panel rows < 10%; linked screener stocks ≥ 350.
- Size: S

**T5. Panel freshness automation (G7)** *(parallel with T4 prep)*
- Small cron/script: after any `ingest*` run touching `mutual_funds`, refresh panel + overlap. Log refreshes.
- Size: S

### WAVE 3 — Thesis Validation (the point of it all)

**T6. Re-run D3 backtest at full breadth** *(one agent)*
- Re-execute `06_consensus_backtest.ipynb` against the refreshed panel; add sensitivity: smallcap-only cohort, category-divergence cohort (smallcaps accumulating while largecaps exit), min-history filters.
- **Verify:** every decile has ≥100 stock-quarters; forward returns computable for ≥90% via security_prices join; results stable across quarter shifts.
- Size: M

**T7. Vision Definition-of-Done query** *(same agent, after T6)*
- The vision's target: *"Q1-2023: which small-cap schemes held X, AUM fraction, holder evolution, next-12m return vs Nifty Smallcap 250"* — in <5s, numbers spot-checkable.
- Write it as a parameterized query + save output in the backtest notebook.
- Size: S

### WAVE 4 — Hygiene (anytime, parallel filler)

- **T8.** Docs pass: update MASTER_STATE/session_state/codebase_map to post-wave reality; archive stale warnings. *(P2)*
- **T9.** Screener: standalone-variant column decision (G6) — document as out-of-scope unless needed. *(P3)*

---

## 3. Parallelization Map

```
WAVE 1:   T1 (B2 backfill)  ‖  T2 (categories)  ‖  T3 (screener crawl)
             │                   │                    │
             └───────────────────┴────────────────────┘
                                 ▼
WAVE 2:   T4 (refresh panel/overlap/linkage)   ‖  T5 (freshness cron)
                                 ▼
WAVE 3:   T6 (backtest re-run)  →  T7 (DoD query)      [serial, one agent]
                                 ▼
WAVE 4:   T8 (docs)  ‖  T9 (defer decision)                [anytime]
```

- T1/T2/T3 touch disjoint tables and even disjoint databases → safe 3-way parallel.
- T4 must wait for all of Wave 1 (it refreshes from their output).
- T6/T7 must wait for T4. T8/T9 never block anything.

## 4. Standing Rules (carry over)

1. Polite crawling always; screener ≤1 req/s, AMFI ≥1s sleep, Yahoo via yfinance only.
2. History-preserving writes; never delete without backup + explicit approval.
3. ISIN regex guard on everything entering holdings; quarantine stays on-path.
4. Commit per task: `git commit -m "agent: <task-id> <description>"`.
5. Verify with SQL counts shown in the report, not assertions in prose.
6. Screener DB is `postgresql://vlmrouter:***@localhost:5432/screener`; MF DB is `.../mutual_funds`. Never cross-write.

## 5. Definition of Done (unchanged from vision)

One fast query answers: *"In Q1-2023, which small-cap schemes held X, what AUM fraction, how did holders evolve, and what did X return over the next 12 months vs Nifty Smallcap 250?"* — computed from a panel fed by ≥40 AMCs' monthly history, with categories on ≥90% of contributing schemes, and fundamentals+prices available for the stocks involved.
