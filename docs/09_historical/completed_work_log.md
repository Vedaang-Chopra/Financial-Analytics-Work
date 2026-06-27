# Documentation Audit

_Audited: 2026-06-23. All claims verified against live codebase, tests (125 passing), and git working tree._

---

## Summary

The project has accumulated 25+ planning and governance documents across multiple sessions. Most are valuable historically. Several contain stale claims. The critical conflicts are listed below with verified resolutions.

---

## Document Classification

| Document | Classification | Current? | Action |
|---|---|---|---|
| `AGENTS.md` | Authoritative — governance | ✅ Yes | Read before every change |
| `docs/agent_context/README.md` | Authoritative — navigation | ✅ Yes (created 2026-06-23) | Primary entry for agents |
| `docs/agent_context/01_current_system_state.md` | Authoritative — current state | ✅ Yes | Read before any planning |
| `docs/ai_context/CODEBASE_MAP.md` | Authoritative but partially stale | ⚠️ Needs updates | See conflicts list below |
| `docs/design/task_url_agent_design_pack/` | Authoritative — behavioral specs | ✅ Yes | Read for system intent |
| `docs/design/phase_1/` | Authoritative — Phase 1 specs | ✅ Yes (frozen) | Phase 1 is complete |
| `docs/design/phase_2/` | Authoritative — Phase 2 specs | ✅ Yes (not yet implemented) | Read before Phase 2 work |
| `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md` | Partially stale — Jun 17 audit | ⚠️ Stale status claims | Valuable for gap analysis history; conflicts noted below |
| `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` | Authoritative — task registry | ⚠️ Statuses all show "pending" | **All task statuses must be audited and updated** |
| `plans/SMALL_MODEL_EXECUTION_GUIDE.md` | Authoritative — execution rules | ✅ Yes | Correct as-is |
| `plans/ACTIVE_EXECUTION_PLAN.md` | Authoritative — current roadmap | ✅ Yes (created 2026-06-23) | Read for next work |
| `plans/MICROTASK_BATCHES.md` | Authoritative — batch grouping | ✅ Yes (created 2026-06-23) | Read for batch organization |
| `CHATGPT_PROJECT_MEMORY.md` | Authoritative continuity | ⚠️ Test count stale | Update test count to 125 |
| `README.md` | Authoritative user guide | ⚠️ Test count stale (says 118) | Update to 125 |
| `docs/README_DOCS_INDEX.md` | Navigation index | ⚠️ Missing agent_context/ entries | Update |
| `docs/session_state.md` | Stale handoff | ❌ Contains old R003/R004 "blocker" | Replace with current handoff |
| `PLAN.md` | Stale plan | ❌ Several items now done | Mark completed tasks; correct runner claim |
| `plans/task_url_ingestion_agent.md` | Stale status doc | ❌ Test count wrong, gap list stale | Update after full task audit |
| `plans/task_url_ingestion_detailed_implementation_plan.md` | Historical build plan | ✅ Useful | Keep as historical |
| `plans/DOCS_AND_ARCHIVE_PLAN.md` | Archive guidance | ✅ Useful | Keep |
| `plans/TESTING_STRATEGY_AND_FIXTURE_PLAN.md` | Testing strategy | ✅ Useful | Keep |
| `plans/TECHNICAL_SPEC_AGENT_TARGET_STATE.md` | Target state spec | ✅ Useful | Keep |
| `docs/design/mutual_fund_project_memory_pack/` | Historical memory | ⚠️ May be stale | Keep; read before Phase 2 |
| `docs/handoff/handoff_financial_analytics_refactor_20260617_0230.md` | Historical handoff | ✅ Historical value | Keep |
| `docs/archive/legacy_experiments/` | Legacy code archive | ✅ Historical | Do not modify |

---

## Critical Conflicts Resolved

### CONFLICT 1: VLM Not Wired

**Old claim** (CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md, Jun 17):
> `analyze_page()` is never called anywhere in the BFS loop. `--use-vlm` flag does nothing at runtime.

**Verified reality** (2026-06-23, runner.py lines 179–195):
```python
if self.config.use_vlm and score > 0 and score < self.config.vlm_confidence_threshold and html:
    # ... vlm_decision = self.vlm.analyze_page(vlm_payload)
```
**Resolution**: VLM IS wired. TASK-K004 is complete. CODEBASE_MAP.md note "NOTE: analyze_page() is never called" is stale.

---

### CONFLICT 2: Portfolio Parser Broken

**Old claim** (CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md, Jun 17):
> `parse_portfolio_excel()` column mapping broken — `header=None` produces integer column indices.

**Verified reality** (CHATGPT_PROJECT_MEMORY.md, Jun 21; code verified):
> TASK-P001 FIXED — header row detection works for real AMFI Excel files.

**Resolution**: Portfolio column mapping is fixed. The note in CODEBASE_MAP.md "has column mapping bug" should be updated to "FIXED".

---

### CONFLICT 3: Test Count Across Documents

| Document | Claimed count | Date |
|---|---|---|
| `plans/task_url_ingestion_agent.md` | 50 tests | Old |
| `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md` | 85 tests | Jun 17, 2026 |
| `README.md` | 118 tests | Earlier |
| `docs/session_state.md` | implied 88 tasks in progress | Earlier |
| `CHATGPT_PROJECT_MEMORY.md` | 121 tests | Jun 22, 2026 |
| **Live test suite** | **125 tests** | **Jun 23, 2026 ✅** |

**Resolution**: 125 is the verified count. All documents claiming other values are stale.

---

### CONFLICT 4: Task Statuses in TASKS_FULL_SYSTEM_MICRO_PLAN.md

**Old claim**: All 73+ tasks show `Status: pending`

**Verified reality**: Many tasks are done based on CHATGPT_PROJECT_MEMORY session updates and code inspection:
- TASK-A001 (*.db gitignore): DONE
- TASK-A002 (pika removed): DONE
- TASK-A004 (financial_env/ gitignore): DONE
- TASK-D002 (logging format): DONE
- TASK-E001–E007 (logging observability): DONE
- TASK-F002, F003 (schema tests): DONE
- TASK-K004 (VLM wired): DONE
- TASK-L001 (raw file retention): DONE
- TASK-N003 (parse_nav_html): DONE
- TASK-P001 (portfolio column fix): DONE
- TASK-P004 (parse_portfolio_csv): DONE
- TASK-R001–R004 (fixture tests): DONE
- TASK-S001–S002 (smoke tests): DONE

**Resolution**: Task statuses must be updated. See `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` — update each completed task to `Status: complete`.

---

### CONFLICT 5: session_state.md Is a Stale Handoff

**Old claim** (docs/session_state.md): "Current blocker: R003/R004 tests keep failing"

**Verified reality** (2026-06-23): R003 and R004 are passing tests. `test_fixture_seed_page_writes_source_pages` and `test_fixture_nav_file_upserted_to_nav_history` are both in the test suite and passing.

**Resolution**: `docs/session_state.md` should be replaced with a current handoff or clearly marked as historical.

---

### CONFLICT 6: Raw File Retention Incomplete

**Old claim** (CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md, Jun 17):
> Files are never actually moved from temp dir to a permanent `raw_dir`.

**Verified reality** (runner.py lines 409–417):
```python
# L001: Implement raw file retention - move to raw_dir if configured
if artifact_result.get("retained") and self.config.raw_dir:
    ...
    shutil.copy2(src, dest)
```
Also verified by `test_smoke_keep_raw_files_creates_file_in_raw_dir` passing.

**Resolution**: Raw file retention IS implemented. TASK-L001 is complete.

---

### CONFLICT 7: PLAN.md Claims Runner Does Not Write to DB

**Old claim** (PLAN.md, section 1.5):
> "runner.run() does NOT insert to PostgreSQL"

**Verified reality**: Runner writes to all 17 tables. This was already corrected in the Jun 17 audit. PLAN.md has not been updated.

**Resolution**: PLAN.md tasks 1 and 2 should be marked complete.

---

## Stale Documents Register

See `docs/historical/stale_docs_register.md` for the full register.

---

## Documents NOT to Modify

- `docs/archive/legacy_experiments/` — historical code; read-only
- `docs/design/` — design specs; update only if implementation diverges from spec
- `docs/handoff/` — historical handoffs; do not modify

---

## Action Items

| Priority | Action | File |
|---|---|---|
| HIGH | Update task statuses in TASKS_FULL_SYSTEM_MICRO_PLAN.md | `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` |
| HIGH | Replace docs/session_state.md with current handoff | `docs/session_state.md` |
| HIGH | Update CODEBASE_MAP.md corrections (VLM, portfolio, parsers) | `docs/ai_context/CODEBASE_MAP.md` |
| MEDIUM | Update README.md test count to 125 | `README.md` |
| MEDIUM | Update CHATGPT_PROJECT_MEMORY.md test count to 125 | `CHATGPT_PROJECT_MEMORY.md` |
| MEDIUM | Update plans/task_url_ingestion_agent.md gap list | `plans/task_url_ingestion_agent.md` |
| LOW | Mark PLAN.md tasks complete | `PLAN.md` |
