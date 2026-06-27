# Authoritative Sources

_Which documents to trust, and in what order. Updated: 2026-06-23._

---

## Priority Order for Any Session

When two documents conflict, use this order to resolve:

1. **Live codebase + tests** — current working tree is truth
2. **Current CLI behavior** — `--help` and actual output
3. **Git working tree / git status** — catches uncommitted state
4. **`docs/agent_context/`** — verified 2026-06-23 audit
5. **`AGENTS.md`** — non-negotiable governance rules
6. **`docs/design/`** — design specs (behavioral intent)
7. **`CHATGPT_PROJECT_MEMORY.md`** — continuity context (test counts stale: use 125)
8. **`plans/`** — planning documents (task statuses stale: see audit)
9. **Historical memory documents** — read for context, verify before acting

---

## Reading Order by Session Type

### Large Model Planning Session

Goal: understand current state, design next phase, identify gaps.

1. `docs/agent_context/README.md` — navigation
2. `docs/agent_context/00_project_brief.md` — system purpose
3. `docs/agent_context/01_current_system_state.md` — verified state
4. `docs/agent_context/03_documentation_audit.md` — conflicts
5. `docs/agent_context/05_next_execution_roadmap.md` — forward plan
6. `AGENTS.md` — governance rules
7. `docs/design/task_url_agent_design_pack/` — behavioral specs
8. `docs/design/phase_2/` — if Phase 2 is the topic

### Claude Code / Codex Implementation Session

Goal: execute a specific task or microtask.

1. `AGENTS.md` — read first, always
2. `docs/ai_context/CODEBASE_MAP.md` — module ownership
3. `docs/agent_context/02_verified_codebase_map.md` — corrections
4. `docs/agent_context/01_current_system_state.md` — what is done vs. missing
5. Task spec from `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md`
6. Files listed under "Files to read" in the task spec

### Small Model Single-Microtask Session

Goal: execute exactly one task from the micro plan.

1. `plans/SMALL_MODEL_EXECUTION_GUIDE.md` — execution rules (read all of it)
2. `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` — find next pending task
3. `docs/agent_context/01_current_system_state.md` — for context if needed
4. Files listed under "Files to read" in the task spec only

Do not load the full codebase. Do not read files not listed in the task.

### Debugging Session

Goal: diagnose a failing test or broken behavior.

1. `docs/agent_context/02_verified_codebase_map.md` — find the relevant module
2. `docs/agent_context/01_current_system_state.md` — is this a known gap?
3. `docs/agent_context/07_testing_and_demo_gates.md` — what does "passing" mean?
4. The specific test file
5. The specific module under test
6. `mutual_fund_ingestion/agent/runner.py` — if it's a pipeline behavior

### Handoff Session

Goal: capture current state for the next session.

1. `docs/agent_context/08_session_handoff_template.md` — fill in the template
2. `docs/agent_context/01_current_system_state.md` — verify completed items
3. `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` — update task statuses

---

## Documents That Are Authoritative but Outdated (Verify Before Acting)

| Document | What to verify |
|---|---|
| `docs/ai_context/CODEBASE_MAP.md` | VLM status, portfolio bug status, parser list |
| `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` | All statuses show "pending" but many are done |
| `CHATGPT_PROJECT_MEMORY.md` | Test count is 125, not 121 |
| `README.md` | Test count is 125, not 118 |
| `plans/task_url_ingestion_agent.md` | Old test counts and gap list |

---

## Documents That Are Historical (Read for Context, Do Not Act On)

| Document | Use |
|---|---|
| `docs/session_state.md` | Old handoff — R003/R004 blocker is resolved |
| `PLAN.md` | Old 6-task plan — tasks 1/2 done |
| `docs/design/mutual_fund_project_memory_pack/` | Design memory — verify against live code |
| `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md` | Jun 17 audit — many items since fixed |
| `docs/handoff/handoff_financial_analytics_refactor_20260617_0230.md` | Historical handoff |

---

## Do Not Trust Without Verification

- Any document claiming test count other than 125 (verified 2026-06-23)
- Any document claiming VLM is not wired (it is, as of runner.py lines 179–195)
- Any document claiming portfolio.py column mapping is broken (it is fixed)
- Any document claiming raw file retention is not implemented (it is, lines 409–417)
