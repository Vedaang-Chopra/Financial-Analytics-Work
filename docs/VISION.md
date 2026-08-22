# VISION — Consensus/Dissent Mutual-Fund Intelligence Platform

_Last updated: 2026-08-22. This is the canonical product vision. All architecture, ingestion, and analysis work serves this document._

---

## The Core Idea

Indian mutual funds employ professional research teams that continuously buy and sell stocks based on deep fundamental analysis. **Their portfolio disclosures are public, monthly evidence of that research.**

We are building a platform that turns thousands of these disclosures into a single analytical panel:

> For every **stock × time period**: how many fund managers held it, how much money (AUM-weighted) stood behind it, which *kinds* of managers agreed vs disagreed (small-cap vs large-cap, growth vs value), how those consensus patterns formed and dissolved over history — and then, whether stocks that showed strong consensus went on to outperform.

**The thesis in one sentence:** When many independent professional investors converge on the same stock — especially where disagreement existed before — that convergence is information, and it can be systematically measured, backtested, and used as one input for stock selection.

### Why small caps matter most
Mega-cap stocks are held by everyone by default — consensus there carries no signal. The informational edge lives where:
- Managers had to make an active, non-index-driven choice;
- Analyst coverage is thinner, so the market hasn't already priced the collective insight;
- Dissent exists and *resolves* over time (e.g., 3 small-cap managers hold a stock → 12 hold it two quarters later).

### What this is NOT
- Not an automatic recommendation engine. MF behavior is one research signal among others.
- Not a scraper project. The ingestion system is infrastructure; the product is the consensus panel + validated performance linkage.

---

## The Analytical Questions the Data Must Answer

1. Which stocks are held by the largest number of distinct schemes? How has that count changed quarter over quarter?
2. Which stocks are being accumulated (new holders added) or exited (holders dropped)? By whom?
3. For a given stock: what is the AUM-weighted conviction across all holding schemes?
4. Which manager categories agree/disagree on each stock? (e.g., small-cap funds converge on X while flexi-cap funds avoid it)
5. How similar are any two funds' portfolios over time (overlap coefficient), and when do they diverge?
6. After a consensus pattern forms, what did the stock return over the following quarters — absolute, and relative to its appropriate benchmark (Nifty Smallcap 250 for smallcaps, etc.)?

Question 6 is the validation loop: patterns without measured outcomes are just observations.

---

## Data Required (and current status)

| # | Dataset | Feeds question | Source | Status |
|---|---|---|---|---|
| 1 | Portfolio holdings, ALL AMCs, multi-year monthly (incl. exited stocks — survivorship matters) | 1,2,4,5,6 | AMFI monthly all-AMC portfolio files (historical archive) + per-AMC sites for recency | Partial: ~8 AMCs only |
| 2 | Scheme category / sub-category | 4 | AMFI monthly scheme master | Missing (column exists, NULL) |
| 3 | Scheme AUM/AAUM monthly | 3 | AMFI AUM dataset | Missing entirely |
| 4 | Daily prices for every ever-held ISIN | 6 | NSE/BSE bhavcopy | Missing in MF DB (screener DB covers 11 stocks only) |
| 5 | Benchmark index closes (NIFTY 50/500, MIDCAP 150, SMALLCAP 250) | 6 | NSE indices | Missing entirely |
| 6 | NAV history | Context/perf sanity | AMFI NAVAll.txt + history endpoint | ✅ Done (full 2006→today) |
| 7 | Stock fundamentals | Later-stage enrichment | Screener.in (`screener` DB) | ✅ Working; needs ISIN↔stock linkage |

Explicitly deprioritized: TER granularity, factsheets/SID/KIM PDFs, fund-manager names, risk parameters. They don't feed the consensus signal.

## Target End State

A PostgreSQL-backed panel where one fast query answers:

*"In Q1-2023, which small-cap-focused schemes held stock X, what fraction of their AUM did that represent, how did the holder count evolve from prior quarters, and what did X return over the following 12 months versus the Nifty Smallcap 250?"*

Delivered via: `portfolio_holdings` (all AMCs, quarterly-bucketable) ⨝ `scheme_aum_history` ⨝ `schemes.category` ⨝ `security_prices` ⨝ `index_prices`, surfaced through a `consensus_panel` materialized view.

## Where the Execution Plan Lives

**`docs/plans/EXECUTION_PLAN_consensus_platform.md`** — the authoritative build sequence (Track A correctness → Track B parsers → Track C market data → Track D analysis layer, with parallel-subagent orchestration waves). Read that before doing any implementation work.

Related audit (background, why-not): `docs/audits/2026-08-22_full_system_audit.md`.

## Non-Negotiable Principles

1. **Survivorship safety** — ingest historical disclosures including stocks funds exited; sampling only current state invalidates every backtest.
2. **History-preserving schema** — nothing overwrites point-in-time facts.
3. **Instrument identity integrity** — valid ISINs are the join key across funds and to stock data; garbage ISINs poison everything downstream.
4. **Deterministic-first ingestion** — static HTTP → API → browser automation → manual review, per project AGENTS.md.
5. **PostgreSQL is the durable dataset** — raw files are transient after parse+validate; provenance stays.
6. **Compliance** — public disclosure documents only; polite crawling; no investment advice language anywhere in the product.
