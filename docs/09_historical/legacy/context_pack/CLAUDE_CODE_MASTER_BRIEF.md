# CLAUDE_CODE_MASTER_BRIEF.md
# The single file Claude Code reads at the start of every major restructure session.
# Place in repository root. This supersedes SESSION_ZERO_INSTRUCTIONS.md.
#
# SESSION TYPE: Restructure + Audit (no new features)
# GOAL: Make the system inspectable, organized, and correctly structured
#       so that both the human designer and Pi can work effectively.

---

## PART 0 — READ FIRST (Mandatory Orientation)

Read these files before doing anything else. In this order.

```
1.  AGENTS.md
2.  CLAUDE.md
3.  docs/agent_context/01_current_system_state.md
4.  docs/agent_context/02_verified_codebase_map.md
5.  docs/agent_context/05_next_execution_roadmap.md
6.  docs/agent_context/06_microtask_batch_plan.md
7.  plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md (scan — understand scope)
```

Then audit what physically exists:
```bash
find . -name "*.md" | grep -v node_modules | grep -v .git | sort
find notebooks/ -name "*.ipynb" | sort
find mutual_fund_ingestion/ -name "*.py" | sort
./financial_env/bin/python -m pytest tests/ -q   # confirm test count
```

Print the audit summary before doing any work.

---

## PART 1 — Single Documentation Umbrella

**Problem:** Docs are scattered across `docs/`, `plans/`, `source_memory/`, root-level numbered files.
**Solution:** Everything lives under `docs/`. Plans live inside `docs/`. Root stays minimal.

### Target Structure

```
docs/
│
├── README.md                        ← Entry point. Humans AND agents read this first.
│                                       Table of contents. Session-type routing.
│
├── 00_project/                      ← What/Why/For Whom (stable, changes rarely)
│   ├── brief.md                     ← 1-page system description (what it is, why it exists)
│   ├── decisions.md                 ← Key architecture decisions + rationale
│   └── goals_and_milestones.md      ← Primary goal, 5 milestones, non-goals
│
├── 01_status/                       ← Current state (updated every session)
│   ├── MASTER_STATE.md              ← Single truth: done / partial / not started / test count
│   ├── session_state.md             ← Last session handoff (replaced each session)
│   └── AGENT_EXECUTION_LOG.md       ← Failure log — prevents repeated mistakes
│
├── 02_architecture/                 ← System design (stable, updated on structure change)
│   ├── system_overview.md           ← Pipeline diagram + 13-component descriptions
│   ├── codebase_map.md              ← THE authoritative module map (single source)
│   ├── database_schema.md           ← All 17 tables, relationships, indexes
│   └── layer_model.md               ← 5-layer architecture enforced on all code
│
├── 03_implemented/                  ← Frozen: specs for complete phases
│   ├── README.md                    ← "These are done. Read only. Do not re-implement."
│   ├── phase_1a_source_registry/    ← Phase 1A spec + audit report
│   ├── phase_1b_provider_profiling/ ← Phase 1B spec + provider profile schema
│   └── task_url_agent/              ← Task-URL agent: all 14 spec files + impl report
│
├── 04_in_progress/                  ← Active work (updated as tasks complete)
│   ├── README.md                    ← "These are being worked on now."
│   └── test_coverage_epics/
│       ├── overview.md              ← Summary of all pending epics + test count target
│       ├── epic_g_validation.md
│       ├── epic_h_discovery.md
│       ├── epic_p_portfolio.md
│       └── epic_n_nav.md
│
├── 05_planned/                      ← Not started: specs for future phases
│   ├── README.md                    ← "Do not implement until gate criteria met."
│   ├── phase_2_discovery/           ← Move from docs/design/phase_2/
│   ├── phase_3_classification/      ← Stub README
│   └── phase_4_plus/                ← Stub README
│
├── 06_plans/                        ← Execution planning (agent-readable)
│   ├── README.md                    ← How the planning system works
│   ├── GOAL_ALIGNMENT.md            ← Goals all tasks must serve (see Part 5)
│   ├── SPRINT_CURRENT.md            ← What Pi is executing RIGHT NOW + next 5 tasks
│   ├── MICROTASK_SPEC.md            ← Current task spec for Pi (replaced each task)
│   ├── EXECUTION_RESULT.md          ← Last Pi execution result (replaced each task)
│   ├── active/                      ← Current sprint batch plans (one file per batch)
│   │   ├── BATCH_B_docs.md
│   │   ├── BATCH_E_validation.md
│   │   ├── BATCH_F_discovery.md
│   │   └── BATCH_G_browser_vlm.md
│   ├── backlog/                     ← Future batches (one file per batch)
│   │   ├── BATCH_I_retention.md
│   │   ├── BATCH_J_nav.md
│   │   ├── BATCH_K_scheme_amc.md
│   │   ├── BATCH_L_portfolio.md
│   │   ├── BATCH_M_metadata.md
│   │   └── PHASE_2_tasks_TBD.md    ← Placeholder: tasks to be written from Phase 2 spec
│   └── completed/                   ← Done batches (archive)
│       └── BATCH_A_hygiene.md
│
├── 07_agent_rules/                  ← Rules and skills enforced on ALL agents
│   ├── README.md                    ← Which rule file to read by agent type
│   ├── CLAUDE_CODE_PRIMER.md        ← Claude Code session orientation
│   ├── SMALL_MODEL_GUIDE.md         ← Pi coding agent operating rules
│   ├── skills/                      ← SKILL.md files (copied from coding agent skills)
│   │   ├── design_layered_module.md ← 5-layer architecture (MANDATORY for all code)
│   │   ├── write_notebook.md        ← Notebook structure (MANDATORY for all notebooks)
│   │   └── session_handoff.md       ← Handoff format (MANDATORY end of every session)
│   └── task_generation_rules.md    ← Rules Claude Code must follow when writing tasks for Pi
│
└── 09_historical/                   ← Archive: read for context, never act on
    ├── README.md
    ├── completed_work_log.md
    ├── stale_docs_register.md
    └── legacy/                      ← All old scattered docs go here
        ├── context_pack/            ← Root-level numbered docs
        ├── source_memory/           ← Old source_memory/ directory
        └── design_memory_pack/      ← Old design memory docs
```

### Root Level After Restructure (Minimal)

```
AGENTS.md          ← Governance. Points to docs/07_agent_rules/.
CLAUDE.md          ← Claude Code rules. Points to docs/07_agent_rules/CLAUDE_CODE_PRIMER.md.
README.md          ← User-facing overview. Points to docs/README.md for full docs.
configs/
  amc_sources.yaml
notebooks/
  mutual_fund_ingestion/   ← All notebooks here (see Part 3)
tests/
mutual_fund_ingestion/
utils/
```

### What to Move / Archive

| Current location | Action | Destination |
|---|---|---|
| Root-level `00_CLAUDE_MASTER_CONTEXT.md` etc. | Archive | `docs/09_historical/legacy/context_pack/` |
| `source_memory/` | Archive entire dir | `docs/09_historical/legacy/source_memory/` |
| `docs/design/mutual_fund_project_memory_pack/` | Archive | `docs/09_historical/legacy/design_memory_pack/` |
| `docs/design/phase_1/` | Move + rename | `docs/03_implemented/phase_1a_source_registry/` + `docs/03_implemented/phase_1b_provider_profiling/` |
| `docs/design/task_url_agent_design_pack/` | Move | `docs/03_implemented/task_url_agent/` |
| `docs/design/phase_2/` | Move | `docs/05_planned/phase_2_discovery/` |
| `docs/agent_context/` | Merge into `docs/01_status/` and `docs/00_project/` | See file map below |
| `docs/ai_context/CODEBASE_MAP.md` | Move + become `docs/02_architecture/codebase_map.md` | Single authoritative map |
| `plans/` entire directory | Move inside `docs/06_plans/` | All plan files |
| `plans/SMALL_MODEL_EXECUTION_GUIDE.md` | Move | `docs/07_agent_rules/SMALL_MODEL_GUIDE.md` |

### docs/agent_context/ Merge Map

| Old file | New location |
|---|---|
| `00_project_brief.md` | `docs/00_project/brief.md` |
| `01_current_system_state.md` | `docs/01_status/MASTER_STATE.md` |
| `02_verified_codebase_map.md` | Merge corrections INTO `docs/02_architecture/codebase_map.md` |
| `03_documentation_audit.md` | `docs/09_historical/completed_work_log.md` (audit done, move to history) |
| `04_authoritative_sources.md` | `docs/README.md` (embed reading order there) |
| `05_next_execution_roadmap.md` | `docs/06_plans/GOAL_ALIGNMENT.md` + `docs/06_plans/SPRINT_CURRENT.md` |
| `06_microtask_batch_plan.md` | Split into `docs/06_plans/active/BATCH_*.md` files |
| `07_testing_and_demo_gates.md` | `docs/07_agent_rules/task_generation_rules.md` |
| `08_session_handoff_template.md` | `docs/07_agent_rules/skills/session_handoff.md` |

---

## PART 2 — Codebase Layer Audit

Before generating any task for Pi, audit the codebase against the 5-layer model from `docs/07_agent_rules/skills/design_layered_module.md`.

**Check these specific things:**

### 2A. Runner.py Size Check

`mutual_fund_ingestion/agent/runner.py` is the most likely layer violation.
Check: how many lines? Does it mix orchestration + core implementation?

If `runner.py` is > 300 lines AND mixes pipeline coordination with parsing/validation logic:
→ Flag as a refactor candidate. Do NOT refactor in this session. Create `REFACTOR_runner.md` in `docs/04_in_progress/` describing the violation and proposed split.

If `runner.py` is reasonably structured (calls other modules, does not inline logic):
→ Document as compliant.

### 2B. Agent Module Structure Check

For each file in `mutual_fund_ingestion/agent/`, classify it:

| File | Expected layer | Actual? | Violation? |
|---|---|---|---|
| `runner.py` | Layer 2+3 (runner + thin orchestration) | ? | ? |
| `discovery.py` | Layer 4 (core discovery logic) | ? | ? |
| `browser.py` | Layer 4 (core Playwright logic) | ? | ? |
| `extract.py` | Layer 4 (core download logic) | ? | ? |
| `parser/__init__.py` | Layer 2 (router = public API) | ? | ? |
| `parser/nav.py` | Layer 4 (parser implementation) | ? | ? |
| `parser/portfolio.py` | Layer 4 (parser implementation) | ? | ? |
| `validate.py` | Layer 4 (core validation) | ? | ? |
| `vlm.py` | Layer 4 (core VLM client) | ? | ? |
| `db.py` | Layer 5 (schemas + DB models) | ? | ? |
| `models.py` | Layer 5 (runtime dataclasses) | ? | ? |
| `config.py` | Layer 5 (config schema) | ? | ? |

**Fill in the "Actual" and "Violation" columns. Write findings to `docs/01_status/MASTER_STATE.md`.**

### 2C. Profiling Module Check (Frozen)

Confirm profiling/ is properly layered (it should be — it was built first):

| File | Layer | Notes |
|---|---|---|
| `profiling/models.py` | Layer 5 | Schemas |
| `profiling/registry.py` | Layer 5 | Config loading |
| `profiling/extract.py` | Layer 4 | HTML parsing |
| `profiling/http.py` | Layer 5 | HTTP session |
| `profiling/browser.py` | Layer 4 | Playwright |
| `profiling/profiler.py` | Layer 4 | Core profiling |
| `profiling/artifacts.py` | Layer 3 | Artifact persistence |
| `profiling/reports.py` | Layer 3 | Report generation |
| `profiling/source_registry.py` | Layer 3 | Candidate merging |
| `profiling/source_discovery.py` | Layer 4 | AMFI/SEBI discovery |

Document: compliant or violations found.

### 2D. Utils Module Check

`utils/http.py`, `utils/url_utils.py`, `utils/text_utils.py` — these are Layer 5.
Check: do any high-level modules (runner, discovery) import from deep inside profiling/ instead of from utils/?
If yes: note as a cleanup task (low priority, batch-able).

### 2E. Produce Codebase Assessment Report

Write `docs/01_status/MASTER_STATE.md` section: **"Code Structure Assessment"** with:
- Layer compliance: pass / violations (list them)
- Refactor candidates (if any): name, reason, estimated scope, priority
- Conclusion: is the codebase structure acceptable to continue building on, or does it need refactoring before Phase 2?

---

## PART 3 — Notebook Creation (Skills-Compliant)

The user cannot inspect the system. This is the highest priority fix.

### 3A. Before Creating Any Notebook

Apply `docs/07_agent_rules/skills/write_notebook.md`.
Write a Notebook Plan (as specified in the skill) before writing any cell.

### 3B. Required Notebook: `00_system_checkpoint.ipynb`

**Purpose:** Designer-level health check. Run at any time to see system state in 2 minutes.

**Notebook Plan:**
- Path: `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb`
- Feature being tested: Overall system health
- Public entry points: CLI subprocess calls, direct file checks, pytest subprocess

**Required sections:**
1. **Purpose** — "Run this notebook to see the current state of the ingestion system"
2. **Setup** — imports: subprocess, pathlib, yaml, json, pandas
3. **Phase Status Table** — DataFrame with columns [Phase, What It Does, Status, Key Output]
   ```
   Phase 1A | Source registry | ✅ Complete | data/raw/.../source_registry.latest.json
   Phase 1B | Provider profiling | ✅ Complete | data/raw/.../provider_profiles.latest.json
   Agent Core | Ingestion pipeline | ✅ Substantially complete | 17 DB tables
   Test Coverage | Epics G-Q | ⚠️ In progress | target: 145 tests
   Phase 2 | Document discovery | ❌ Not started | —
   ```
4. **Test Suite Status** — run `pytest tests/ -q` via subprocess, parse count, display pass/fail
5. **Artifact Existence Check** — for each expected output file, check if it exists on disk
6. **Source Registry Summary** — load `configs/amc_sources.yaml`, show AMC count, enabled count
7. **Provider Profile Summary** — load latest profiles JSON, show strategy breakdown as bar chart
8. **CLI Smoke Test** — run `python -m mutual_fund_ingestion --help` via subprocess, confirm exit 0
9. **Phase 2 Gate Check** — auto-check each gate criterion, show ✅ or ❌
10. **Assertions** — assert test count ≥ 125, assert source registry has ≥ 50 entries, assert profile file exists
11. **Summary** — green/yellow/red status per section

### 3C. Required Notebook: `02_agent_pipeline_inspection.ipynb`

**Purpose:** Inspect a full agent pipeline run step by step.

**Notebook Plan:**
- Path: `notebooks/mutual_fund_ingestion/02_agent_pipeline_inspection.ipynb`
- Feature being tested: Task-URL Agent end-to-end pipeline
- Public entry points: `agent/db.py` → `create_tables()`, `agent/config.py` → `AgentConfig`, `agent/runner.py` → `IngestionRunner`

**Required sections:**
1. **Purpose** — "Run this notebook to trace a complete agent pipeline run"
2. **Setup** — imports from production modules only. SQLite for easy local testing.
3. **Database Init** — call `create_tables()`, confirm all 17 tables exist, display table list
4. **Config** — show `AgentConfig` with test parameters (sqlite URL, max_pages=2, dry_run=False)
5. **Run: Bounded Crawl** — run against AMFI NAV URL with max_pages=2. Show log output.
6. **Inspect: ingestion_runs** — DataFrame of runs, columns: run_id, status, start_time, end_time
7. **Inspect: source_pages** — DataFrame: url, status_code, relevance_score, dataset_type_hint
8. **Inspect: discovered_links** — DataFrame: url, link_text, relevance, file_type
9. **Inspect: dataset_candidates** — DataFrame: url, dataset_type, confidence
10. **Inspect: raw_artifacts** — DataFrame: filename, file_type, size_bytes, checksum, retained
11. **Inspect: staging_rows** — sample 5 rows, show raw fields
12. **Inspect: validation_results** — show valid_count, quarantine_count, reason breakdown
13. **Inspect: canonical tables** — row counts for amcs, schemes, nav_history, portfolio_holdings
14. **Inspect: quarantine_rows** — show reason codes and sample bad records
15. **Edge Case: invalid URL** — run with a known-bad URL, show how failure is captured
16. **Assertions** — assert run_id exists, assert source_pages count > 0, assert no crash
17. **Debugging Notes** — where to look if each stage fails
18. **Summary** — pipeline stage status, what worked, what quarantined, readiness assessment

### 3D. Verify Existing Notebooks

Check that these three Phase 1 notebooks run cell-by-cell without error:
- `01_phase_1_provider_profiling_review.ipynb`
- `01a_phase_1_source_registry_review.ipynb`
- `01b_phase_1_provider_profiling_review.ipynb`

If any cell fails: fix the import path or missing file reference. Do not rewrite the notebook.
Document result in `docs/01_status/MASTER_STATE.md`.

---

## PART 4 — Plan Restructure

### 4A. Create `docs/06_plans/GOAL_ALIGNMENT.md`

Content:
```markdown
# Goal Alignment
Every task must serve at least one milestone.

## Primary Goal
Reproducible provider-first ingestion → PostgreSQL → analytics over fund holdings.

## Milestones
1. CURRENT: System is inspectable (notebooks run, 125+ tests passing)
2. Pipeline fully tested (≥145 tests, all parser paths verified)
3. Phase 2 produces real documents (3+ AMCs, 1+ Excel downloaded)
4. Canonical tables populated with real data (2+ AMCs in PostgreSQL)
5. Analytics queries exist (fund overlap, accumulation signals, sector exposure)

## Not a Goal Now
- Frontend / dashboard
- Investment recommendations
- All-PDF parsing
- Analytics before real data exists
- Real-time data

## Alignment Check (before any new task)
Q: Which milestone does this task advance?
Q: Is it blocked by anything incomplete?
Q: Does it touch ≤3 files? (if not, split it)
Q: Does it produce a verifiable test output?
```

### 4B. Create `docs/06_plans/SPRINT_CURRENT.md`

```markdown
# Sprint Current
Updated: [DATE] | Tests: 125 passing | Next target: 145

## Phase 2 Gate Criteria
- [ ] Epic G (6 validation tasks) — all complete
- [ ] Epic H (5 discovery tests) — all complete
- [ ] Epic P (portfolio Excel fixture test) — complete
- [ ] Epic N (NAV HTML end-to-end test) — complete
- [ ] Test count ≥ 145

## Active Task (Pi is working on this)
[Insert current MICROTASK_SPEC content here]

## Next 5 Tasks (in order)
1. TASK-B001: Update PLAN.md — mark tasks 1/2 complete
2. TASK-B002: Update task_url_ingestion_agent.md
3. TASK-B003: Update CHATGPT_PROJECT_MEMORY.md — test count to 125
4. TASK-B004: Fix CODEBASE_MAP.md stale claims
5. TASK-G001: Add validate_scheme_master_record()

## Sprint Goal
Complete documentation cleanup (Batch B) and begin validation coverage (Batch E)
so that test count reaches 135 by end of this sprint.

## Sprint Gate
- [ ] All Batch B tasks complete
- [ ] At least 2 Epic G tasks complete
- [ ] Test count ≥ 130
- [ ] system_checkpoint notebook runs without error
```

### 4C. Split TASKS_FULL_SYSTEM_MICRO_PLAN.md into Batch Files

For each batch in `docs/06_plans/active/` and `docs/06_plans/backlog/`, create one file.
Extract the relevant tasks from `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` into that file.

Format for each batch file:
```markdown
# Batch [X] — [Name]
# Milestone served: [N]
# Status: [active / backlog / complete]
# Gate: [what "done" means for this batch]

## Tasks

### TASK-XXX: [Title]
**Goal:** One sentence.
**Files to read:** [list]
**Files to modify:** [list]
**Exact work:** [numbered steps]
**Acceptance criteria:** [list]
**Test command:** [bash command]
**Do not do:** [list]
**Status:** pending | in_progress | complete
```

### 4D. Update TASKS_FULL_SYSTEM_MICRO_PLAN.md

Mark these tasks as `Status: complete` (per the 2026-06-23 audit):
A001, A002, A004, D002, E001, E002, E003, E004, E005, E006, E007,
F002, F003, K004, L001, N003, P001, P004, R001, R002, R003, R004, S001, S002

---

## PART 5 — Skills Enforcement

### 5A. Copy Skills Into docs/07_agent_rules/skills/

Copy the content of these skill files into the agent rules directory:
- `design_layered_module.md` — from the skills system
- `write_notebook.md` — from the skills system
- `session_handoff.md` — from the skills system

These files must be referenced in every task spec that involves:
- Creating or editing a notebook → reference `write_notebook.md`
- Creating or editing a module → reference `design_layered_module.md`
- Ending a session → reference `session_handoff.md`

### 5B. Create `docs/07_agent_rules/task_generation_rules.md`

```markdown
# Task Generation Rules
Claude Code must apply these rules when writing any MICROTASK_SPEC.md for Pi.

## Mandatory references per task type

| Task touches | Must reference skill |
|---|---|
| New notebook | docs/07_agent_rules/skills/write_notebook.md |
| New module or new file in agent/ | docs/07_agent_rules/skills/design_layered_module.md |
| Session end / handoff | docs/07_agent_rules/skills/session_handoff.md |
| Multiple files in same module | docs/07_agent_rules/skills/design_layered_module.md |

## Mandatory checks before writing a task spec

1. Does this task serve a milestone in GOAL_ALIGNMENT.md?
2. Does Pi have all the context it needs in "Files to Read"?
3. Is the task ≤3 files? If not, split it.
4. Does it have a single verifiable test command?
5. Does it have clear acceptance criteria?
6. Have you listed what NOT to do?
7. Does it reference the correct skill if applicable?

## Anti-patterns Pi must not produce (check before accepting result)

- Production logic inside a notebook cell
- Importing from deep internal files (not from public interfaces)
- runner.py growing beyond 300 lines
- Duplicate schema definitions
- New validators not wired into runner.py
- Tests that pass via mocking the thing being tested
- Task marked complete without running the test command
```

### 5C. Update CLAUDE_CODE_PRIMER.md

Add a section: **"Skills to Apply"** listing the three skill files and when to invoke them.
Claude Code must check which skills apply before writing each MICROTASK_SPEC.

---

## PART 6 — Pi Guidance Generation

After completing Parts 1–5, generate the first real MICROTASK_SPEC.md for Pi.

This spec must be written to `docs/06_plans/MICROTASK_SPEC.md` and must:
- Reference only files that exist in the restructured docs system
- Apply the relevant skills (for TASK-B001, session_handoff is relevant; no code skill needed)
- Be executable by Pi in one session without clarification

The first task for Pi after the restructure is TASK-B001 from `docs/06_plans/active/BATCH_B_docs.md`.
Pi should also be directed to verify the restructure is complete before starting B001.

---

## PART 7 — What Claude Code Produces (Deliverables)

At the end of this session, produce this exact status report to the terminal:

```
=== RESTRUCTURE SESSION COMPLETE ===

DOCS UMBRELLA:
  ✓/✗ docs/00_project/ created with 3 files
  ✓/✗ docs/01_status/ created: MASTER_STATE.md, session_state.md, AGENT_EXECUTION_LOG.md
  ✓/✗ docs/02_architecture/ created with codebase_map.md (merged, corrected)
  ✓/✗ docs/03_implemented/ populated (phase_1a, phase_1b, task_url_agent)
  ✓/✗ docs/04_in_progress/ created with test_coverage_epics/
  ✓/✗ docs/05_planned/ populated (phase_2_discovery + stubs)
  ✓/✗ docs/06_plans/ created: GOAL_ALIGNMENT.md, SPRINT_CURRENT.md, active/, backlog/, completed/
  ✓/✗ docs/07_agent_rules/ created: skills/, CLAUDE_CODE_PRIMER.md, SMALL_MODEL_GUIDE.md, task_generation_rules.md
  ✓/✗ docs/09_historical/legacy/ populated with archived docs
  ✓/✗ Root-level duplicate docs moved to archive
  ✓/✗ source_memory/ moved to archive
  ✓/✗ docs/README.md created with full table of contents + session-type routing

CODEBASE ASSESSMENT:
  ✓/✗ Layer audit completed for agent/ modules
  ✓/✗ Layer audit completed for profiling/ modules
  ✓/✗ Violations documented in docs/01_status/MASTER_STATE.md
  ✓/✗ Refactor candidates flagged (if any)
  ✓/✗ Conclusion: acceptable / needs refactor (state which)

NOTEBOOKS:
  ✓/✗ 00_system_checkpoint.ipynb — created, runs without error
  ✓/✗ 02_agent_pipeline_inspection.ipynb — created, runs without error
  ✓/✗ Phase 1 notebooks (01, 01a, 01b) — verified they run
  ✓/✗ All notebooks comply with write_notebook skill structure

PLANS:
  ✓/✗ GOAL_ALIGNMENT.md created
  ✓/✗ SPRINT_CURRENT.md created
  ✓/✗ Batch files created: B, E, F, G in active/; I-M in backlog/; A in completed/
  ✓/✗ TASKS_FULL_SYSTEM_MICRO_PLAN.md: ~25 tasks marked complete
  ✓/✗ MICROTASK_SPEC.md for TASK-B001 ready for Pi

SKILLS ENFORCEMENT:
  ✓/✗ Skills copied into docs/07_agent_rules/skills/
  ✓/✗ task_generation_rules.md created
  ✓/✗ CLAUDE_CODE_PRIMER.md updated with skills reference

TESTS:
  [N] tests passing (must be ≥ 125, same as before this session)
  ✓/✗ No regressions introduced

FILES ARCHIVED: [N] files moved to docs/09_historical/legacy/
FILES MODIFIED: [N] files updated in place
FILES CREATED: [N] new files

SESSION HANDOFF: docs/01_status/session_state.md — updated
NEXT TASK FOR PI: TASK-B001 — waiting in docs/06_plans/MICROTASK_SPEC.md
===
```

---

## PART 8 — Rules for This Session

- No new Python features
- No modifications to `mutual_fund_ingestion/profiling/` (frozen)
- No modifications to `mutual_fund_ingestion/amfi_disclosure/` (legacy)
- No Phase 2 code
- If moving a file would break an existing import or reference, fix the reference before moving
- Notebooks must import from production modules — never reimplement logic in cells
- Write the Notebook Plan (from write_notebook skill) before creating any notebook
- Write the Layer Plan (from design_layered_module skill) before creating any new module
- Apply session_handoff skill at end of session to produce docs/01_status/session_state.md
