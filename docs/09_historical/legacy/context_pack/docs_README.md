# docs/ — System Documentation Index
# Indian Mutual Fund Ingestion System
# Everything lives here. No documentation exists outside this directory (except AGENTS.md, CLAUDE.md, README.md at root).

---

## Quick Reference — Where to Look

| I want to... | Go to |
|---|---|
| Understand what this system does | `00_project/brief.md` |
| See what is built and what is not | `01_status/MASTER_STATE.md` |
| Find a module's location and API | `02_architecture/codebase_map.md` |
| Read specs for a completed phase | `03_implemented/<phase>/` |
| See what is being worked on now | `04_in_progress/` |
| Read specs for a future phase | `05_planned/<phase>/` |
| See what Pi is executing right now | `06_plans/SPRINT_CURRENT.md` |
| Write a task for Pi | `06_plans/MICROTASK_SPEC.md` + `07_agent_rules/task_generation_rules.md` |
| Understand what Pi produced last | `06_plans/EXECUTION_RESULT.md` |
| Apply a coding skill | `07_agent_rules/skills/` |
| Review historical or archived docs | `09_historical/` |

---

## Session-Type Reading Order

### Human Designer Session
Goal: understand system state and direct next work.
```
1. 01_status/MASTER_STATE.md      — current state, test count, gate criteria
2. 06_plans/SPRINT_CURRENT.md     — what's being built right now
3. 06_plans/GOAL_ALIGNMENT.md     — are we on track toward the milestones?
4. notebooks/00_system_checkpoint.ipynb  — run to see live system health
```

### Claude Code Planning Session
Goal: select next task, write MICROTASK_SPEC for Pi.
```
1. AGENTS.md                               — governance rules
2. 01_status/MASTER_STATE.md               — verified state
3. 06_plans/GOAL_ALIGNMENT.md              — which milestone are we serving?
4. 06_plans/active/<current batch>.md      — find next pending task
5. 07_agent_rules/task_generation_rules.md — apply before writing spec
6. 06_plans/MICROTASK_SPEC.md              — write the task for Pi
```

### Pi Coding Agent Execution Session
Goal: implement exactly one task.
```
1. 07_agent_rules/SMALL_MODEL_GUIDE.md     — rules (read ALL of it)
2. 06_plans/MICROTASK_SPEC.md             — your task
3. [only files listed under "Files to Read" in the task spec]
```

### Debugging Session
Goal: diagnose a failing test or broken behavior.
```
1. 01_status/MASTER_STATE.md              — is this a known gap?
2. 02_architecture/codebase_map.md        — find the module
3. 01_status/AGENT_EXECUTION_LOG.md       — has this failed before?
4. The failing test file
5. The module under test
```

### Phase 2 Planning Session
Goal: design Phase 2 implementation.
```
1. 01_status/MASTER_STATE.md              — confirm gate criteria are met
2. 05_planned/phase_2_discovery/          — read ALL spec files
3. 03_implemented/task_url_agent/         — understand what Phase 2 will build on
4. 02_architecture/codebase_map.md        — import guidance for Phase 2 modules
```

### End-of-Session Handoff
Goal: hand off to next session cleanly.
```
1. 07_agent_rules/skills/session_handoff.md  — apply the template
2. 01_status/MASTER_STATE.md                 — update test count and status
3. 06_plans/SPRINT_CURRENT.md               — update active task
4. 01_status/session_state.md               — write current handoff (replace old)
```

---

## Directory Index

| Directory | Who reads it | Update frequency |
|---|---|---|
| `00_project/` | Everyone | Rarely (architecture decisions) |
| `01_status/` | Everyone, every session | Every session |
| `02_architecture/` | Coding agents, debugging | On structure change |
| `03_implemented/` | Reference only | Never (frozen) |
| `04_in_progress/` | Claude Code, Pi | Weekly |
| `05_planned/` | Claude Code (planning) | Before each new phase |
| `06_plans/` | Claude Code, Pi | Every task |
| `07_agent_rules/` | All agents | On rule change |
| `09_historical/` | Background context | Never (archive) |

---

## What Does NOT Exist Outside This Directory

The following are NOT authoritative and should not be used to make decisions:
- Root-level numbered docs (`00_CLAUDE_MASTER_CONTEXT.md` etc.) → archived to `09_historical/`
- `source_memory/` → archived to `09_historical/`
- `docs/agent_context/` → merged into `01_status/` and `00_project/`
- `docs/ai_context/CODEBASE_MAP.md` → merged into `02_architecture/codebase_map.md`
- `plans/` directory → moved to `06_plans/`

If you find a doc outside this structure that is not `AGENTS.md`, `CLAUDE.md`, or root `README.md`,
it is historical. Read it for context. Do not act on its claims without verifying against `01_status/MASTER_STATE.md`.

---

## Last restructured: [DATE]
## Test suite: [N] tests passing
## Phase 2 gate: [met / not met]
