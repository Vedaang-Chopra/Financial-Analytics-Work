# Financial Data Intelligence Platform — Full System Audit

**Date:** 2026-08-22
**Method:** Live code inspection, PostgreSQL introspection (`mutual_funds` + `screener` DBs on vlmrouter-postgres), pytest execution (162 passed / 6 failed), storage analysis, documentation cross-referencing. Every claim below is backed by a file, table, query, or test run. Nothing was deleted or modified.

---

## 1. Executive Summary

**What has actually been built.** A working mutual-fund ingestion core exists and has proven itself against live data: AMFI NAV ingestion (a **full 2006→today historical backfill is running right now** — `nav_history` grew from 15,495 to 359,071+ rows across 240 distinct dates while this audit ran), portfolio-disclosure ingestion for ~8 AMCs via targeted navigators, an Excel/ZIP parser family hardened by many real-world fixes, idempotent upserts into 23 PostgreSQL tables, staging/validation/quarantine tables, and a separate working screener.in equity engine (`screener_ingestion/`, its own `screener` database, ~6.5K line items).

**How far from the vision.** The foundation is real but the system's *operational surface* does not match what the docs claim:

- The documented CLI (`nav backfill`, `portfolio backfill`, `census`, `coverage`, `storage`) **does not exist** in `cli.py`. Those commands are unreachable.
- `NAVPipeline`, `PortfolioPipeline`, `CoverageCalculator`, `ArtifactStorageManager` — all marked "✅ Complete" in `MASTER_STATE.md` — are **imported by nothing except each other**. Dead code from the operator's perspective; everything that actually runs lives in ad-hoc `scripts/*.py`.
- Coverage tables were populated once by hand (scheme_coverage shows 100% NAV coverage — false now that history backfill changed reality) and `ingestion_quality_metrics` / `coverage_snapshots` have never been written.

**Biggest problems, ranked:**

1. **Two competing "production paths"**: the generic task-URL agent (`run-agent`) vs. hardcoded per-AMC navigator scripts. Neither covers the other's gaps; docs describe a third (pipeline classes) that isn't wired.
2. **Correctness defects in canonical writes**: garbage ISINs in `instruments` (2,807 numeric/`-` values), section-header rows stored as holdings ("Total" ×4,026 instruments; 1,253 duplicate holdings within snapshots), `portfolio_holdings` unique key silently collides when `isin` is NULL, `portfolio_snapshots.amc_id` never set by the upsert path.
3. **No orchestration/reliability layer**: nothing schedules, retries end-to-end, or detects drift; ICICI navigator already broke after a site change.
4. **Documentation drift is severe** — three generations of architecture coexist (phased plan → task-url agent → pipeline classes), with status files contradicting both the code and each other.

**Is the foundation worth continuing? Yes.** No rewrite needed. Schema is fundamentally sound and extensible; parsers work; the data model preserves history correctly where it's populated. What's needed is consolidation: wire one entry point, fix the P0 data-integrity bugs, delete-or-wire dead layers, then broaden AMC/dataset coverage.

---

## 2. Current System Architecture (as inferred from code)

```
                         ┌──────────────────────────────────────────────┐
   CONFIG LAYER          │ configs/amc_sources.yaml (55 sources)        │
                         │ configs/amfi_dataset_census.yaml (20 sets)   │
                         │ configs/amc_capability_matrix.yaml (53 AMCs) │
                         └──────────────┬───────────────────────────────┘
                                        │ (read only by profiling/ + source_registry.py)
                                        ▼
 ┌───────────────────── LIVE PATH A: scripts/targeted_portfolio_ingestion.py ──────────────┐
 │  per-AMC navigators (portfolio_navigators.py, icici_navigator.py)                       │
 │    → requests.get → parse_file('portfolio_disclosure', ft) → RawArtifact + StagingRow   │
 │    → UpsertManager.upsert_portfolio → amcs/schemes/instruments/snapshots/holdings       │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
 ┌───────────────────── LIVE PATH B: scripts/backfill_amfi_nav_history.py (RUNNING NOW) ───┐
 │  AMFI DownloadNAVHistoryReport_Po.aspx (88-day windows)                                 │
 │    → parse_file('nav_history','text') → UpsertManager.upsert_nav_history                │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
 ┌───────────────────── PATH C: cli.py run-agent (generic crawler, works, rarely used) ────┐
 │  IngestionRunner → DiscoveryEngine (BFS) → ArtifactCollector → ArtifactProcessor         │
 │    → validate_and_filter_records → quarantine_rows → upsert_canonical                   │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
 ┌───────────────────── DEAD CODE (documented as complete, wired to nothing) ──────────────┐
 │  nav_pipeline.py · portfolio_pipeline.py · coverage.py · artifact_storage.py            │
 │  scheme_identity.py (only used by scripts/reconcile_schemes.py)                         │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
                                        ▼
              PostgreSQL (23 tables) ← also: screener DB (separate schema, screener_ingestion/)
```

## 3. Repository Map (important parts only)

| Path | Responsibility | Verdict |
|---|---|---|
| `mutual_fund_ingestion/cli.py` (447 ln) | Only real CLI: bootstrap-sources, profile-providers, phase-1, run-agent, init-db, inspect-run, retry-failed | LIVE |
| `agent/db.py` (531 ln) | 23 SQLAlchemy models | LIVE |
| `agent/upserts.py` (512 ln) | Canonical upserts (NAV/AMC/schemes/portfolio) | LIVE |
| `agent/artifact_processor.py` | download→parse→stage→validate→quarantine→upsert | LIVE (path C) |
| `agent/parser/*` | nav (semicolon-fixed), portfolio (Excel/CSV/ZIP, 630 ln of hard-won heuristics), scheme_master, amc, metadata stubs | LIVE; metadata = stubs |
| `agent/runner.py` (575 ln) + discovery/browser/extract/vlm | Generic task-URL crawler | LIVE but superseded in practice |
| `agent/nav_pipeline.py`, `portfolio_pipeline.py`, `coverage.py`, `artifact_storage.py` | "Dedicated pipelines", storage abstraction, monitoring | **DEAD — zero external importers** (verified by grep incl. notebooks/scripts/tests) |
| `scripts/backfill_amfi_nav_history.py` | Full NAV history via AMFI history endpoint | LIVE, running now |
| `scripts/targeted_portfolio_ingestion.py` | Per-AMC portfolio ingestion w/ hardcoded configs | LIVE (de-facto production) |
| `scripts/{load_amcs,populate_scheme_amc,reconcile_schemes,clean_and_resave}.py` | Manual repair/backfill utilities | LIVE one-shots — symptoms of missing pipeline ownership |
| `profiling/` (10 modules) | Phase 1A/1B source registry + provider profiling, JSONL artifacts | LIVE, frozen, clean |
| `screener_ingestion/` (5 modules) + `screener` DB | Equity fundamentals engine (stocks/snapshots/periods/line_items/prices/peers) | LIVE, separate stack |
| `tests/` (7 files, 168 tests) | Unit + SQLite-integration + fixtures | Mostly meaningful; see §9 |
| `notebooks/mutual_fund_ingestion/` (9) + `screener_ingestion/` (3) | Review/exploration | See §16 note below |
| `docs/` (137 md files) | Status/architecture/plans/historical | Heavily drifted |
| Repo root: 45 stray `test_*.db` SQLite files (~90 MB) | Abandoned experiment outputs | Garbage, gitignored |
| `data/tmp/mutual_funds/runtime/` (289 MB, 516 run dirs) | Temp downloads never cleaned | Policy violated |

## 4. Current Data Coverage Matrix (traced end-to-end)

Legend: ✅ operational · 🟡 partial · ❌ absent

| Dataset | Source | Discovery | Fetcher | Parser | Model | PG table | History | Validation | Tests | Operational? | Limitations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NAV daily snapshot | AMFI NAVAll.txt | ✅ census yaml | ✅ | ✅ nav_text (semicolon-only fix verified by tests/test_nav_amfi_semicolon.py) | ✅ | nav_history (15.5K obs pre-backfill) | 🟡 latest-window only | ✅ validate_nav_record | ✅ | ✅ | 0.0-NAV rows quarantined (~108/day suspended schemes) |
| NAV full history | AMFI DownloadNAVHistoryReport_Po.aspx | ✅ (discovered 2026-08-22) | ✅ script, 88-day windows | ✅ same parser | ✅ | nav_history → 359K+/152 dates and climbing | ✅ 2006→now | ✅ | 🟡 script untested | ✅ (in progress) | Script not integrated; no scheduler |
| Portfolio disclosures | 8 AMC sites (PPFAS/DSP/Mirae/Invesco/ICICI/ABSL/LIC/Axis configs; Groww/Nippon done earlier) | 🟡 hardcoded in script | 🟡 static+playwright navigators | ✅ excel/csv/zip (strongest component) | ✅ | portfolio_snapshots(384)/holdings(19.1K) | ✅ multi-period (2021-06→2026-08 observed; earlier AUDIT saw 2013+) | 🟡 record-level only, no snapshot-level pct-sum gate at write time | ✅ unit | 🟡 works for covered AMCs | ~45 of 53 AMCs uncovered; ICICI selector broken post-site-change |
| AMC master | curated YAML + load_amcs.py | ✅ Phase 1A | n/a | ✅ amc_html (unused in practice) | ✅ | amcs (55) | ❌ mutable row overwrite | 🟡 | 🟡 | 🟡 | amfi_code never populated |
| Scheme master | AMFI monthly | ✅ cataloged | ❌ | 🟡 CSV/HTML only, no Excel parser | ✅ | schemes (partial) | ❌ | ✅ validator exists | ✅ | ❌ | No fetcher; category/benchmark mostly NULL |
| Scheme category/benchmark | AMFI monthly | ✅ cataloged | ❌ | ❌ | columns exist (category, benchmark) | empty | ❌ | ❌ | ❌ | ❌ | Blocked on Excel parser |
| Instruments/securities | derived from portfolios | n/a | n/a | ✅ | 🟡 | instruments (206,781 rows!) | n/a | ❌ none | ❌ | 🟡 | 92% NULL-ISIN duplicates; 2,807 garbage ISINs; junk names |
| Sector allocation | parsed from portfolios | — | — | 🟡 sector column 96% empty | ✅ | portfolio_holdings.sector | — | ❌ | ❌ | ❌ | No normalized taxonomy |
| AUM/AAUM | AMFI form | ✅ cataloged | ❌ | ❌ (parse_tabular_csv stub) | ❌ no table | — | ❌ | ❌ | ❌ | ❌ | |
| TER | AMFI form | ✅ cataloged | ❌ | ❌ stub | ❌ no table | — | ❌ | ❌ | ❌ | ❌ | |
| Factsheets/SID/KIM/SAI | AMC sites | ✅ cataloged | 🟡 discovered by agent | ❌ PDF stub returns empty | ❌ documents only | documents (1,797) | ❌ | ❌ | ❌ | ❌ | |
| Fund managers | factsheets | ❌ | ❌ | ❌ | ❌ no table | — | ❌ | ❌ | ❌ | ❌ | Vision item, absent |
| Equities/fundamentals | Screener.in | ✅ | ✅ | ✅ | ✅ | **separate `screener` DB** (11 stocks, 6524 line items, 1044 prices) | ✅ snapshots | ✅ verify vs live | ✅ | ✅ | Not linked to MF platform (different DB, different models) |

**Bottom line:** today only **NAV (daily + full history being backfilled)** and **portfolio disclosures for ~8 AMCs** genuinely reach PostgreSQL. Everything else is cataloged, stubbed, or absent.

## 5. PostgreSQL Schema Assessment

**Sound:** UUID surrogate PKs + natural keys (`normalized_name`, `scheme_code`, `(scheme_code, nav_date)` UNIQUE); proper FK graph; history-preserving design (`nav_history` unique (scheme_code,nav_date); `portfolio_snapshots` unique (scheme_id,reporting_date)); staging/quarantine/provenance separation; JSONB escape hatches; 6-table coverage subsystem designed well.

**Defects (evidence):**

1. **Plans/options conflated with schemes.** `schemes.scheme_code` = AMFI *plan-level* code; Direct/Regular/Growth/IDCW variants are separate rows distinguished only by name text and `metadata_json.plan/option` (upserts.py:160–176). There is no `fund`/parent entity, so "how has the fund changed month over month" requires string surgery. 1,698 duplicated `normalized_scheme_name` groups exist today.
2. **No migration system.** Schema = `Base.metadata.create_all()` (db.py:525). Any model change on existing data requires manual ALTER or drop. This is the single biggest structural risk going forward.
3. **`documents` upsert target** `(scheme_id, reporting_date, document_type, source_url)` exists as a unique index (created manually — it's NOT in db.py's model! The model defines no constraint; the live DB has `documents_scheme_date_type_url_key`). Code and DB have diverged; a fresh `init-db` would break `on_conflict_do_update`.
4. **`instruments.isin` has no unique constraint** (only PK). Combined with NULL-isin creation path (upserts.py:442–450 creates a new instrument whenever lookup misses), you get 206,781 instruments vs 15,181 distinct ISINs, plus 2,807 invalid values (`0.00059…`, `-`) that came from parser fallbacks writing percentage cells into ISIN fields.
5. **`portfolio_holdings` unique (snapshot_id, security_name, isin)** — in Postgres, NULL isin makes the constraint non-enforcing; result: 1,253 duplicate security rows within snapshots already.
6. **`portfolio_snapshots.amc_id` never written** by `upsert_portfolio` (upserts.py:378–384 doesn't set it) — 384/384 NULL; AMC attribution only via join through schemes (which still misses 180 snapshots whose scheme has NULL amc).
7. **Extensibility:** reasonably good — `documents` is dataset-generic; adding equities/corpor-actions tables alongside is feasible. But mutual-fund-specific assumptions (e.g., scheme identity resolution inside `upserts`) should be pushed behind a domain layer before the second asset class lands.

## 6. End-to-End Pipeline Assessment

Working chain (portfolio): navigator → requests/playwright download → `parse_file` → StagingRow → `validate_and_filter_records` → quarantine (table exists, currently 0 rows because the script path skips validation entirely — see defect) → `UpsertManager.upsert_portfolio`.

Breaks/gaps found by tracing:

1. **Path A (targeted_portfolio_ingestion.py) bypasses validation and quarantine completely.** It calls `upsert_manager.upsert_canonical(...)` directly after staging (script lines 171–179) — `validate_and_filter_records` is never invoked. This is exactly why garbage ISINs and "Total" holdings are in canonical tables. The validated path exists (artifact_processor.py:170) but production doesn't use it.
2. **Path B (NAV backfill script)** likewise stages raw artifacts but calls `upsert_canonical` directly — no validation, no quarantine, though NAV parsing itself is solid.
3. **Discovery knowledge isn't reused.** Provider profiles (Phase 1B JSONL artifacts, `detected_strategy`) exist, yet Path A hardcodes URLs/configs in the script body (lines 33–83) — violating the project's own "learn once, persist, reuse" principle.
4. **Idempotency:** genuinely good where it matters — re-runs upsert cleanly (proven: repeated NAV windows produce no dupes thanks to UNIQUE(scheme_code,nav_date)).
5. **Restartability:** weak. Run records stuck in `running` (3 runs, oldest 2026-08-21 23:14) with no watchdog; retry_queue exists but `retry-failed` merely resets flags ("Re-run the agent with the same task URLs").
6. **Observability:** `inspect-run` prints counts, `validation_results` has 43,680 uniform "passed/info/schema_validation" rows (noise, written even by legacy path), quality-metrics table never populated. You can answer "what ran" but not "what was rejected and why" on the production path.

## 7. Source / AMC Coverage

- Registry: 53 AMCs + AMFI + SEBI (`configs/amc_sources.yaml`); capability matrix marks most `not_profiled`.
- Portfolio-proven AMCs: PPFAS, DSP, Mirae, Invesco, ICICI (⚠ selector broken), Groww, ABSL, LIC, Axis (last three configured; success varies). Nippon ingested previously.
- Snapshot distribution in DB is heavily skewed: DSP 163, ABSL 16, PPFAS 15, Mirae 9, Quant 1, **unlinked 180**.
- NAV: universal (all 8,108+ scheme codes) via AMFI.
- Factsheet/TER/AUM: cataloged everywhere, implemented nowhere.
- Strategy order (static→api→browser→VLM→manual) is respected in `profiling/` and partially in navigators, but VLM components (`playwright_vlm_navigator.py` pointing at a LAN endpoint `192.168.1.10:9000`) are environment-bound and untested.

## 8. Code Quality & Architecture Audit

**Good:** layered-model intent is real in `profiling/`; parser module is disciplined (pure functions → ParserResult); shared `utils/` is small and sane; naming conventions followed; logging present throughout.

**Problems:**

1. **Dead-code layer presented as complete** — the four "NEW" modules (§2) total ~2,300 lines nobody executes. Worst case: `artifact_storage.py` (696 lines, S3/tiered retention) — while actual temp dirs accumulate 289 MB of never-cleaned runtime artifacts. Documentation-driven development outran integration.
2. **Production logic lives in scripts/** — `targeted_portfolio_ingestion.py` contains orchestration + HTTP + config (AMC_PORTFOLIO_CONFIGS dict) outside the package; `backfill_amfi_nav_history.py` reimplements window iteration that `NAVPipeline.run_backfill` was written for. Two implementations of the same concept, neither canonical.
3. **Config scattered:** AMC endpoints duplicated between `configs/amc_sources.yaml`, `configs/amc_capability_matrix.yaml`, and inline dicts in two scripts.
4. **DB session hygiene:** per-file sessions opened/closed manually with try/finally everywhere; `UpsertManager.write_validation_result` depends on mutable `_run_id` class state (upserts.py:507) — fragile implicit coupling.
5. **Generated artifacts mixed with source:** 45 `test_*.db` files + `.DS_Store` files tracked in tree edges; 402 data files (71 MB incl. 247 tmp screenshots) committed to git despite the "raw files transient" philosophy.
6. **`parser/__init__.py` router** uses if/elif dispatch instead of the declared registry map — minor, but the map and dispatch can drift (they already differ in error behavior).
7. **Circular-import dodges via function-local imports** in upserts/pipelines — symptom of entangled domain models.

## 9. Testing Assessment

Executed baseline: **162 passed, 6 failed** (4 DB-integration runner tests failing on `pages_visited=0` fixture-seeding issue — pre-existing; 2 smoke tests need network).

Meaningful coverage: NAV semicolon-format regression tests (`test_nav_amfi_semicolon.py` — guards the worst historical bug), parser unit tests with real fixtures (xlsx/html/csv), profiling round-trips, screener parse tests, SQLite-based upsert integration tests.

Critical gaps:
- **No test exercises `validate_and_filter_records` → quarantine → canonical** as an integrated path (which is why Path A could skip validation unnoticed).
- Zero tests for any `scripts/*.py` (the de-facto production entry points).
- Zero tests for navigators (understandable — network — but no recorded-playback fixtures either).
- No test catches the NULL-isin holding-collision or instrument-garbage cases (they'd fail today).
- Coverage/pipeline classes: untested AND unused — double liability.
- No CI config anywhere.

## 10. Documentation vs Code (contradiction register)

| Item | Docs say | Reality | Class |
|---|---|---|---|
| CLI `nav/portfolio backfill`, `census`, `coverage`, `storage` (MASTER_STATE.md §CLI) | Verified working | Subcommands don't exist in cli.py | **OUTDATED/FALSE** |
| `NAVPipeline`/`PortfolioPipeline`/`CoverageCalculator`/`ArtifactStorage` "Complete ✅" | Operational | No importer anywhere; never executed | **DOCUMENTATION ONLY** |
| AGENTS.md phase table: Phase 2–5 "Not yet implemented" | — | Phase 2 discovery, parsing, staging, validation, canonical loads all demonstrably ran (60 ingestion_runs, 20K staged rows) | **OUTDATED** |
| MASTER_STATE test baseline "148 passed, 3 skipped" | — | Actual today: 162 passed / 6 failed | OUTDATED (drifted both directions) |
| MASTER_STATE DB "SQLite dev / PG prod, 17→23 tables" | — | Accurate on tables; SQLite used by tests only | PARTIALLY IMPLEMENTED |
| database_schema.md "20 SQLAlchemy tables" vs codebase_map "23" | — | 23 in code; doc internally inconsistent | UNCLEAR (minor) |
| Storage policy spec (task_url_agent spec #10): temp cleanup at run end | — | 516 run dirs / 289 MB remain under data/tmp | **LIVE SPEC, VIOLATED BY BEHAVIOR** |
| AUDIT_REPORT.md (2026-08-21) claims amcs=0, provenance NULL | — | Fixed since (amcs=55; 1,197/1,797 documents linked) — report itself is stale but honest | SUPERSEDED |
| FIXES_SUMMARY.md claims debt fields fixed | — | coupon=0, maturity=0, asset_class=0 in DB; rating=15,703 ✓ | PARTIALLY TRUE (parser emits, some paths don't store) |
| codebase_map lists screener_ingestion? | Absent | Entire second platform undocumented in maps | MISSING |
| Three architecture generations (05_planned phases / 03_implemented task_url_agent specs / "NEW pipelines") | All current-looking | Mutually inconsistent | **SUPERSEDED ×2** |

## 11. Storage Assessment

Permanent-on-disk inventory (589 MB `data/`):
- `data/tmp/mutual_funds/runtime/` — **289 MB, 516 run dirs, 993 files** of downloaded XLSX/HTML/screenshots that policy says must be deleted post-parse. Cleanup is implemented only in dead code (`storage cleanup-temp`). Safe to make fully transient.
- `data/reports/mutual_funds/exploration/` — 208 MB of notebook-generated HTML/CSV dumps (91 MB csv_exports). Regenerable analytics output masquerading as reports. Should be excluded from retention/git.
- `git` tracks 402 data files (71 MB): Oct-2024 monthly portfolio workbooks (137), 247 runtime debug screenshots, legacy datasets. Contradicts the transient-artifact philosophy; safe candidates for `git rm --cached` + ignore (nothing deleted from disk).
- Root `test_*.db` (~90 MB): abandoned SQLite experiments; gitignored already, deletable pending user approval.
- Genuinely worth keeping permanently: `raw_artifacts` metadata (already in PG, checksums present for new-path artifacts), Phase 1A/1B profile JSONL (small), parser fixtures.
- Provenance adequacy: PG retains source URL, checksum, size, fetch time, run id, parser name/confidence, staging raw-row JSON — sufficient to explain lineage **without keeping files**. Retention posture can safely become aggressive-delete after parse.

## 12. Gap Analysis (Vision vs Reality)

**A. Data coverage:** AUM/AAUM, TER, category/benchmark, fund managers, factsheet-derived data: MISSING (cataloged only). Scheme master fetcher: MISSING. Sector taxonomy: MISSING. Screener equity data exists but is an island (separate DB, no cross-links).

**B. Pipeline:** validation bypass on the production path (P0); no unified orchestrator; discovery knowledge not consumed at runtime; no scheduling.

**C. Database:** no migrations; no parent-fund entity above plans/options; instruments unconstrained/duplicated; snapshots.amc_id unwritten; documents constraint exists only in live DB, not in models.

**D. Historical data:** NAV history solved as of today (backfill running). Portfolio history: preserved per reporting_date where ingested, but depth limited to what AMCs publish online (typically months-years, varies). Manager/AUM/TER history: nothing. Coverage tables contain stale "100%" claims that will mislead analytics.

**E. Provider/source:** ~85% of AMCs unprofiled/unimplemented; ICICI regression shows no drift detection; VLM path environment-dependent.

**F. Parser:** scheme_master_excel (blocks category/AUM joins), TER/AUM excel, PDF (factsheet/SID/KIM) all absent; unknown Excel columns dropped without raw preservation (staging keeps them, canonical doesn't).

**G. Validation:** production path skips validators entirely; no cross-field checks (pct-sum ≈100 per snapshot enforced only informally — measured avg 108.9%, only 350/384 within 90–105); no referential sanity checks (ISIN format) before insert; quarantine never exercised in prod.

**H. Reliability:** no scheduler, no alerting (alerts table designed, never filled), stuck `running` runs, no end-to-end retry, polite-crawl settings inconsistent between scripts (one has sleep, one doesn't).

**I. Architecture/code-quality:** dead 2.3K-line layer; production logic in scripts; config triplication; no single CLI surface; generated artifacts in repo.

**J. Testing:** no integration test of validate→canonical path; no script tests; no navigator contract tests; no CI.

**K. Documentation:** MASTER_STATE is materially false in its "Completed"/"CLI" sections; three conflicting architectures; screener platform undocumented; AGENTS.md phase table inverted relative to reality.

## 13. Recommended Target Architecture (incremental)

Keep the modular monolith + PostgreSQL. Five moves:

1. **Single entry point.** Extend `cli.py` with real subcommands (`nav backfill`, `portfolio ingest --amc …`, `coverage update`, `storage cleanup-temp`) that call the *existing* pipeline/script logic moved into `agent/`. Delete the script bodies afterward. (Current: logic split between cli/scripts. Target: thin CLI → package orchestration.)
2. **Make the validated path mandatory.** Route all ingestion through `ArtifactProcessor.process()` so staging→validation→quarantine→upsert is unavoidable. Add snapshot-level checks (pct-sum band, ISIN regex) to validators.
3. **Adopt Alembic.** Baseline migration = current 23-table schema (including the documents unique index that exists only in the live DB). All future model changes versioned.
4. **Fix the identity model incrementally:** add `funds` parent table (or `parent_scheme_id`) later, but *first* enforce `instruments(isin)` uniqueness + cleanup job, and populate `snapshots.amc_id` in the upsert. Plan/option normalization can ride on `scheme_identity.py`, which should finally get wired into the upsert path instead of a one-off reconcile script.
5. **Consolidate docs** (§15 recommendation below) and demote dead modules explicitly: either wire `coverage.py` into every run's completion hook (it's the cheapest win — tables already exist) or archive it.

Explicitly rejected: microservices, ORM replacement, new frameworks, rewriting parsers (they're the strongest asset).

## 14. Prioritized Remediation Plan

### P0 — correctness blockers
| Task | Solves | Files | Verify | Size |
|---|---|---|---|---|
| P0-1 Route scripts through validation | Garbage stops entering canonical | `scripts/targeted_portfolio_ingestion.py`, `scripts/backfill_amfi_nav_history.py`, `agent/artifact_processor.py` | Quarantine count > 0 after next run; zero new invalid ISINs | S |
| P0-2 ISIN guard + instruments dedup migration | 206K→~15K instruments; valid format enforced | new Alembic migration + `upserts.py` lookup | `SELECT count(*) FROM instruments WHERE isin !~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'` = 0 | M |
| P0-3 Holding uniqueness fix | Duplicate holdings impossible | migration: partial unique index `(snapshot_id, security_name)` WHERE isin IS NULL + dedupe script | dup-count query = 0 | S |
| P0-4 Set snapshots.amc_id in upsert | AMC rollups correct | `upserts.py::upsert_portfolio` | 384 NULL → 0 after rerun/backfill SQL | S |
| P0-5 Sync `documents` unique index into db.py model | Fresh init-db matches prod | `db.py` | create-all on scratch DB shows index | S |
| P0-6 Stop storing section headers | Clean holdings | `parser/portfolio.py` JUNK_ROW_PATTERNS extension ('total', 'net current assets'… already partly there—close the observed leaks) + one-off cleanup | junk_like count → 0 | S |

### P1 — ingestion completeness
| Task | Solves | Files | Verify | Size |
|---|---|---|---|---|
| P1-1 Integrate NAV backfill script into package + CLI (`nav backfill`) | History capability owned by codebase, schedulable | move `backfill_amfi_nav_history.py` logic → `agent/nav_backfill.py`, wire CLI | CLI rerun is no-op-idempotent; row count stable | M |
| P1-2 Wire `PortfolioPipeline` (or delete it): make it call navigators + ArtifactProcessor | One portfolio path | `portfolio_pipeline.py`, `cli.py` | `portfolio ingest --amc ppfas` produces identical rows to script | M |
| P1-3 Scheme-master Excel parser + fetcher (AMFI monthly) | Category/benchmark/AUM joins unlock | `parser/scheme_master.py`, `cli.py` | categories populate for ≥80% schemes | M |
| P1-4 AUM + TER parsers/tables (`scheme_aum_history`, `scheme_ter_history`) | Vision datasets land | new parser + models | monthly rows per scheme queryable | M |
| P1-5 AMC expansion wave using capability matrix (top-10 by AUM first) | Coverage | navigators + registry | ≥18 AMCs with current-month snapshots | L |

### P2 — architecture/refactoring
- P2-1 Alembic adoption + baseline (prereq for P0-2/3) — M
- P2-2 Consolidate AMC configs to `configs/` only; scripts read registry — S
- P2-3 Decide fate of `artifact_storage.py`: implement `cleanup-temp` via it, else archive/ — S
- P2-4 Move remaining script orchestration into package; scripts shrink to arg-parsing — M
- P2-5 Wire `scheme_identity.py` resolver into upserts (replace brand-alias guesswork) — M

### P3 — reliability/operations
- P3-1 Scheduler (cron/launchd) for: NAV incremental daily, portfolio weekly, coverage update after each — S
- P3-2 Run watchdog: fail stuck `running` runs >N hours; alert row into `coverage_alerts` — S
- P3-3 Temp-dir cleanup at run end + `storage cleanup-temp` CLI; purge the 289 MB backlog (with user approval) — S
- P3-4 Drift detection: navigator failure → open alert (would have caught ICICI) — M
- P3-5 Populate `ingestion_quality_metrics` per run — S

### P4 — future platform
- P4-1 Unify screener DB with platform (shared instruments/entity ids or cross-db linkage views)
- P4-2 Fund-manager assignment history table + factsheet PDF parser
- P4-3 Analytics views (accumulation, overlap, concentration) as SQL views, not app code
- P4-4 Corporate actions / indices ingestion designs

## 15. Immediate Next Actions (ordered)

1. **Let the running NAV backfill finish; then re-verify counts and mark the skill/doc state** (it changes every number in this audit's §4).
2. **P0-1** — put validation back on the production path (smallest change, largest correctness gain).
3. **P0-2/P0-3/P0-6** — data-integrity migration batch + one-off cleanup (with backup, per your usual workflow).
4. **P0-4 + P0-5** — trivial upsert/model fixes in the same pass.
5. **P1-1** — promote the NAV backfill into the package + CLI; retire the script.
6. **P2-1** — Alembic baseline before any further schema work.
7. **P1-3** — scheme-master Excel parser (unlocks category/benchmark for analytics).
8. **P3-1/P3-3** — scheduler + temp cleanup (disk relief is immediate).
9. **Docs reconciliation pass** — rewrite `MASTER_STATE.md` to match reality; mark the two superseded architecture generations; declare one canonical architecture (recommend: task_url_agent spec + wired pipelines).
10. **AGENTS.md refresh** — fix the inverted phase table; add "check cli.py for real command surface before trusting docs"; add screener_ingestion to the map.
