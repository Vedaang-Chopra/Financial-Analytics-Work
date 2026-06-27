# Stale Docs Register

_Audit date: 2026-06-23. Conflicts resolved against live codebase and 125-test suite._

Do not delete stale documents. Preserve historical context.

---

## Register

### 1. docs/session_state.md

**Stale claim**: "Current blocker: R003/R004 tests keep failing due to file corruption when editing tests/test_agent_db.py"

**Verified reality**: R003 (`test_fixture_seed_page_writes_source_pages`) and R004 (`test_fixture_nav_file_upserted_to_nav_history`) are both in the passing test suite. No blocker exists.

**Action taken**: Noted in `03_documentation_audit.md`.

**Action still needed**: Replace `docs/session_state.md` with a current handoff using `08_session_handoff_template.md`. (TASK-T004)

---

### 2. plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md — All statuses show "pending"

**Stale claim**: Every task shows `Status: pending`, implying no work has been done.

**Verified reality**: The following tasks are confirmed complete based on code inspection, CHATGPT_PROJECT_MEMORY session updates, and passing tests:

| Task | Verified complete |
|---|---|
| TASK-A001 (*.db gitignore) | ✅ `.gitignore` contains `*.db` |
| TASK-A002 (pika removed) | ✅ `pika` absent from `requirements.txt` |
| TASK-A004 (financial_env gitignore) | ✅ `.gitignore` contains `financial_env/` |
| TASK-D001 (retry-failed crash) | ✅ Per CHATGPT_PROJECT_MEMORY Jun 21 |
| TASK-D002 (logging format) | ✅ `cli.py:386-388` has format with asctime |
| TASK-E001–E007 (logging observability) | ✅ Per CHATGPT_PROJECT_MEMORY Jun 22 |
| TASK-F002 (nav_history index test) | ✅ Per CHATGPT_PROJECT_MEMORY Jun 22 |
| TASK-F003 (amcs unique constraint) | ✅ Per CHATGPT_PROJECT_MEMORY Jun 22 |
| TASK-K004 (VLM wired in runner) | ✅ `runner.py:179-195` confirmed |
| TASK-L001 (raw file retention) | ✅ `runner.py:409-417` confirmed |
| TASK-N003 (parse_nav_html) | ✅ `parser/nav.py:102` confirmed |
| TASK-P001 (portfolio column fix) | ✅ Per CHATGPT_PROJECT_MEMORY Jun 21 |
| TASK-P004 (parse_portfolio_csv) | ✅ `parser/portfolio.py:132` confirmed |
| TASK-R001–R004 (fixture tests) | ✅ 125 tests pass including these |
| TASK-S001–S002 (smoke tests) | ✅ `test_smoke.py` 3 tests pass |

**Action taken**: Listed in `03_documentation_audit.md`.

**Action still needed**: Update status lines in `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` for all confirmed-complete tasks. (TASK-T001 / TASK-B001–B005)

---

### 3. plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md (Jun 17, 2026)

**Stale claims**:
- "VLM is wired but analyze_page() never called" — **resolved**: wired in runner.py:179-195
- "portfolio.py column mapping broken" — **resolved**: header row detection fixed
- "Files are never actually moved from temp dir" — **resolved**: implemented in L001
- "85 tests pass" — **resolved**: 125 tests pass as of 2026-06-23

**Action taken**: Noted in `03_documentation_audit.md`. Conflicts resolved.

**Action still needed**: This doc is historically valuable. Keep as-is. Future agents should use `01_current_system_state.md` instead.

---

### 4. plans/task_url_ingestion_agent.md

**Stale claim**: "50 passing tests (29 Phase 1 + 21 agent)"

**Verified reality**: 125 tests pass.

**Action taken**: Noted in `03_documentation_audit.md`.

**Action still needed**: Update test count and gap list. (TASK-B002)

---

### 5. README.md — Test Count

**Stale claim**: "118 tests: 38 Phase 1 + 36 agent + 11 amfi_disclosure + 22 DB integration + 11 parser/routing"

**Verified reality**: 125 tests pass.

**Action taken**: Noted.

**Action still needed**: Update test count. (TASK-B005)

---

### 6. CHATGPT_PROJECT_MEMORY.md — Test Count

**Stale claim** (in "Status Update 2026-06-22"): "121/121 tests pass"

**Verified reality**: 125 tests pass (2026-06-23).

**Action taken**: Noted.

**Action still needed**: Update "Current Status" section with test count = 125. (TASK-B003)

---

### 7. docs/ai_context/CODEBASE_MAP.md — Multiple Stale Notes

**Stale claims**:
- `agent/vlm.py`: "NOTE: analyze_page() is never called in runner.py" — **resolved**: it IS called
- `agent/parser/portfolio.py`: "has column mapping bug" — **resolved**: fixed
- Missing: `parse_nav_html`, `parse_portfolio_csv` in module table
- Missing: raw file retention status in extract.py row

**Action taken**: Corrections documented in `02_verified_codebase_map.md`.

**Action still needed**: Update `CODEBASE_MAP.md` directly. (TASK-B004, TASK-T001)

---

### 8. PLAN.md (Root)

**Stale claims**:
- Task 1 (EvidenceParser → LinkExtractor): not marked complete
- Task 2 (Wire runner.run() to DB): not marked complete
- "runner.run() does NOT insert to PostgreSQL" — **wrong**: runner writes to all 17 tables

**Action taken**: Noted.

**Action still needed**: Mark tasks 1/2 complete; correct the runner claim. (TASK-B001)
