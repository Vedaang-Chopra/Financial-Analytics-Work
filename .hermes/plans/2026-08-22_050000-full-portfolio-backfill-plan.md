# Full-Coverage Portfolio Disclosure Ingestion Plan

> **For Hermes:** Execute legs in the order given. Legs B, C, D are independent of each other and can run as parallel agents once Leg A completes.

**Goal:** For every AMC, collect portfolio disclosures (fortnightly + monthly Excel/ZIP files) for every scheme they offer, going back as far as data is published, with everything parsed, validated, and saved in structured PostgreSQL tables — raw files deleted after confirmed DB persistence.

**Architecture:** Reuse the existing `targeted_portfolio_ingestion.py` pipeline (navigator → download → parse → stage → validate → upsert). Fix the two known structural gaps first (AMC linkage, ICICI parser), then scale from "bounded samples" to full historical backfill per AMC, then onboard the remaining ~45 registry AMCs. Polite crawling throughout: sequential requests, delays, timeouts, public disclosures only.

**Tech Stack:** Python 3.14 (`financial_env`), SQLAlchemy + PostgreSQL 18 (`vlmrouter-postgres/mutual_funds`), pandas/openpyxl/xlrd parsers, Playwright (JS-heavy AMCs only).

**Current verified state (2026-08-22):**
- 8 AMCs have holdings in `portfolio_holdings`: DSP (~7,550), Axis (~4,000), ABSL (~2,467), PPFAS (~1,553), Mirae (~315), Invesco (~56), LIC (~21), Quant (~46)
- ~19,120 holdings total across 384 snapshots; 0 quarantined; upserts idempotent
- Parser bugs fixed & verified: frozen-dataclass zip bug, OLE2 engine sniffing, unguarded float casts, TOC-sheet junk, end-of-portfolio markers, fraction-vs-percent normalization
- Known gaps: ICICI downloaded but never parsed; ~303 schemes orphaned (`amc_id IS NULL`); all ingestion so far used `--max-files ≤ 20` samples; ~45 registry AMCs not onboarded

---

## Leg A — Foundation Fixes (sequential, do first, ~1 session)

Everything else depends on these. No new AMCs until A is done.

### Task A1: Commit current working state
The repo has 26 modified + 219 untracked files including all parser fixes. Commit before anything else so parallel agents start from a clean tree.

```bash
git add mutual_fund_ingestion/ scripts/targeted_portfolio_ingestion.py \
        scripts/convert_to_notebook.py tests/test_agent.py \
        notebooks/mutual_fund_ingestion/
git commit -m "fix: portfolio parser — zip frozen-dataclass bug, OLE2 engine sniffing,
guarded float casts, TOC/end-marker filtering, pct normalization;
fix targeted ingestion sys.path; regenerate exploration notebook"
```
Verify: `git status` shows clean tree for code paths; `pytest tests/ -q --ignore=tests/test_smoke.py --ignore=tests/test_agent_db.py` → 136 passed.

### Task A2: Backfill scheme → AMC linkage
303 schemes exist without `amc_id`, hiding their holdings from per-AMC rollups.
- File: `scripts/populate_scheme_amc.py` (exists — verify it covers both strategies: name-pattern matching AND snapshot source_url host matching)
- Run: `./financial_env/bin/python scripts/populate_scheme_amc.py --database-url "$DATABASE_URL" --dry-run` first; review counts; then run live
- Verify:
```sql
SELECT count(*) FROM schemes WHERE amc_id IS NULL;   -- expect near 0
SELECT a.name, count(DISTINCT ps.scheme_id) FROM amcs a
JOIN schemes s ON s.amc_id=a.id JOIN portfolio_snapshots ps ON ps.scheme_id=s.id
GROUP BY a.name ORDER BY 2 DESC;                     -- Axis/ABSL/DSP now appear
```
- Add regression test: upserting a scheme with an `amc_hint` metadata field must set `amc_id`. Likely touchpoint: `mutual_fund_ingestion/agent/upserts.py`.
Commit: `feat: backfill scheme-amc links; auto-link schemes on upsert`

### Task A3: Parse the 110 ICICI ZIPs already downloaded
ICICI files sit in `raw_artifacts` but produced 0 snapshots (pre-fix zip bug era). Do NOT re-download; re-parse locally.
- Write: `scripts/reparse_artifacts.py` — stream `raw_artifacts` rows by host filter, call `parse_portfolio_zip(content, metadata)` directly, reuse `UpsertManager.upsert_canonical()`
- Note: `raw_artifacts` currently stores metadata only (no blob) — if content is absent from `local_path`, fall back to re-download via stored `source_url` with checksum dedup
- Verify: `SELECT count(*) FROM portfolio_snapshots ps WHERE ps.source_url LIKE '%icicipruamc%'` > 0; spot-check one scheme's allocation sums to ~100%
Commit: `feat: artifact reparse tool; ICICI backfill`

### Task A4: Idempotency proof before scaling
Re-run ingestion twice for one AMC at small `--max-files 5`; assert row counts identical after second pass.
- Verify: `SELECT count(*) FROM portfolio_holdings` unchanged between runs; zero new quarantine rows
Commit: `test: idempotency check script`

---

## Leg B — Deep Historical Backfill for the 8 Working AMCs (parallel agent #1)

Objective: max-depth pull per AMC, oldest available → present. Each AMC gets its own bounded run; polite delay between requests.

Order by value (most-current-first, then dig backward):

| Priority | AMC | Navigator | Expected depth |
|---|---|---|---|
| B1 | PPFAS | static | monthly since ~2023 + fortnightly debt |
| B2 | DSP | static+zip | fortnightly since ~2016 (zips seen back to Jul 2016!) |
| B3 | ABSL | zip | monthly debt zips seen to Nov 2021 — probe deeper |
| B4 | Mirae | playwright | monthly, recent years |
| B5 | Invesco | playwright | fortnightly xlsx archive |
| B6 | LIC | playwright | fortnightly/monthly |
| B7 | Axis | xls | fortnightly archive on transact.axismf.com |
| B8 | Quant | TBD | profile first (only 1 test snapshot exists) |

Steps per AMC (repeat pattern):
1. Extend navigator to enumerate ALL archive pages/pagination (many AMCs paginate or year-archive folders; e.g. PPFAS uses `/2023/`, `/2024/` path segments)
2. Run: `./financial_env/bin/python scripts/targeted_portfolio_ingestion.py --database-url "$DATABASE_URL" --amcs <key> --max-files 500`
3. Record per-AMC coverage into `docs/01_status/session_state.md` table
4. Verify per-AMC: distinct reporting dates count increases; latest date ≈ today; no quarantine spike

Verification query per AMC:
```sql
SELECT count(DISTINCT ps.reporting_date) AS dates, min(ps.reporting_date), max(ps.reporting_date),
       count(ph.id) AS holdings
FROM portfolio_snapshots ps
JOIN schemes s ON s.amc_id = a.id ...
WHERE a.name = '<AMC>';
```
Commit per AMC: `data: deep backfill <AMC> (N files, M holdings, dates X–Y)`

## Leg C — Onboard Remaining AMCs (parallel agent #2)

Objective: extend coverage from 8 toward the full 53-AMC registry. Work strictly in deterministic strategy order (static_html → network_api → playwright → VLM → manual), one AMC at a time, sample-size runs first.

1. Build triage list from `configs/amc_capability_matrix.yaml` (42 entries `not_run`, 21 `not_profiled`). Prioritize by AUM tier: SBI, HDFC, ICICI(done in B/C overlap), Nippon, Kotak, UTI, Aditya Birla(deep in B), Franklin, Canara Robeco, Union, Baroda BNP...
2. For each AMC:
   - Locate portfolio disclosure page (provider profile JSON may already hint URL)
   - Static HTML? → add navigator function in `mutual_fund_ingestion/agent/portfolio_navigators.py` + entry in `AMC_NAVIGATORS` + entry in `AMC_PORTFOLIO_CONFIGS`
   - JS-rendered? → use existing Playwright browser module (`agent/browser.py`) pattern like Mirae/Invesco navigators
   - Update capability matrix yaml entry: strategy, formats, status
3. Sample-run each new AMC (`--max-files 3`) → confirm records > 0 → then hand off to deep-backfill queue (Leg B pattern)
4. Log failures honestly in matrix (`status: failed`, notes with root cause) — do NOT skip silently

Acceptance per AMC: ≥1 snapshot with ≥10 holdings whose pct_to_nav sums within 90–110%.
Commit: `feat: navigator for <AMC>` per AMC (small commits keep review easy)

## Leg D — Raw File Retention Policy (parallel agent #3, after A1)

User requirement: local file clutter deleted once data is safely in DB.

1. Confirm DB-only guarantee first: `staging_rows.raw_row_json` already stores parsed record payloads; `documents`/`raw_artifacts` store provenance. Data survives without local files.
2. Use existing retention machinery: `agent/artifact_storage.py` (`LocalFilesystemBackend`, `RetentionPolicy`, `storage cleanup-temp` CLI)
3. Configure policy for `portfolio_disclosure`: retain-in-hot 0 days post-validation (i.e., delete temp downloads after successful commit)
4. Add safety gate: cleanup only deletes files whose `checksum` exists AND whose artifact's staging rows reached canonical tables (join through `dataset_candidate_id`/run)
5. Run: `python -m mutual_fund_ingestion storage stats` → `storage retention-apply` → `storage cleanup-temp`
6. Also clean repo-root test litter: 50+ `test_*.db` SQLite files (verify none referenced by tests, then delete)
7. Verify: holdings/snapshots counts unchanged pre/post cleanup; `du -sh data/` shrinks; repo root clean

Commit: `feat: delete-after-ingest retention for portfolio artifacts`

---

## Cross-cutting Verification (after all legs)

1. **Coverage report** (new): `python -m mutual_fund_ingestion portfolio coverage` per AMC — expected-vs-stored using each AMC's publishing frequency
2. **Allocation sanity**: for every snapshot, sum(percentage_to_nav) ∈ [90, 110] — flag outliers to quarantine
```sql
SELECT count(*) FILTER (WHERE pct_sum BETWEEN 90 AND 110) AS ok,
       count(*) FILTER (WHERE pct_sum NOT BETWEEN 90 AND 110) AS bad
FROM (
  SELECT ps.id, SUM(h.percentage_to_nav) AS pct_sum
  FROM portfolio_snapshots ps JOIN portfolio_holdings h ON h.snapshot_id=ps.id
  GROUP BY ps.id
) t;
```
3. **Test suite**: `pytest tests/ -q --ignore=tests/test_smoke.py` — expect ≥161 passing, no regressions vs baseline
4. **Final summary doc** update: `docs/01_status/MASTER_STATE.md` metrics table (AMCs working, holdings total, date ranges)

## Parallelization Map

```
A1 commit ──► A2 amc-links ──► A3 icici ──► A4 idempotency
                    │
                    ├──► Leg B (deep backfill, 8 AMCs)      [agent 1]
                    ├──► Leg C (onboard remaining AMCs)     [agent 2]
                    └──► Leg D (retention/cleanup)          [agent 3]
```
Legs B and C contend on the same Postgres tables but upserts are conflict-safe; stagger large runs (B at night, C sampling daytime) to respect rate limits. Leg D must wait until B/C runs for the day complete (deletes only validated-persisted files).

## Risks / Open Questions

- **Politeness vs depth**: full archives mean hundreds of requests per AMC. Mitigate: sequential, 1–2s delay, honor robots/403 immediately, stop-and-profile rather than retry-storm.
- **Axis history**: transact portal serves old fortnightly XLS; unclear how far back — probe before promising depth.
- **Quant**: single test snapshot; needs real profiling before backfill.
- **VLM/browser AMCs** (some of the 45) will need LM Studio running — flag when hit, don't block other legs.
- **Open question**: should `raw_artifacts.local_path` blobs be kept in object storage (S3 backend already stubbed) instead of deleted? Default plan deletes; say the word to switch to cold storage instead.
