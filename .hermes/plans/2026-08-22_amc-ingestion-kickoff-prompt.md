# Kickoff Prompt — Full AMC Portfolio Ingestion (Remaining Work)

Copy everything below this line into the new session.

---

## Mission

Make portfolio-disclosure ingestion work for **every AMC in the registry** (53 AMCs in `configs/amc_capability_matrix.yaml`), collect **every scheme's** fortnightly/monthly portfolio disclosures **as far back as data is published**, parse them, and save everything in **PostgreSQL** (`postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds`, container `vlmrouter-postgres`). Raw downloaded files get deleted only after their data is confirmed in the DB. No local file clutter.

**Current state (2026-08-22):** 8 AMCs have holdings in `portfolio_holdings` (DSP, Axis, ABSL, PPFAS, Mirae, Invesco, LIC, Quant — ~19,120 rows). Parsers are fixed and verified (zip frozen-dataclass bug, OLE2/xlrd engine sniffing, float-cast guards, TOC/end-marker filtering, fraction-vs-percent normalization). The full execution plan is at `.hermes/plans/2026-08-22_050000-full-portfolio-backfill-plan.md` — read it first.

## Execution order

**Phase A — foundation (do sequentially first):**
1. Commit all uncommitted work (`git add` code paths, commit; verify `pytest tests/ -q --ignore=tests/test_smoke.py` has no regressions).
2. Backfill ~303 orphaned schemes (`schemes.amc_id IS NULL`) using `scripts/populate_scheme_amc.py` (dry-run first, then live). Add auto-linking on upsert in `agent/upserts.py`.
3. Re-parse ICICI's 110 downloaded-but-unparsed ZIPs (`raw_artifacts`, host `www.icicipruamc.com`) — write `scripts/reparse_artifacts.py`, reuse `parse_portfolio_zip` + `UpsertManager`.
4. Idempotency check: re-run one AMC twice at `--max-files 5`, confirm zero new rows on pass 2.

**Phase B/C/D — parallel agents after Phase A:**
- **Agent 1 (Leg B):** Deep backfill for the 8 working AMCs — extend navigators in `mutual_fund_ingestion/agent/portfolio_navigators.py` to walk year-archive pages, run `scripts/targeted_portfolio_ingestion.py --amcs <key> --max-files 500`. Priority: PPFAS, DSP, ABSL, Mirae, Invesco, LIC, Axis, Quant.
- **Agent 2 (Leg C):** Onboard remaining ~45 AMCs in AUM-priority order (SBI, HDFC, Kotak, Nippon, UTI, Franklin, Canara Robeco, Union, Baroda BNP, ...). Deterministic strategy order per AMC: static_html → network_api → playwright → VLM → manual. Add navigator + `AMC_NAVIGATORS` + `AMC_PORTFOLIO_CONFIGS` entries, sample-test with `--max-files 3`, then queue for deep backfill. Record failures honestly in `configs/amc_capability_matrix.yaml`.
- **Agent 3 (Leg D):** Delete-after-ingest retention — configure `agent/artifact_storage.py` so a raw file is deleted only when its checksum exists AND its rows reached canonical tables. Also clean the 50+ `test_*.db` files in repo root. Verify holdings counts unchanged before/after.

## Rules

- Polite crawling: sequential requests, 1–2s delay, timeouts, honest 403 handling (profile, never retry-storm). Public investor disclosures only.
- Upserts are idempotent — safe to re-run; never hand-edit canonical tables.
- Per-AMC acceptance: ≥1 snapshot with ≥10 holdings whose `SUM(percentage_to_nav)` lands in 90–110.
- Commit per unit of work (`feat: navigator for <AMC>`, `data: deep backfill <AMC> (N files, M holdings)`).
- Update `docs/01_status/MASTER_STATE.md` metrics table as coverage grows.
- If a scheme's data can't be found, log why in the capability matrix — never silently skip.

## Definition of done

Every registry AMC has either (a) portfolio holdings in `portfolio_holdings` with its full published date range, or (b) a documented, evidence-backed reason it can't be ingested. `SELECT count(*) FROM schemes WHERE amc_id IS NULL` ≈ 0. Zero quarantine surprises. Test suite green. Raw files deleted post-persistence.

Start with Phase A now. Report per-AMC numbers (files, holdings, date ranges) as each completes.
