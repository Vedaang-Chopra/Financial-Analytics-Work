# Batch N — Final Docs and Handoff
# Milestone served: 1+2 (inspectable + fully tested)
# Status: backlog
# Gate: All docs accurate; test suite verified at ≥145

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/ -q   # All pass
./financial_env/bin/python -m mutual_fund_ingestion --help   # Accurate
```

## Tasks

### TASK-T001: Update docs/02_architecture/codebase_map.md to reflect completed epics
**Goal:** After all G–Q epics complete, update codebase_map.md to show all parser/validator status as ✅.
**Files to modify:** `docs/02_architecture/codebase_map.md`
**Status:** pending (execute after G–Q batches complete)

---

### TASK-T002: Update README.md with verified commands
**Goal:** Ensure all CLI examples in README.md work as-written.
**Files to modify:** `README.md`
**Exact work:** Run each CLI command in README; fix any that error
**Status:** pending

---

### TASK-T003: Run full test suite and verify count ≥ 145
**Goal:** Confirm test count has reached the Phase 2 gate target.
**Test command:** `./financial_env/bin/python -m pytest tests/ -q`
**Acceptance criteria:** ≥145 tests passing; 0 failures
**Status:** pending

---

### TASK-T004: Create final handoff note
**Goal:** Update `docs/01_status/session_state.md` with final verified state before Phase 2 begins.
**Files to modify:** `docs/01_status/session_state.md`
**Exact work:** Follow `docs/07_agent_rules/skills/session_handoff.md` template
**Status:** pending
