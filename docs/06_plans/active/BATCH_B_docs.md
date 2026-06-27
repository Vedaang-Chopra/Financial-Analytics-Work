# Batch B — Documentation Truth Cleanup
# Milestone served: 1 (system inspectable)
# Status: active
# Gate: grep for stale claims returns no matches (see test command below)

## Purpose

Eliminate stale claims in key docs that confuse future agents.

## Completion Gate

```bash
grep -n "50 passing\|21 agent\|85 pass\|118 test\|does NOT insert\|never called\|column mapping broken\|files not moved" \
  PLAN.md plans/task_url_ingestion_agent.md CHATGPT_PROJECT_MEMORY.md \
  docs/ai_context/CODEBASE_MAP.md README.md
# Should return no matches
```

## Tasks

### TASK-B001: Update PLAN.md to mark completed tasks
**Goal:** Mark tasks 1 and 2 complete in PLAN.md so it reflects verified reality.
**Files to read:** `docs/01_status/MASTER_STATE.md`, `PLAN.md`
**Files to modify:** `PLAN.md`
**Exact work:**
1. Open PLAN.md
2. Find all tasks confirmed done in MASTER_STATE.md
3. Mark them `[x]` (or equivalent)
4. Update test count to 122 (3 skipped)
**Acceptance criteria:** PLAN.md test count accurate; done tasks marked done
**Test command:** `grep -n "passing\|complete" PLAN.md | head -10`
**Do not do:** Rewrite the entire file; add new tasks; modify planned tasks
**Status:** pending

---

### TASK-B002: Update plans/task_url_ingestion_agent.md
**Goal:** Correct stale test count and gap list in task_url_ingestion_agent.md.
**Files to read:** `docs/01_status/MASTER_STATE.md`, `plans/task_url_ingestion_agent.md`
**Files to modify:** `plans/task_url_ingestion_agent.md`
**Exact work:**
1. Update test count references to 122 (3 skipped)
2. Remove any claims about unimplemented features that are now implemented (VLM wired, portfolio fix, nav_html)
3. Update gap list to reflect current MASTER_STATE.md missing section
**Acceptance criteria:** No stale counts; no false "not implemented" claims
**Test command:** `grep -n "21 agent\|85 pass\|50 passing\|does NOT insert\|never called" plans/task_url_ingestion_agent.md` (should be empty)
**Do not do:** Rewrite entire file
**Status:** pending

---

### TASK-B003: Update CHATGPT_PROJECT_MEMORY.md
**Goal:** Update test count to 122 (3 skipped) in CHATGPT_PROJECT_MEMORY.md.
**Files to read:** `docs/01_status/MASTER_STATE.md`, `CHATGPT_PROJECT_MEMORY.md`
**Files to modify:** `CHATGPT_PROJECT_MEMORY.md`
**Exact work:**
1. Find all test count references
2. Update to 122 passed, 3 skipped
3. Update status of VLM (wired), portfolio parser (fixed), nav_html (implemented)
**Acceptance criteria:** Test count accurate; no false claims
**Test command:** `grep -n "test\|passing" CHATGPT_PROJECT_MEMORY.md | head -15`
**Do not do:** Add new content beyond corrections
**Status:** pending

---

### TASK-B004: Update docs/ai_context/CODEBASE_MAP.md stale claims
**Goal:** Fix stale claims about VLM, portfolio, and parsers in the old CODEBASE_MAP.md.
**Files to read:** `docs/02_architecture/codebase_map.md`, `docs/agent_context/02_verified_codebase_map.md`
**Files to modify:** `docs/ai_context/CODEBASE_MAP.md`, `docs/02_architecture/codebase_map.md`
**Exact work:**
1. Update agent/runner.py entry: VLM wired ✅, raw retention ✅
2. Update agent/parser/nav.py: parse_nav_html added ✅
3. Update agent/parser/portfolio.py: header detection fixed ✅, CSV parser added ✅
4. Update validate.py: note scheme_master/AMC validators status (verify TASK-G001/G002)
5. Apply same corrections to docs/02_architecture/codebase_map.md
**Acceptance criteria:** No stale "column mapping broken", "files not moved", "does NOT insert" claims
**Test command:** `grep -rn "column mapping broken\|files not moved\|does NOT insert\|never called" docs/ai_context/CODEBASE_MAP.md docs/02_architecture/codebase_map.md` (should be empty)
**Do not do:** Restructure the entire file; remove valid entries
**Status:** pending

---

### TASK-B005: Update README.md test count
**Goal:** Update root README.md test count to 122 (3 skipped).
**Files to read:** `docs/01_status/MASTER_STATE.md`, `README.md`
**Files to modify:** `README.md`
**Exact work:**
1. Find test count reference in README.md
2. Update to 122 passed, 3 skipped
3. Verify CLI commands listed are accurate
**Acceptance criteria:** README.md test count accurate
**Test command:** `grep -n "test\|passing" README.md | head -10`
**Do not do:** Rewrite the README
**Status:** pending
