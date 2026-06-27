# Financial Analytics Work — Documentation Hub

> **Start here.** This README is the entry point for all agents and humans.

---

## Session-Type Routing

| Session type | Read first | Then read |
|---|---|---|
| Restructure / audit | `01_status/MASTER_STATE.md` | `02_architecture/codebase_map.md` |
| Implementation | `07_agent_rules/SMALL_MODEL_GUIDE.md` | `06_plans/SPRINT_CURRENT.md` → `06_plans/MICROTASK_SPEC.md` |
| Claude Code planning | `07_agent_rules/CLAUDE_CODE_PRIMER.md` | `06_plans/GOAL_ALIGNMENT.md` |
| New notebook | `07_agent_rules/skills/write_notebook.md` | `02_architecture/codebase_map.md` |
| Debugging | `01_status/AGENT_EXECUTION_LOG.md` | `02_architecture/codebase_map.md` |
| Phase 2 start | `05_planned/phase_2_discovery/` | `03_implemented/phase_1b_provider_profiling/` |

---

## Directory Map

```
docs/
├── README.md                    ← You are here
│
├── 00_project/                  ← What/Why/For Whom (stable)
│   ├── brief.md                 ← 1-page system description
│   ├── decisions.md             ← Architecture decisions + rationale
│   └── goals_and_milestones.md  ← Primary goal, milestones, non-goals
│
├── 01_status/                   ← Current state (updated every session)
│   ├── MASTER_STATE.md          ← Single truth: done / partial / not started / test count
│   ├── session_state.md         ← Last session handoff
│   └── AGENT_EXECUTION_LOG.md   ← Failure log — prevents repeated mistakes
│
├── 02_architecture/             ← System design (stable, updated on structure change)
│   ├── codebase_map.md          ← THE authoritative module map
│   ├── system_overview.md       ← Pipeline diagram + component descriptions
│   ├── database_schema.md       ← All 17 tables, relationships, indexes
│   └── layer_model.md           ← 5-layer architecture enforced on all code
│
├── 03_implemented/              ← Frozen: specs for complete phases (read only)
│   ├── phase_1a_source_registry/
│   ├── phase_1b_provider_profiling/
│   └── task_url_agent/
│
├── 04_in_progress/              ← Active work (updated as tasks complete)
│   └── test_coverage_epics/
│       ├── overview.md
│       ├── epic_g_validation.md
│       ├── epic_h_discovery.md
│       ├── epic_p_portfolio.md
│       └── epic_n_nav.md
│
├── 05_planned/                  ← Not started: do not implement until gate criteria met
│   ├── phase_2_discovery/
│   ├── phase_3_classification/
│   └── phase_4_plus/
│
├── 06_plans/                    ← Execution planning (agent-readable)
│   ├── GOAL_ALIGNMENT.md        ← Goals all tasks must serve
│   ├── SPRINT_CURRENT.md        ← What Pi is executing NOW
│   ├── MICROTASK_SPEC.md        ← Current task spec for Pi
│   ├── EXECUTION_RESULT.md      ← Last Pi result (replaced each task)
│   ├── TASKS_FULL_SYSTEM_MICRO_PLAN.md  ← Full task backlog
│   ├── active/                  ← Current sprint batch plans
│   ├── backlog/                 ← Future batches
│   └── completed/               ← Done batches
│
├── 07_agent_rules/              ← Rules enforced on ALL agents
│   ├── CLAUDE_CODE_PRIMER.md    ← Claude Code session orientation
│   ├── SMALL_MODEL_GUIDE.md     ← Pi coding agent operating rules
│   ├── task_generation_rules.md ← Rules for writing task specs for Pi
│   └── skills/
│       ├── design_layered_module.md
│       ├── write_notebook.md
│       └── session_handoff.md
│
└── 09_historical/               ← Archive: read for context only, never act on
    ├── completed_work_log.md
    ├── stale_docs_register.md
    └── legacy/                  ← Old scattered docs
        ├── context_pack/
        ├── source_memory/
        └── design_memory_pack/
```

---

## Authoritative Reading Order

For any new agent starting cold:

1. `AGENTS.md` (project root) — governance rules
2. `docs/README.md` — you are here
3. `docs/01_status/MASTER_STATE.md` — current verified state
4. `docs/02_architecture/codebase_map.md` — module ownership
5. `docs/07_agent_rules/SMALL_MODEL_GUIDE.md` — execution rules (Pi)
6. `docs/06_plans/SPRINT_CURRENT.md` — what to do next
7. `docs/06_plans/MICROTASK_SPEC.md` — exact task spec

Do not read from `09_historical/` or `05_planned/` before reading the above.
