# Checkpoint Plan — Financial Analytics Mutual Fund Ingestion
# Covers: Current state → Milestone 3 (real AMC documents downloaded)
# Designed: 2026-06-27
# Test baseline at design time: 125 passed, 0 skipped

---

## Overview

| Checkpoint | Name | Tests | Status |
|---|---|---|---|
| 0 | System Foundation | 125 | ACTIVE |
| 1.1 | Validation Coverage (Epic G) | ~131 | blocked on CP0 |
| 1.2 | Discovery Tests (Epics H, I, J) | ~140 | blocked on CP1.1 |
| 1.3 | Portfolio + NAV Coverage (Epics P, N, L) | ≥145 | blocked on CP1.2 |
| 2 | Phase 2 Document Discovery | 145+ | blocked on CP1.3 |
| 3 | Real AMC Documents Downloaded | 145+ | blocked on CP2 |
| 4 | Canonical Tables (placeholder) | TBD | blocked on CP3 |
| 5 | Analytics Layer (placeholder) | TBD | blocked on CP4 |

---

## Checkpoint 0 — System Foundation

**Goal**
Make the system demonstrable, architecturally clean, and documented before any new feature work.

**Prerequisite**
None. This is the entry point.

**Tasks (in order)**

TASK-C001: Refactor runner.py — extract upserts.py and artifact_processor.py
  Per docs/04_in_progress/REFACTOR_runner.md exactly.
  Extract all _upsert_* methods and _write_validation_result to agent/upserts.py.
  Extract _download_and_process_artifact to agent/artifact_processor.py.
  runner.py must shrink from 821 → ~300 lines.
  All 125 tests must pass after.

TASK-C002: Discover and document the PostgreSQL connection
  Two postgres containers are running. The project container is vlmrouter-postgres at localhost:5432.
  Attempt: ./financial_env/bin/python -m mutual_fund_ingestion init-db --database-url postgresql://postgres@localhost:5432/mutual_funds
  If that fails, try: postgresql://postgres:postgres@localhost:5432/mutual_funds
  Document the working DATABASE_URL in docs/01_status/MASTER_STATE.md under "Database".
  If no database named mutual_funds exists, create it: createdb -h localhost -U postgres mutual_funds
  Write the verified DATABASE_URL in exactly one place for all future Pi sessions to read.

TASK-C003: Write docs/02_architecture/system_overview.md
  A ~40-line Mermaid flowchart + prose description of the full pipeline.
  Must cover: Phase 1A (source registry) → Phase 1B (profiling) → Task-URL Agent (runner.py) →
  discovery → download → parse → validate → upsert → canonical tables.
  No new architecture decisions — describe what exists.

TASK-C004: Write docs/02_architecture/database_schema.md
  Document all 17 SQLAlchemy tables from agent/db.py.
  For each table: name, purpose, key columns, relationships.
  ~60 lines total. No diagrams required.

TASK-C005: Make 00_system_checkpoint.ipynb runnable
  Open notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb.
  Ensure all cells execute without error (use --dry-run / --limit flags for live calls).
  Update any cells that reference stale test counts or old file paths.
  The notebook must show: test count (125), DB table count (17), AMC source count (53).
  Note: if nbconvert not installed, install it: ./financial_env/bin/pip install nbconvert

TASK-C006: Update MASTER_STATE.md
  Correct test count from 122/3 skipped → 125 passed.
  Remove "runner.py LAYER VIOLATION" from Known Blockers (resolved by C001).
  Add "Database" section with verified DATABASE_URL.
  Add "Checkpoint 0 complete" status line.

**Exit Condition**
```bash
./financial_env/bin/python -m pytest tests/ -q --tb=no
# Expected: 125 passed
ls mutual_fund_ingestion/agent/upserts.py mutual_fund_ingestion/agent/artifact_processor.py
# Expected: both files exist
```

**Demonstrable Output**
```bash
open notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb
# Shows: 125 tests passing, 17 tables, 53 AMC sources, DB connected
```

**Verification Prompt**
Verifier reads: test output, MASTER_STATE.md, upserts.py, artifact_processor.py, runner.py line count.
Answers: Did runner.py shrink to ≤350 lines? Do all 125 tests pass? Is DATABASE_URL documented?

---

## Checkpoint 1.1 — Validation Coverage (Epic G)

**Goal**
Add missing validators for scheme_master and AMC record types. 6 new tests.

**Prerequisite**
Checkpoint 0 exit condition passed.

**Tasks (in order)**

TASK-G001: Add validate_scheme_master_record() to agent/validate.py
  Per docs/06_plans/active/BATCH_E_validation.md TASK-G001 exactly.

TASK-G002: Add validate_amc_record() to agent/validate.py
  Per docs/06_plans/active/BATCH_E_validation.md TASK-G002 exactly.

TASK-G003: Wire scheme_master and AMC validators into validate_and_filter_records
  Per docs/06_plans/active/BATCH_E_validation.md TASK-G003 exactly.

TASK-G004: Add tests for scheme_master and AMC validation (4 tests)
  Per docs/06_plans/active/BATCH_E_validation.md TASK-G004 exactly.

TASK-G005: Verify staging_rows.raw_row_json preserves original record
  Per docs/06_plans/active/BATCH_E_validation.md TASK-G005 exactly.

TASK-G006: Add test for quarantine reason propagation
  Per docs/06_plans/active/BATCH_E_validation.md TASK-G006 exactly.

**Exit Condition**
```bash
./financial_env/bin/python -m pytest tests/ -q --tb=no
# Expected: ≥131 passed
./financial_env/bin/python -m pytest tests/test_agent.py -k "validation or quarantine or scheme_master or amc_record" -v
# Expected: all pass
```

**Demonstrable Output**
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "validation" -v
```

**Verification Prompt**
Verifier reads: validate.py, test_agent.py (validation section), pytest output.
Answers: Are all 6 G-epic functions implemented? Do 4+ new tests pass? Are validators wired into validate_and_filter_records?

---

## Checkpoint 1.2 — Discovery Tests (Epics H, I, J)

**Goal**
Test BFS discovery, relevance scoring, dataset classification, browser path, and network path. ~9 new tests.

**Prerequisite**
Checkpoint 1.1 exit condition passed.

**Tasks (in order)**

TASK-H001: Test high/low relevance URL scoring (2 tests)
  Per docs/06_plans/active/BATCH_F_discovery.md TASK-H001 exactly.

TASK-H002: Test link extraction from HTML fixture (1 test)
  Per docs/06_plans/active/BATCH_F_discovery.md TASK-H002 exactly.

TASK-H003: Test dataset classification by URL pattern (3 tests)
  Per docs/06_plans/active/BATCH_F_discovery.md TASK-H003 exactly.

TASK-H004: Add factsheet/SID/KIM/TER/AUM to DATASET_TYPE_HINTS
  Per docs/06_plans/active/BATCH_F_discovery.md TASK-H004 exactly.

TASK-H005: Test factsheet and TER URL classification (2 tests)
  Per docs/06_plans/active/BATCH_F_discovery.md TASK-H005 exactly.

TASK-I001: Test browser fallback path (mock Playwright unavailable)
  Per docs/06_plans/active/BATCH_G_browser_vlm.md TASK-I001 exactly.

TASK-I002: Test BrowserUnavailable raised when Playwright not installed
  Per docs/06_plans/active/BATCH_G_browser_vlm.md TASK-I002 exactly.

TASK-J001: Test discovery engine handles HTTP errors gracefully
  Per docs/06_plans/active/BATCH_G_browser_vlm.md TASK-J001 exactly.

**Exit Condition**
```bash
./financial_env/bin/python -m pytest tests/ -q --tb=no
# Expected: ≥139 passed
./financial_env/bin/python -m pytest tests/test_agent.py -k "relevance or discovery or classification or browser" -v
# Expected: all pass
```

**Demonstrable Output**
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "discovery or relevance" -v 2>&1 | tail -20
```

**Verification Prompt**
Verifier reads: discovery.py, test_agent.py (discovery section), DATASET_TYPE_HINTS, pytest output.
Answers: Are H001-H005, I001-I002, J001 all implemented? Do H004 type hints appear in discovery.py?

---

## Checkpoint 1.3 — Portfolio + NAV + Phase 2 Gate (Epics P, N, L)

**Goal**
Reach ≥145 tests. Clear the Phase 2 gate. Complete Milestone 2.

**Prerequisite**
Checkpoint 1.2 exit condition passed.

**Tasks (in order)**

TASK-P002: Add portfolio Excel parser test with real fixture (1 test)
  Per docs/06_plans/backlog/BATCH_L_portfolio.md TASK-P002 exactly.
  Uses tests/fixtures/*.xlsx fixture (create if needed).

TASK-P003: Add portfolio CSV parser test (1 test)
  Per docs/06_plans/backlog/BATCH_L_portfolio.md TASK-P003 exactly.

TASK-N001: Add NAV HTML end-to-end parsing test (1 test)
  Per docs/06_plans/backlog/BATCH_J_nav.md TASK-N001 exactly.

TASK-N002: Add NAV text parser edge-case tests (2 tests)
  Per docs/06_plans/backlog/BATCH_J_nav.md TASK-N002 exactly.

TASK-L002: Verify raw artifact files are written to data/raw/ (1 test)
  Per docs/06_plans/backlog/BATCH_I_retention.md TASK-L002 exactly.

TASK-J002: Test network/API discovery fallback behavior (1 test)
  Per docs/06_plans/active/BATCH_G_browser_vlm.md TASK-J002 exactly.

TASK-CP1-GATE: Update docs + run final test count verification
  Update: docs/04_in_progress/test_coverage_epics/overview.md (mark all CP1 epics done)
  Update: docs/06_plans/SPRINT_CURRENT.md (mark Phase 2 gate criteria complete)
  Run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
  Confirm: ≥145 passed.

**Exit Condition**
```bash
./financial_env/bin/python -m pytest tests/ -q --tb=no
# Expected: ≥145 passed
grep "Done: \[x\]" docs/06_plans/SPRINT_CURRENT.md | wc -l
# Expected: ≥4 (Epic G, H, P, N all complete)
```

**Demonstrable Output**
```bash
./financial_env/bin/python -m pytest tests/ -v 2>&1 | tail -20
# Shows 145+ passing
```

**Verification Prompt**
Verifier reads: all test files, SPRINT_CURRENT.md, test_coverage_epics/overview.md, pytest output.
Answers: Is count ≥145? Are Epics G, H, P, N all marked done? Is the Phase 2 gate clear?

---

## Checkpoint 2 — Phase 2 Document Discovery

**Goal**
Run the discovery pipeline against at least 3 real AMC provider profiles. Produce a review notebook.

**Prerequisite**
Checkpoint 1.3 exit condition passed.
runner.py refactor complete (verified in CP0).
DATABASE_URL documented and verified (verified in CP0).

**Tasks (in order)**

TASK-D001: Read provider_profiles.latest.json — select 3 seed AMCs
  Load profiles, pick 3 with confirmed_disclosure_url set.
  Write selected 3 to docs/06_plans/active/PHASE2_seed_amcs.md.

TASK-D002: Run discovery pipeline against seed AMC 1 (dry-run mode)
  Run: python -m mutual_fund_ingestion run-agent --task-url <AMC1_URL> --database-url $DATABASE_URL --max-pages 5 --dry-run
  Record output in docs/06_plans/active/PHASE2_discovery_log.md.

TASK-D003: Run discovery pipeline against seed AMCs 2 and 3 (dry-run mode)
  Same as D002 for AMC2 and AMC3.
  Append to PHASE2_discovery_log.md.

TASK-D004: Run live discovery against seed AMC 1 (non dry-run, limited)
  --max-pages 10, --max-downloads 3
  Record discovered candidate URLs in DB.

TASK-D005: Inspect discovered candidates in DB
  Run: python -m mutual_fund_ingestion inspect-run --database-url $DATABASE_URL --run-id <RUN_ID>
  Record: how many DatasetCandidate rows, what dataset_types found.

TASK-D006: Write notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb
  Layer 1 only. Loads discovery results from DB (or JSON export).
  Shows: how many links found, dataset_type distribution, top candidate URLs.

TASK-D007: Update docs/01_status/MASTER_STATE.md with Phase 2 results
  Add "Phase 2 Discovery" section: which AMCs discovered, how many candidates, date.

**Exit Condition**
```bash
ls data/raw/mutual_funds/ 2>/dev/null | head -5
# Expected: at least 0 files (discovery may produce 0 downloads in dry-run — candidates in DB is sufficient)
./financial_env/bin/python -m pytest tests/ -q --tb=no
# Expected: ≥145 (no regression)
ls notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb
# Expected: file exists
```

**Demonstrable Output**
```bash
open notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb
```

**Verification Prompt**
Verifier reads: PHASE2_discovery_log.md, 03_phase2_discovery_review.ipynb, MASTER_STATE.md Phase 2 section, pytest output.
Answers: Were 3 AMCs discovered? Did the pipeline run without crashing? Is the notebook renderable?

---

## Checkpoint 3 — Real AMC Documents Downloaded

**Goal**
Download at least 1 real disclosure document (portfolio Excel or NAV text) from at least 1 real AMC, with a metadata sidecar written.

**Prerequisite**
Checkpoint 2 exit condition passed. At least 1 real DatasetCandidate URL identified.

**Tasks (in order)**

TASK-R001: Run full pipeline against best candidate URL (portfolio Excel or NAV text)
  Use a URL from CP2 discovery that has high relevance score.
  Run without --dry-run. max-pages 1, max-downloads 1.
  Record: SHA256, file size, download path.

TASK-R002: Verify metadata sidecar written
  Confirm: data/raw/mutual_funds/<hash>.json sidecar exists alongside downloaded file.
  Confirm: sidecar has amc_name, dataset_type, source_url, downloaded_at fields.

TASK-R003: Parse the downloaded file
  Run parser on the downloaded artifact.
  Record: how many records parsed, any parse errors.

TASK-R004: Verify canonical upsert
  Check the DB for newly upserted NAVHistory or PortfolioSnapshot rows.
  Run a SELECT and record the count.

TASK-R005: Write notebooks/mutual_fund_ingestion/04_phase3_real_data_review.ipynb
  Show: which file was downloaded, parsed record count, DB row count.
  Must render without error.

TASK-R006: Update MASTER_STATE.md with Phase 3 entry
  Add "First Real Document" entry: AMC name, file type, records, DB rows, date.

**Exit Condition**
```bash
ls data/raw/mutual_funds/
# Expected: ≥1 file downloaded + ≥1 .json sidecar
./financial_env/bin/python -m pytest tests/ -q --tb=no
# Expected: ≥145 (no regression)
ls notebooks/mutual_fund_ingestion/04_phase3_real_data_review.ipynb
# Expected: file exists
```

**Demonstrable Output**
```bash
open notebooks/mutual_fund_ingestion/04_phase3_real_data_review.ipynb
# Shows: real downloaded file, parse results, DB record count
```

**Verification Prompt**
Verifier reads: data/raw/mutual_funds/ file list + sidecar, 04_phase3_real_data_review.ipynb, MASTER_STATE.md Phase 3 section, DB record count from inspect-run.
Answers: Was ≥1 real file downloaded? Does the sidecar have required fields? Are DB rows present?

---

## Checkpoint 4 — Canonical Tables Populated (Placeholder)

**Goal:** Real portfolio holdings from ≥2 AMCs in PostgreSQL. NAV history from ≥10 schemes.

**Tasks:** TBD after CP3 review. Scope: validation coverage for real data, ETL hardening.

**Exit Condition:** TBD

---

## Checkpoint 5 — Analytics Layer (Placeholder)

**Goal:** Can query: top stocks held by most funds, month-over-month holding changes, fund overlap.

**Tasks:** TBD after CP4 review. Scope: analytics agent implementation.

**Exit Condition:** TBD
