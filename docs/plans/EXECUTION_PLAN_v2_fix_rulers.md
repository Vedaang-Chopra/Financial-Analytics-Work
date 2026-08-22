# EXECUTION PLAN v2 — Fix the Rulers, Then Flood With History

**Created:** 2026-08-22
**Supersedes:** waves of `EXECUTION_PLAN_consensus_platform.md` (Tracks A–D are DONE — see git log; do not redo them).
**Source evaluation:** full-project forensic review 2026-08-22 (tests run, DB internals inspected, D3 notebook audited). Key findings that motivate this plan:

| # | Finding | Evidence |
|---|---|---|
| 1 | Structural look-ahead bias in backtest entry dates | D3 enters on quarter start; disclosures publish ~10 days after quarter end |
| 2 | Unadjusted prices corrupt forward returns | 255 ISINs show < −80% single-day moves (unadjusted splits/bonuses) |
| 3 | Plan-level double counting inflates consensus | `schemes` = AMFI plan codes; Direct+Regular variants counted as separate holders; no fund-level entity exists |
| 4 | AUM weighting suspiciously complete | 100% of panel rows have AUM basis but only 165/358 snapshot-schemes have AUM history → fallback may attach stale/mismatched months |
| 5 | History breadth missing | 358 schemes w/ snapshots; 69% from 2026; only 24 schemes have ≥6 quarters |
| 6 | Category coverage incomplete | ~41–59% filled depending on measurement; segmentation columns systematically undercount |
| 7 | Smallcap thesis untestable today | 129 / 18,251 panel rows involve any smallcap holder (0.7%) |
| 8 | No operational automation or freshness alerts | all pipelines manual scripts; ICICI navigator already rotted once |
| 9 | Repo hygiene debt | 293 MB data/tmp, 53 stray test_*.db, 205 MB reports in-tree, 31 unpushed commits, hardcoded DB creds in tracked scripts |

**Rules of engagement:** same as v1 plan — read AGENTS.md first; incremental; tests written+passing per task; verification query shown; never delete without backup + approval; polite crawling; commit per task (`git commit -m "agent: <task-id> <description>"`).

**Environment facts:** unchanged from v1 plan §0 (repo root, venv `./financial_env`, PG `mutual_funds` + `screener` DBs on Docker `vlmrouter-postgres`, Alembic live at head `b3a7e5c1d904`, test baseline **339 passed / 6 known failures** — do not regress).

---

## 1. Task Dependency Graph

```
TRACK E (analytical correctness — P0)      TRACK F (data breadth — P0)
E1 fund-level rollup ──────┐               F1 FULL AMFI monthly history backfill
                           │               F2 category completion
E2 adjusted prices ────────┤               F3 AUM date-match audit
                           ▼
                    H1 panel rebuild ←── needs E1+E2+E3+F1+F2
E3 look-ahead fix ─────────┘        │
                                    ▼
                             H2 pre-registered backtest re-run

TRACK G (hardening/hygiene — fully independent, run anywhere)
G1 freshness watchdog   G2 scheduler   G3 repo hygiene + push   G4 docs consolidation
```

- **Nothing analytical gets measured again until E1–E3 land.** The current null backtest result is an artifact of bias + thin data, not evidence about the thesis.
- Track G never blocks anything; run its tasks whenever an agent is idle.
- F1 is long-running and network-bound; give it a dedicated background process, not a subagent that blocks.

---

## TRACK E — Analytical Correctness Blockers (P0)

### E1. Fund-level rollup entity (do FIRST — two other tasks depend on it)
- **Problem:** `schemes.scheme_code` is AMFI *plan-level*. Direct-Growth and Regular-IDCW of one fund are distinct rows holding identical portfolios → `holders_total` over-counts by up to ~2× per dual-plan fund.
- **Do:**
  1. Alembic migration: new table `funds` (id UUID PK, amc_id FK, base_name TEXT, normalized_base_name TEXT, UNIQUE(amc_id, normalized_base_name)).
  2. New column `schemes.fund_id UUID NULL REFERENCES funds(id)` (keep scheme rows intact — history-preserving, nothing dropped).
  3. Rollup resolver: strip plan/option tokens (`direct|regular|idcw|growth|dividend|payout|reinvestment`) from `scheme_name`, normalize whitespace/case; group within AMC. Ambiguity rule: only merge schemes whose holding-overlap in the latest shared snapshot ≥90%, else leave separate and log.
  4. One-off backfill script `scripts/backfill_fund_rollup.py` (backup-first), idempotent, prints merge report: N funds created, M schemes linked, K ambiguous left alone.
  5. Update `consensus_panel` view definition to count `DISTINCT fund_id` (falling back to scheme_id where fund_id IS NULL) and add `holders_*` category columns keyed off fund category = mode of member schemes' categories.
- **Verify:**
  ```sql
  SELECT count(*) FROM schemes WHERE fund_id IS NULL AND amc_id IS NOT NULL; -- expect small, logged
  SELECT count(DISTINCT fund_id) FROM funds;                                  -- sanity: < scheme count
  ```
  Spot-check: PPFAS Flexi Cap Direct & Regular map to ONE fund; panel holder count drops accordingly.
- **Size:** M | Blocks: H1, and F1 should write fund_id going forward (wire into `upserts.py::upsert_portfolio` via the same resolver).

### E2. Corporate-action-adjusted prices
- **Problem:** raw bhavcopy closes make a 10:1 split look like −90%. 255 ISINs already show impossible moves inside the backtest windows.
- **Do:**
  1. New table `corporate_actions(isin TEXT, ex_date DATE, action TEXT CHECK (action IN ('split','bonus','rights')), ratio NUMERIC NOT NULL, source_url TEXT, UNIQUE(isin, ex_date, action))` — Alembic revision.
  2. Fetcher: corporate-action feed (NSE/BSE announcements pages, or derive-and-flag approach below if feeds prove unreliable).
  3. **Deterministic detection fallback (mandatory):** scan `security_prices` for |1-day move| > 60%; for each candidate, verify against action feed; actions found get stored, unresolved candidates go to a review CSV in `data/reports/`. Never auto-adjust without a confirmed action row.
  4. New table or view `security_prices_adj` storing adjustment factors; forward-return SQL switches to adjusted closes. Keep raw `security_prices` untouched.
- **Verify:** rerun impossible-move scan on adjusted series → expect near-zero (genuine crashes like −85% business failures may remain; those are real and stay).
- **Size:** L | Independent of everything except C2 (done). ⚡PARALLEL-SAFE with E1.

### E3. Disclosure-aligned entry dates (look-ahead fix)
- **Problem:** backtest enters at quarter start using information published ~10 days later.
- **Do:**
  1. Determine actual publication lag empirically: AMFI monthly files have upload timestamps; sample 12 months, compute median/max lag (expect 8–15 days).
  2. Change entry rule in D3 SQL to `qtr_end + lag_buffer` (use max observed lag + 1 day safety). Exit stays entry + 12 months.
  3. Add a `--entry-mode {quarter_start,disclosure_aligned}` flag to the notebook stage so both variants remain reproducible.
- **Verify:** notebook runs both modes; disclosure-aligned results shift; the delta is itself reported (it quantifies how much the old result was biased).
- **Size:** S | Depends on nothing; ⚡PARALLEL-SAFE. Do before H2 obviously.

---

## TRACK F — Data Breadth (P0, the actual product dataset)

### F1. UNLEASH the historical AMFI monthly backfill ⭐ HIGHEST VALUE
- **Problem:** B2 ran bounded (~35K holdings added); 2017–2024 nearly empty. The thesis needs multi-year, survivorship-safe history.
- **Do:**
  1. First inventory what's retrievable: enumerate AMFI monthly portfolio archive coverage (how many years × months × format stability). Write findings to `docs/reports/amfi_monthly_archive_inventory.md`.
  2. Extend `scripts/backfill_amfi_monthly_portfolios.py`: resumable checkpoint file (which month done), sequential requests ≥1s sleep, retry-with-backoff, monthly progress log.
  3. Run order: oldest→newest so history lands first. Bound each invocation (`--months N`) and run as background process; monitor, don't fire-and-forget.
  4. After every ~10 months ingested: run integrity spot-checks (pct-sum gate pass-rate, ISIN validity rate, junk-row rate) — watch for format drift across years.
  5. Wire fund_id assignment (from E1 resolver) into the upsert path BEFORE bulk writes so we don't need another backfill.
- **Verify:** `SELECT extract(year FROM reporting_date), count(*) FROM portfolio_snapshots GROUP BY 1 ORDER BY 1;` shows continuous coverage from earliest retrievable year; distinct schemes with snapshots grows from 358 toward thousands; ≥24 → hundreds of schemes with ≥6 quarters.
- **Size:** XL wall-clock, M code | Depends on: E1 wired into upserts (else second backfill needed later). Can START while E2/E3 proceed once E1 merges.

### F2. Category completion (~41% → ≥90%)
- **Problem:** "which kinds of managers agree" breaks without categories; B1 got live schemes only.
- **Do:** extend `backfill_scheme_master.py` over historical months; handle defunct-scheme ceiling explicitly (report achievable-max separately from overall rate); fill `schemes.benchmark` too where master provides it.
- **Verify:** `SELECT round(100.0*count(*) FILTER (WHERE category IS NOT NULL)/count(*),1) FROM schemes;` ≥ 90 among schemes having ≥1 snapshot.
- **Size:** S–M | ⚡PARALLEL-SAFE with everything.

### F3. AUM date-match audit
- **Problem:** 100% of panel rows carry AUM basis but only 165/358 snapshot-schemes have AUM history → likely stale-fallback attaching wrong-month AUM silently.
- **Do:** read `consensus_panel` view definition; instrument the fallback: add `aum_month_used` column; audit query reporting distribution of |panel qtr − aum month|. Policy: if gap > 3 months → NULL basis (honest blank beats fake precision); update view.
- **Verify:** audit query shows ≤3-month gaps for ≥95% of non-null basis rows.
- **Size:** S | ⚡PARALLEL-SAFE.

---

## TRACK G — Hardening & Hygiene (independent, fill idle agents with these)

### G1. Freshness watchdog (cron)
- Daily check: did today's NAVAll ingest land? Is newest bhavcopy ≤ 2 trading days old? Newest AMFI monthly present when month-end +15d passed? Panel refreshed?
- Output: quiet when healthy, alert message on staleness (no_agent script pattern; empty stdout = silent).
- **Verify:** kill one pipeline manually, watchdog fires; restore, goes silent.
- Size: S

### G2. One-command daily orchestrator
- `scripts/daily_update.py`: NAV increment → bhavcopy fetch → AMFI monthly (if new month available) → category/AUM top-up → `REFRESH MATERIALIZED VIEW consensus_panel` → coverage summary printed. Idempotent, safe to double-run. Watchdog (G1) monitors ITS output.
- **Verify:** run twice back-to-back; second run no-ops cleanly.
- Size: M

### G3. Repo hygiene + push (do immediately, half-day)
- Push the 31 unpushed commits (single biggest durability risk).
- Delete 53 stray `test_*.db`; purge `data/tmp/mutual_funds/runtime` older than 30 days (backup manifest first); move `data/reports` large binaries out-of-tree or gitignore policy decision.
- Move hardcoded `postgresql://vlmrouter:***@localhost...` defaults to env var with config fallback (new code stops adding them; don't rewrite git history).
- Close out stale plans: archive `SPRINT_CURRENT.md`, story-notebook series, backlog batches J/K/L/M/N, Phase 3/4 specs to `docs/archive/` with a README note pointing at this plan + VISION.md.
- **Verify:** `git status` clean-ish; `git push` succeeds; watchdog unaffected.
- Size: S | ⚡PARALLEL-SAFE | Do this wave 1.

### G4. Docs consolidation (after G3 archives)
- Rewrite `MASTER_STATE.md` from measured DB state (like the 2026-08-21 pass but post-consensus-pivot); delete dead-pipeline claims or mark DEAD explicitly; single "start here" pointer chain: VISION.md → this plan → AGENTS.md.
- Size: M

---

## TRACK H — Re-validation (only after E1+E2+E3+F1+F2)

### H1. Full panel rebuild
- Refresh `consensus_panel` (fund-keyed, adjusted prices, aligned entries, honest AUM blanks, ≥90% categories). Record before/after metrics: row counts, holders distributions, smallcap share (target: >>0.7%).
- **Verify:** known-case spot-check against manual AMFI lookup; duplicate-holder ratio (same fund twice per isin-qtr) = 0.

### H2. Pre-registered backtest re-run
- Before looking at results, WRITE DOWN the hypothesis in the notebook header: one panel definition, one benchmark (SMALLCAP 250), one horizon (12m), deciles by fund-count. Also register a holdout: most recent 4 quarters excluded from reading until the rule is frozen.
- Report BOTH entry modes (old vs disclosure-aligned) so the look-ahead bias magnitude is documented forever.
- Include liquidity filter variant (median daily turnover floor) as a secondary cut.
- Honest-conclusion cell mandatory, same standard as current notebook.

---

## 2. Recommended Execution Waves

| Wave | Tasks | Mode | Notes |
|---|---|---|---|
| 0 | G3 (hygiene + PUSH) | 1 agent, immediate | Durability first; half-day |
| 1 | E1 ‖ E2 ‖ E3 | 3 parallel agents (different files: migrations/upserts ‖ market_data ‖ notebooks/sql) | E1 gates F1 |
| 2 | F1 (background process, oldest-first) ‖ F2 ‖ F3 ‖ G1 | F1 = dedicated background runner + monitor; rest parallel agents | Longest phase; weeks of wall-clock for full history |
| 3 | G2 ‖ G4 | 2 parallel | While F1 continues |
| 4 | H1 → H2 | serial, single integrator | Human reviews H2 output before any conclusion is drawn |

**Wave-1 caution (E1):** the rollup ambiguity rule matters more than speed. Over-merging creates fake consensus; under-merging just leaves counts conservative. Prefer under-merge + log.

**Wave-2 caution (F1):** format drift across years is guaranteed. Iterate parser against ALL sampled years on disk first (`data/datasets/Monthly Reports October 2024/` + whatever the archive yields), then bounded live run (--months 3), verify, then unleash. Never bulk-write while parser is being changed.

## 3. Definition of Done (this plan)

1. All four bias fixes verifiably landed (impossible-move scan ≈ clean; dup-fund-per-panel-cell = 0; entry dates ≥ publication lag; AUM gaps ≤3mo or NULL).
2. Holdings history covers every retrievable AMFI month, with per-year snapshot counts documented.
3. Categories ≥90% among snapshotted schemes.
4. One-command daily update + silent-unless-broken watchdog running.
5. H2 executed under pre-registration, both entry modes reported, honest conclusion written — whatever the sign of the result.

## 4. Standing Warnings

1. Do NOT delete or overwrite raw `security_prices` when adding adjusted series — additive tables/views only.
2. Do not restart NAV history backfill if running (`ps aux | grep backfill_amfi`).
3. Any migration dropping/renaming existing columns → stop and ask user first.
4. If AMFI archive turns out shallower than expected (e.g., <5 years online), record the boundary honestly in the inventory doc and evaluate exchange-shareholding-patterns as the depth supplement instead of forcing it.
