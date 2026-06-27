# SESSION ZERO — Claude Code Restructure Brief
# Paste this file into Claude Code as the first message of the session.
# Purpose: restructure docs, plans, and create missing notebooks. No new features.

---

## Your Role This Session

You are the architect agent. This session is about structure, not features.

Do NOT implement new code. Do NOT add parsers. Do NOT write Phase 2.
Your job is to make the existing system inspectable, organized, and testable.

---

## What This System Is

An Indian mutual fund disclosure ingestion pipeline. It collects public investor disclosure
documents from AMC/provider websites, parses them, validates them, and loads them into PostgreSQL.

**Current verified state (2026-06-23):**
- Phase 1A/1B: Complete and frozen (source registry + provider profiling)
- Task-URL Agent: Core pipeline substantially complete (17 DB tables, parsers, VLM, CLI)
- Tests: 125 passing
- Missing: notebooks for the agent pipeline, organized plan structure, clean doc hierarchy

---

## Read These Files First (In Order)

```
1. AGENTS.md
2. CLAUDE.md
3. docs/agent_context/README.md
4. docs/agent_context/01_current_system_state.md
5. docs/agent_context/02_verified_codebase_map.md
6. docs/agent_context/05_next_execution_roadmap.md
7. docs/agent_context/06_microtask_batch_plan.md
8. docs/ai_context/CODEBASE_MAP.md
9. plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md (scan only — get a feel for the 140 tasks)
10. notebooks/ directory listing (what notebooks currently exist)
```

---

## Audit First — Then Act

Before changing anything, produce a brief audit to console:
```
AUDIT RESULTS:
- Notebooks that exist: [list]
- Notebooks that are missing: [list]
- Docs root files that are duplicates: [list]
- Plans/ structure current shape: [describe]
- Test count confirmed: [run pytest -q]
```

---

## Task 1: Fix the Notebook Gap (Highest Priority)

The user cannot test the system because there is no notebook for the agent pipeline.

**Phase 1 notebooks (already exist — verify they run):**
- `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb`
- `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb`
- `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb`

**Create these missing notebooks:**

### Notebook A: `notebooks/mutual_fund_ingestion/02_agent_pipeline_inspection.ipynb`

This notebook lets the user inspect a completed agent run without running live network code.

Sections:
1. **Setup** — imports, db connection (sqlite default), verify tables exist with `create_tables()`
2. **Run a bounded dry-run** — `run-agent` against the AMFI NAV URL with `--max-pages 2 --dry-run`
3. **Inspect ingestion_runs** — show run_id, status, start/end time as DataFrame
4. **Inspect source_pages** — show pages visited, status codes, relevance scores
5. **Inspect discovered_links** — show links found, dataset_type hints, relevance scores
6. **Inspect dataset_candidates** — show what was identified as downloadable content
7. **Inspect raw_artifacts** — show files downloaded (if any), checksums, file sizes
8. **Inspect staging_rows** — sample of parsed rows before validation
9. **Inspect validation_results** — show valid vs. quarantined counts
10. **Inspect canonical tables** — row counts for: amcs, schemes, nav_history, portfolio_holdings
11. **Inspect quarantine_rows** — show any quarantined records with reason codes
12. **Summary** — green/yellow/red status per pipeline stage
13. **Readiness gate** — what is needed before Phase 2 can start

Cell style: short, readable. Use `pd.DataFrame()` for all tabular output. No production logic in cells.

### Notebook B: `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb`

This is the designer's notebook. Run this at any time to see system health.

Sections:
1. **Phase status table** — Phase 1A ✅, Phase 1B ✅, Agent Core ✅, Phase 2 ❌, etc.
2. **Test suite status** — run `pytest tests/ -q` via subprocess, display count + any failures
3. **Artifact existence checks** — do the Phase 1A/1B output files exist on disk?
4. **Source registry summary** — how many AMCs in configs/amc_sources.yaml
5. **Provider profile summary** — how many providers profiled, strategy breakdown
6. **CLI smoke test** — `python -m mutual_fund_ingestion --help` runs without error
7. **What is blocked** — auto-list items from the Phase 2 gate criteria that are not yet met

---

## Task 2: Restructure docs/

Current problem: 25+ docs with overlapping content, no clear separation of done vs. pending.

**Create this structure:**

```
docs/
├── agent_context/           ← KEEP AS-IS (do not touch)
├── ai_context/              ← KEEP AS-IS (CODEBASE_MAP.md lives here)
├── implemented/             ← NEW: completed phase specs (frozen, read-only)
│   ├── README.md
│   ├── phase_1a/            ← move Phase 1A spec content here
│   ├── phase_1b/            ← move Phase 1B spec content here
│   └── task_url_agent/      ← move task_url_agent_design_pack/ content here
├── planned/                 ← NEW: not-yet-implemented phase specs
│   ├── README.md
│   ├── phase_2_discovery/   ← move docs/design/phase_2/ content here
│   ├── phase_3_classification/ (create stub README)
│   └── phase_4_plus/        (create stub README)
├── historical/              ← KEEP AS-IS (created 2026-06-23)
└── README_DOCS_INDEX.md     ← UPDATE to reflect new structure
```

**Archive these to docs/historical/duplicates/ (do not delete):**
- All root-level numbered docs (`00_CLAUDE_MASTER_CONTEXT.md`, `01_PROJECT_DECISIONS...`, etc.)
- `source_memory/` entire directory
- `docs/design/mutual_fund_project_memory_pack/`

**Update in place (do not move):**
- `docs/ai_context/CODEBASE_MAP.md` — fix 4 stale claims (VLM wired ✅, portfolio bug fixed ✅, nav_html added ✅, retention implemented ✅)
- `CHATGPT_PROJECT_MEMORY.md` — update test count to 125
- `README.md` — update test count to 125

---

## Task 3: Restructure plans/

Current problem: One massive TASKS_FULL_SYSTEM_MICRO_PLAN.md with 140 tasks. Agents read all of it and lose context. Humans cannot track it.

**Create this structure:**

```
plans/
├── README.md                    ← How the planning system works
├── GOAL_ALIGNMENT.md            ← The high-level goals all micro-plans must serve
├── SPRINT_CURRENT.md            ← ONE FILE: what Pi is doing right now + next 5 tasks
├── active/
│   ├── README.md
│   ├── BATCH_B_docs.md          ← Extract Batch B tasks here
│   ├── BATCH_E_validation.md    ← Extract Batch E tasks here
│   ├── BATCH_F_discovery.md     ← Extract Batch F tasks here
│   └── BATCH_G_browser_vlm.md  ← Extract Batches G+H tasks here
├── backlog/
│   ├── README.md
│   ├── BATCH_I_retention.md
│   ├── BATCH_J_nav.md
│   ├── BATCH_K_scheme_amc.md
│   ├── BATCH_L_portfolio.md
│   ├── BATCH_M_metadata.md
│   └── phase_2_tasks_TBD.md    ← placeholder, tasks to be written before Phase 2
└── completed/
    ├── README.md
    └── BATCH_A_hygiene.md       ← Extract completed Batch A tasks here
```

**SPRINT_CURRENT.md format (critical — this is what Pi reads):**
```markdown
# Current Sprint
Updated: YYYY-MM-DD | Tests: NNN passing

## Active Task (Pi is working on this)
[copy the full task block from the batch plan]

## Next 5 Tasks (in order)
1. TASK-XXX: [one line]
2. TASK-XXX: [one line]
...

## Sprint Goal
[1 sentence: what does this sprint accomplish toward the bigger goal]

## Sprint Gate (how we know sprint is done)
- [ ] criterion 1
- [ ] criterion 2
```

**GOAL_ALIGNMENT.md — create this file:**
```markdown
# Goal Alignment Reference
Every micro-plan must serve at least one of these goals.

## Primary Goal
Build a reproducible, provider-first ingestion system that populates PostgreSQL
with validated mutual fund portfolio disclosure data — enabling analytics over
holdings, sector allocation, and fund overlap.

## Sub-Goals (in priority order)
1. Ensure the existing agent pipeline is fully tested and verifiably correct
2. Extend parser coverage to real AMC disclosure documents (Phase 2)
3. Add validation coverage for all dataset types
4. Build analytics queries once canonical tables are populated with real data

## What Is NOT a Goal (right now)
- Frontend dashboard
- Investment recommendations
- Real-time data
- Complete PDF parsing
- Analytics before real data exists

## Alignment Check (for any new task)
Before adding a task, answer: which sub-goal does this serve?
If it serves none of the above, defer or discard.
```

---

## Task 4: Update TASKS_FULL_SYSTEM_MICRO_PLAN.md

Mark all verified-complete tasks as `Status: complete` per the audit in `docs/agent_context/03_documentation_audit.md`.

Verified complete tasks include: A001, A002, A004, D002, E001-E007, F002, F003, K004, L001, N003, P001, P004, R001-R004, S001-S002 (and others per the audit doc).

Do NOT mark anything complete unless it was verified in the audit.

---

## Task 5: Update docs/session_state.md

Replace with a current handoff using `docs/agent_context/08_session_handoff_template.md`.
Test count: 125. No current blockers. Next task: TASK-B001.

---

## Deliverables This Session

At the end of this session, report:

```
RESTRUCTURE COMPLETE:
✓/✗ Notebook 02_agent_pipeline_inspection.ipynb — created and runs without error
✓/✗ Notebook 00_system_checkpoint.ipynb — created and runs without error
✓/✗ docs/implemented/ created and populated
✓/✗ docs/planned/ created and populated
✓/✗ docs/historical/duplicates/ — duplicate files archived
✓/✗ plans/active/ — batch files created
✓/✗ plans/SPRINT_CURRENT.md — created
✓/✗ plans/GOAL_ALIGNMENT.md — created
✓/✗ TASKS_FULL_SYSTEM_MICRO_PLAN.md — ~25 tasks marked complete
✓/✗ CODEBASE_MAP.md — 4 stale claims fixed
✓/✗ README.md + CHATGPT_PROJECT_MEMORY.md — test counts updated
✓/✗ docs/session_state.md — replaced with current handoff
✓/✗ Test suite still passes: NNN tests

FILES CHANGED: [list]
TESTS: [count] passing
REGRESSIONS: none / [describe]
```

---

## Rules for This Session

- No new Python code beyond what is needed for notebooks
- No modifications to `mutual_fund_ingestion/profiling/` (frozen)
- No modifications to `mutual_fund_ingestion/amfi_disclosure/` (legacy)
- No Phase 2 code
- If a restructure step would break an import or reference, fix the reference — do not skip the restructure
- Notebooks must use the real production modules (`from mutual_fund_ingestion...`), not reimplemented logic
