# Documentation Refactor Plan
# Goal: Single source of truth. No ambiguity about what is done vs. pending vs. archived.
# Every doc lives in exactly one place. Agents know exactly what to read and in what order.

---

## The Problem

The current docs directory has:
- Duplicate files at multiple paths (`00_CLAUDE_MASTER_CONTEXT.md` vs `00_claude_master_context.md`, etc.)
- Stale status claims (test counts, bug status) scattered across 25+ files
- No clear separation between "design of what was built" vs "design of what is planned"
- Agents reading the wrong doc and acting on outdated information

---

## Target Structure

```
docs/
├── agent_context/               ← KEEP AS-IS (authoritative, created 2026-06-23)
│   ├── README.md                  Agent navigation guide
│   ├── 00_project_brief.md        What the system is
│   ├── 01_current_system_state.md Verified state — 125 tests, done/partial/missing
│   ├── 02_verified_codebase_map.md Module ownership (corrected)
│   ├── 03_documentation_audit.md  Which docs are stale and why
│   ├── 04_authoritative_sources.md Reading order by session type
│   ├── 05_next_execution_roadmap.md Forward roadmap
│   ├── 06_microtask_batch_plan.md Batched tasks with gates
│   ├── 07_testing_and_demo_gates.md Definition of done
│   └── 08_session_handoff_template.md Reusable handoff template
│
├── implemented/                 ← NEW: design specs for completed phases (frozen)
│   ├── README.md                  "These phases are complete. Do not modify."
│   ├── phase_1a_source_registry/  (move from docs/design/phase_1/ — 1A content)
│   │   ├── spec.md
│   │   └── audit_report.md
│   ├── phase_1b_provider_profiling/ (move from docs/design/phase_1/ — 1B content)
│   │   ├── spec.md
│   │   └── provider_profile_schema.md
│   └── task_url_agent/           (move from docs/design/task_url_agent_design_pack/)
│       ├── README.md
│       ├── implementation_report.md ← Key: what was actually built
│       └── all_specs/             (all 14 spec files)
│
├── in_progress/                 ← NEW: currently being worked on
│   ├── README.md                  "Active work. Update as tasks complete."
│   └── test_coverage_completion/
│       ├── epic_g_validation.md
│       ├── epic_h_discovery.md
│       ├── epic_p_portfolio.md
│       └── epic_n_nav.md
│
├── planned/                     ← NEW: not yet started, specs exist or needed
│   ├── README.md                  "Do not implement until gate criteria are met."
│   ├── phase_2_document_discovery/ (move from docs/design/phase_2/)
│   │   ├── README_PHASE_2_CODEX_PACK.md
│   │   ├── spec.md
│   │   ├── artifact_contract.md
│   │   ├── sample_values.md
│   │   └── testing_and_acceptance.md
│   ├── phase_3_classification/    (spec TBD)
│   ├── phase_4_additional_parsers/ (spec TBD)
│   └── phase_5_plus_analytics/    (spec TBD)
│
├── historical/                  ← KEEP: read-only archive (created 2026-06-23)
│   ├── README.md
│   ├── completed_work_log.md
│   └── stale_docs_register.md
│
├── ai_context/                  ← KEEP: CODEBASE_MAP.md lives here
│   └── CODEBASE_MAP.md          Update with stale-item corrections from audit
│
└── README_DOCS_INDEX.md         ← UPDATE: reflect new structure above

```

---

## Root-Level Files

```
/
├── AGENTS.md                    ← Authoritative governance. Read before any code change.
├── CLAUDE.md                    ← Claude Code operating rules.
├── CHATGPT_PROJECT_MEMORY.md    ← Cross-model memory. Update test count to 125.
├── README.md                    ← User guide. Update test count to 125.
└── configs/
    └── amc_sources.yaml         ← 53 AMCs + AMFI + SEBI. Do not modify structure.

plans/
├── ACTIVE_EXECUTION_PLAN.md     ← Current sprint. Keep updated.
├── TASKS_FULL_SYSTEM_MICRO_PLAN.md ← Master task list. UPDATE statuses.
├── SMALL_MODEL_EXECUTION_GUIDE.md  ← Rules for Pi coding agent.
└── MICROTASK_BATCHES.md         ← Batch groupings.

```

---

## Files to Delete or Archive (Duplicates / Superseded)

The following files are duplicates of the numbered variants. Archive, do not delete permanently.

| File | Action | Reason |
|---|---|---|
| `00_CLAUDE_MASTER_CONTEXT.md` (root) | Move to `docs/historical/` | Superseded by `docs/agent_context/00_project_brief.md` |
| `00_claude_master_context.md` (root) | Move to `docs/historical/` | Duplicate |
| `01_PROJECT_DECISIONS_AND_NON_GOALS.md` (root) | Move to `docs/historical/` | Superseded |
| `01_project_decisions_and_non_goals.md` (root) | Move to `docs/historical/` | Duplicate |
| `02_SYSTEM_ARCHITECTURE.md` (root) | Move to `docs/historical/` | Superseded |
| `02_system_architecture.md` (root) | Move to `docs/historical/` | Duplicate |
| `03_PHASE_ROADMAP_AND_READINESS.md` (root) | Move to `docs/historical/` | Superseded |
| `03_phase_roadmap_and_readiness.md` (root) | Move to `docs/historical/` | Duplicate |
| `docs/session_state.md` | Replace with current handoff | Stale — R003/R004 blocker resolved |
| `PLAN.md` | Update + move to `plans/historical/` | Tasks 1/2 done; mostly stale |
| `source_memory/` (entire dir) | Move to `docs/historical/source_memory/` | Superseded by `docs/agent_context/` |
| `docs/design/mutual_fund_project_memory_pack/` | Move to `docs/historical/` | Superseded |
| Context pack files in project root | Move to `docs/historical/context_pack/` | Superseded by `docs/agent_context/` |

---

## Files to Update In Place (Not Move)

| File | What to Update |
|---|---|
| `docs/ai_context/CODEBASE_MAP.md` | VLM wired ✅, portfolio bug fixed ✅, nav_html added ✅, portfolio_csv added ✅ |
| `README.md` | Test count 118 → 125 |
| `CHATGPT_PROJECT_MEMORY.md` | Test count 121 → 125, add 2026-06-23 status block |
| `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` | Mark ~25 tasks as complete (see audit doc) |
| `plans/ACTIVE_EXECUTION_PLAN.md` | Ensure Phase 2 gate criteria are listed |

---

## Naming Convention for All Future Docs

**Design specs (planned phase):** `docs/planned/<phase_name>/<topic>.md`
**Implementation reference (complete phase):** `docs/implemented/<phase_name>/<topic>.md`
**Active sprint docs:** `plans/<TASK_ID>_<description>.md`
**Agent context (always current):** `docs/agent_context/<NN>_<topic>.md`
**Session handoff:** `docs/session_state.md` (single file, replaced each session)

---

## Immediate Actions (In Priority Order)

```
Priority 1 — Do now:
  1. Update TASKS_FULL_SYSTEM_MICRO_PLAN.md — mark 25 tasks complete
  2. Update CODEBASE_MAP.md — fix 4 stale claims
  3. Replace docs/session_state.md — with current handoff

Priority 2 — Do this week:
  4. Update README.md + CHATGPT_PROJECT_MEMORY.md — test count to 125
  5. Move root-level duplicate docs to docs/historical/
  6. Create docs/implemented/ and move phase_1/ + task_url_agent/ content

Priority 3 — Before Phase 2:
  7. Create docs/planned/phase_2_document_discovery/ — populate from existing phase_2/ specs
  8. Create docs/in_progress/test_coverage_completion/ — one file per epic
  9. Update docs/README_DOCS_INDEX.md — reflect new structure
```
