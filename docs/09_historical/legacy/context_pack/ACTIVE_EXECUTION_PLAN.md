# Active Execution Plan

_Created: 2026-06-23. This is the file a fresh Claude/Codex session should read to know what to do next._

**Do not add the entire 140-task backlog here. See `TASKS_FULL_SYSTEM_MICRO_PLAN.md` for the full list.**

---

## Current Phase: Test Coverage Completion (Pre-Phase-2 Gate)

**Goal**: Complete test coverage for all existing agent capabilities before starting Phase 2.

**Why this matters**: Phase 2 (document discovery from provider profiles) will depend on the parser, validation, and upsert paths. Silent bugs must be surfaced now.

**When this phase is done**: Total test count ≥ 145; all parser paths have fixture-based tests; all validators tested with valid and invalid input.

---

## Immediate Next Workstream: Documentation Cleanup (Batch B)

Before adding new tests, correct the stale documentation that has been confusing agents.

### TASK-B001 — Update PLAN.md
- Mark Tasks 1 and 2 as complete
- Remove "runner does not write to DB" claim
- Files: `PLAN.md`

### TASK-B002 — Update task_url_ingestion_agent.md
- Update test count to 125
- Update gap list to reflect current reality
- Files: `plans/task_url_ingestion_agent.md`

### TASK-B003 — Update CHATGPT_PROJECT_MEMORY.md
- Change test count from 121 to 125
- Update "Current Status" section
- Files: `CHATGPT_PROJECT_MEMORY.md`

### TASK-B004 — Update CODEBASE_MAP.md
- Remove stale note about VLM never called
- Remove stale note about portfolio.py bug
- Add parse_nav_html, parse_portfolio_csv to table
- Files: `docs/ai_context/CODEBASE_MAP.md`

### TASK-B005 — Update README.md
- Update test count from 118 to 125
- Files: `README.md`

---

## Next Workstream After B: Validation Coverage (Batch E)

### TASK-G001 — Add validate_scheme_master_record
- Files: `mutual_fund_ingestion/agent/validate.py`

### TASK-G002 — Add validate_amc_record
- Files: `mutual_fund_ingestion/agent/validate.py`

### TASK-G003 — Wire scheme_master and AMC validators into validate_and_filter_records
- Files: `mutual_fund_ingestion/agent/validate.py`, `mutual_fund_ingestion/agent/runner.py`

### TASK-G004 — Add tests for scheme_master and AMC validation
- Files: `tests/test_agent.py`

### TASK-G005 — Verify staging_rows.raw_row_json preserves original record
- Files: `tests/test_agent_db.py`

### TASK-G006 — Add test: quarantine reason codes are non-empty
- Files: `tests/test_agent.py`

---

## Remaining Batches (See MICROTASK_BATCHES.md)

After Batches B and E:
- **Batch F**: Discovery and relevance tests (H001–H005)
- **Batch G**: Browser and network tests (I001–I002, J001–J002)
- **Batch H**: VLM tests (K001–K003, K005)
- **Batch I**: Raw retention tests (L002–L003)
- **Batch J**: NAV ingestion tests (N001, N002, N004)
- **Batch K**: AMC/Scheme master tests (O001–O003)
- **Batch L**: Portfolio parser tests (P002–P003)
- **Batch M**: Metadata parser stubs (Q001–Q003)
- **Batch N**: Final docs verification (T001–T004)

---

## Phase 2 — Not Yet Started

**Do not start Phase 2 until test coverage is complete.**

When ready:
1. Read `docs/design/phase_2/README_PHASE_2_CODEX_PACK.md`
2. Read all files in `docs/design/phase_2/docs/design/mutual_fund_ingestion/phases/`
3. Write microtasks for Phase 2 before implementing anything

---

## Execution Rules

- One task per session (small model) or one batch per session (large model with supervision)
- Run `./financial_env/bin/python -m pytest tests/ -q` before and after every change
- Mark task status in `TASKS_FULL_SYSTEM_MICRO_PLAN.md` immediately when complete
- Update `docs/session_state.md` at end of every session using `08_session_handoff_template.md`

---

## Commands to Verify Current State

```bash
# Verify test suite
./financial_env/bin/python -m pytest tests/ -q
# Expected: 125 passed

# Verify CLI
./financial_env/bin/python -m mutual_fund_ingestion --help

# Verify gitignore
git status --short | grep "\.db" || echo "no .db files tracked"
```
