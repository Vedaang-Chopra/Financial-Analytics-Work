# AMC Parser-Ready Plan — Every Registry AMC Ingesting (Phase 1: ≥2 months each)

> **For Hermes (next session):** Execute waves in order. Each wave = parallel sub-agents,
> one agent per AMC. An AMC is DONE only when it meets the Acceptance Gate below.
> Do NOT run deep-history backfills in this phase — that's Phase 2, after every AMC
> passes here.

**Goal:** All 52 real AMCs in `configs/amc_capability_matrix.yaml` have a working
parser + ingestion path and ≥2 months of portfolio data in PostgreSQL
(`postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds`, container
`vlmrouter-postgres`). Raw files deleted only after persistence is confirmed
(`scripts/apply_retention.py`).

---

## Verified starting state (2026-08-22 evening)

DB: 368K+ holdings / 8.2K snapshots / 33 AMCs with data (other Hermes session's
Playwright discovery pass added ~180K holdings — commit `dda9dde`). A second
background AMFI-monthly backfill may still be running — check with
`ps aux | grep backfill_amfi_monthly` before large runs.

### Tier 1 — READY (19 AMCs, no work needed this phase)
DSP (138 dates), PPFAS (128), Axis (118), Samco (101), NJ (58), Old Bridge (29),
ICICI (20), Angel One (17), Quantum (12), Groww (11), Shriram (9), Quant (5),
ABSL (4), Motilal Oswal (4), Mirae (3), Franklin Templeton (3), Unifi (3),
HSBC (2), Helios (2).
→ Verify-only: spot-check allocation sums ∈ [90,110] for their latest snapshot.
Note HSBC has a suspicious max date of **2028-04-01** (future date) — investigate
that one data bug as part of its verify step.

### Tier 2 — PARTIAL (13 AMCs, exactly 1 date; need archive walks)
LIC (16.2K holdings already), Nippon India (2.5K), Baroda BNP Paribas (2.2K),
UTI (1.4K), HDFC (1.2K), Zerodha (754), Bank of India (239), Capitalmind (149),
JioBlackRock (149), Sundaram (138), Abakkus (108), ITI (64), Invesco (33).

### Tier 3 — MISSING (20 AMCs, no data at all)
SBI*, Kotak Mahindra*, Tata, Bandhan, Edelweiss, Canara Robeco, Union, Navi,
WhiteOak, JM Financial, Bajaj Finserv, 360 ONE, PGIM India, Mahindra Manulife,
Taurus, ASK, AlphaGrep, Choice, TRUST, The Wealth Company.
(* = known JS-heavy portals needing Playwright; 360 ONE previously failed.)

Existing infrastructure to reuse (do NOT rebuild):
- `scripts/playwright_amc_discovery.py` — generic discover/ingest CLI over
  `configs/amc_sources.yaml` (static-first, Playwright fallback) — handles most
  Tier 3 AMCs without writing per-AMC navigators
- `scripts/targeted_portfolio_ingestion.py --amcs <key>` — targeted runs where a
  navigator exists (`mutual_fund_ingestion/agent/portfolio_navigators.py`)
- `mutual_fund_ingestion/agent/parser/portfolio.py` + `portfolio_monthly_amfi.py`
- Validation → quarantine → upsert path is mandatory; never bare upsert
- `scripts/backfill_scheme_amc.py` — rerun after new AMCs onboard

---

## Acceptance Gate (per AMC — all must hold)

1. ≥2 distinct `reporting_date`s spanning ≥45 days
2. Latest date within ~45 days of today
3. ≥1 snapshot with ≥10 holdings whose `SUM(percentage_to_nav)` ∈ [90, 110]
4. Rows landed via validate/quarantine path; no quarantine explosion (>10% quarantined = investigate)
5. `configs/amc_capability_matrix.yaml` entry updated: strategy, formats, status=working, notes
6. Committed: `feat: <amc> parser-ready (N dates, M holdings)` or honest failure entry

Gate query:
```sql
SELECT count(DISTINCT ps.reporting_date) dates,
       min(ps.reporting_date), max(ps.reporting_date),
       count(ph.id) holdings
FROM amcs a JOIN schemes s ON s.amc_id=a.id
JOIN portfolio_snapshots ps ON ps.scheme_id=s.id
LEFT JOIN portfolio_holdings ph ON ph.snapshot_id=ps.id
WHERE a.name ILIKE '<name>%';
```

---

## Wave 1 — Tier 2 archive walks (13 AMCs, ~2 agents × 6–7 AMCs)

Navigators mostly exist (Leg-B/C sessions built them). Per AMC:
1. Run `./financial_env/bin/python -B scripts/targeted_portfolio_ingestion.py \
   --database-url "$DB" --amcs <key> --max-files 300` (background, notify_on_complete)
2. If navigator yields <5 URLs: extend it (year-archive paths / pagination / JSON API)
3. Check gate; commit per AMC
Known quirks from earlier sessions: LIC has an HTTP-API navigator (no Playwright);
Axis-style JSON APIs are common — check `/cms/sites/default/files/Statutory/`
patterns on CMS sites before writing Playwright code.
Agent split: Agent-W1a: LIC, Nippon India, UTI, HDFC, Invesco · Agent-W1b:
Baroda BNP, Zerodha, Bank of India, JioBlackRock, Sundaram, Abakkus, ITI, Capitalmind

## Wave 2 — Tier 3 onboarding via generic discovery (14 easy-ish AMCs)

Use `playwright_amc_discovery.py` (already built & proven). Per AMC:
1. `--mode discover --source <key>` → confirm file links found
2. `--mode ingest` politely → sample first, then fuller pass
3. Gate check; update capability matrix; commit
Split across 2 agents by AUM: W2a: Tata, Bandhan, Edelweiss, Canara Robeco,
Union, Navi, WhiteOak · W2b: JM Financial, Bajaj Finserv, PGIM, Mahindra
Manulife, Taurus, ASK, TRUST, The Wealth Company, Choice, AlphaGrep
(adjust if counts unbalanced)

## Wave 3 — Hard cases (~4 AMCs, 1 strong agent, sequential)

SBI, Kotak Mahindra, 360 ONE (+any Wave-2 failures). These need real Playwright
work (JS portals, login-free but heavily scripted). Strategy ladder per AGENTS.md:
static_html → network_api → playwright → VLM → manual_review. For SBI/Kotak try:
network-tab inspection for JSON endpoints behind the portals before DOM scraping.
If truly blocked after honest attempts: mark `status: failed` + root cause in the
capability matrix — that satisfies the mission ("documented reason", not silence).

## Wave 4 — Cross-cutting verification (single agent)

1. Re-run `backfill_scheme_amc.py` (links new schemes; orphan count should drop)
2. Allocation sanity sweep: flag snapshots outside [90,110] into validation_results
3. Full test suite: `pytest tests/ -q --ignore=tests/test_smoke.py` — no regressions vs 331-passed baseline
4. Regenerate the census table (this file's "starting state") into MASTER_STATE.md
5. Produce final readiness report: X/52 AMCs ready, list of documented-failure AMCs

---

## Coordination rules (all agents)

- Shared repo: re-read files immediately before patching; NEVER `git add -A`;
  stage explicit paths only. Sibling sessions may be active.
- Do NOT delete files (retention is `apply_retention.py`'s job only).
- Polite crawling: sequential, 1–2s sleep, real UA, timeouts; 403 → profile as
  blocked, never retry-storm. Public disclosures only.
- Never hand-edit canonical tables; upserts are idempotent.
- One agent per AMC during ingestion; two agents may share the DB safely
  (conflict-safe upserts) but must not edit the same files simultaneously.
- Commit per AMC with the acceptance-gate numbers in the message.

## Phase 2 (explicitly OUT OF SCOPE now)

Full-history backfill for all AMCs (max-files 500+, year archives to origin).
Unlocks automatically once this plan completes. DSP/PPFAS/Axis/Samco already
have deep archives from earlier legs — don't redo them here beyond gate needs.
