# Plan: System Governance, Notebook Redesign, and Roadmap Reset
**Spec:** `docs/05_planned/system_governance_notebook_roadmap/001_system_governance_notebook_roadmap.md`
**Status:** Confirmed

## Summary

This plan resets the project around the current numbered documentation hierarchy, rewrites the existing notebooks in place as inspection contracts, clears stale generated data through an explicit confirmed cleanup task, and leaves the next implementation agent with one current roadmap. The key architectural decision is to treat this as a governance and inspection reset first: no new ingestion features are built until docs, notebooks, current state, and generated-data assumptions are clean.

## Layer Assignment

| Component | Layer | File Path | Reason |
|---|---|---|---|
| Current-state reconciliation | Documentation | `docs/01_status/*.md` | Establishes the single truth for tests, phase status, and next task |
| Architecture reconciliation | Documentation | `docs/02_architecture/*.md` | Keeps module ownership and diagrams aligned with live code |
| Phase roadmap reset | Documentation | `docs/05_planned/*`, `docs/06_plans/*` | Defines what agents build next without mixing phases |
| Generated-data cleanup manifest | Documentation / Operations | `docs/06_plans/active/001_data_cleanup_manifest.md` | Lists exact cleanup paths before destructive execution |
| System checkpoint notebook | Layer 1 | `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb` | Human-readable system health and verification surface |
| Phase 1 notebook index | Layer 1 | `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb` | Stable entry point to Phase 1 inspection |
| Phase 1A registry notebook | Layer 1 | `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb` | Source registry inspection and readiness assertions |
| Phase 1B profiling notebook | Layer 1 | `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb` | Provider profile strategy and unresolved-provider inspection |
| Agent pipeline notebook | Layer 1 | `notebooks/mutual_fund_ingestion/02_agent_pipeline_inspection.ipynb` | Public-runner-based pipeline inspection |
| Legacy task-url notebook | Layer 1 | `notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb` | Rewrite in place or convert to a thin pointer, removing stale internals |
| Phase 2 discovery notebook | Layer 1 | `notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb` | Fresh-output discovery review after cleanup/rerun |
| Optional public inspection API | Layer 2 | `mutual_fund_ingestion/agent/runner.py` or new approved public module | Only if notebooks need stage visibility not exposed through existing public entry points |
| Tests for public inspection helpers | Tests | `tests/` | Only if a new public helper is added |

## Files to Create

| File | Layer | Purpose |
|---|---|---|
| `docs/06_plans/active/001_system_governance_notebook_tasks.md` | Planning | Executable task list after this plan is approved |
| `docs/06_plans/active/001_system_governance_notebook_seq_exec_prompt.md` | Planning | Sequential execution prompt after task list approval |
| `docs/06_plans/active/001_data_cleanup_manifest.md` | Documentation / Operations | Exact generated-data paths proposed for cleanup, with exclusions |

## Files to Modify

| File | What changes | Reason |
|---|---|---|
| `docs/01_status/MASTER_STATE.md` | Reconcile test count, phase status, runner refactor status, next checkpoint | It is the current-state source of truth |
| `docs/01_status/session_state.md` | Update resume point, approved plan links, cleanup/rerun expectation | Future agents need a clean handoff |
| `docs/01_status/AGENT_EXECUTION_LOG.md` | Add entries for governance reset tasks as they complete | Required cross-agent failure log |
| `docs/02_architecture/codebase_map.md` | Add missing current modules and full notebook inventory | Prevents duplicate ownership and stale imports |
| `docs/02_architecture/layer_model.md` | Remove stale 821-line runner violation or replace with current audit | Current layer rules should match live code |
| `docs/02_architecture/system_overview.md` | Confirm flow and phase boundaries, update if stale | Keeps pipeline map current |
| `docs/02_architecture/database_schema.md` | Confirm table inventory is current | Keeps DB docs aligned with `agent/db.py` |
| `docs/04_in_progress/REFACTOR_runner.md` | Mark complete/stale and point to actual extracted modules | Prevents agents from redoing completed refactor |
| `docs/04_in_progress/test_coverage_epics/overview.md` | Reconcile live test baseline and remaining coverage gaps | Prevents stale count chasing |
| `docs/05_planned/README.md` | Add planning-path convention and current phase map | Makes numbered hierarchy explicit |
| `docs/05_planned/phase_2_discovery/README_PHASE_2_CODEX_PACK.md` | Clarify discovery vs raw download expectations after cleanup | Avoids conflating current discovery output with completed Phase 2 |
| `docs/05_planned/phase_3_classification/README.md` | State gate depends on fresh raw downloads, not stale candidates | Keeps future phase blocked until evidence exists |
| `docs/05_planned/phase_4_plus/README.md` | State gate depends on classification and real parsed data | Prevents analytics jumping ahead |
| `docs/06_plans/CHECKPOINT_PLAN.md` | Reset checkpoint order around cleanup, notebook validation, fresh rerun, raw download | Drives the next execution loop |
| `docs/06_plans/SPRINT_CURRENT.md` | Replace stale B001/G001 task list with this reset | Gives Pi/Codex one current next task |
| `docs/06_plans/GOAL_ALIGNMENT.md` | Update milestone wording if needed for fresh-data reset | Keeps tasks tied to user goals |
| `README.md` | Update visible test count and notebook/phase guidance if stale | Root entry point should not contradict docs |
| `AGENTS.md` | Add numbered-planning-path override if missing | Project governance should reflect user decision |
| Existing notebooks under `notebooks/mutual_fund_ingestion/` | Rewrite in place to follow notebook skill | User wants proper notebooks at stable paths |

## Dependency Order

1. **Planning path reconciliation**
   - Update docs to state that this project uses the numbered hierarchy for specs, plans, tasks, and execution prompts.
   - Ensure no agent is sent back to `docs/specs/` as the canonical path.

2. **Current-state audit**
   - Re-run or cite current tests.
   - Audit live module list, notebook list, key artifacts, and status docs.
   - Identify stale claims before editing them.

3. **Generated-data cleanup manifest**
   - List exact data/runtime paths to clear.
   - Explicitly exclude configs, docs, notebooks, tests, source files, credentials, historical archives, and manually curated fixtures.
   - Require human confirmation before deletion commands.

4. **Documentation truth reset**
   - Update status, architecture, phase, sprint, and checkpoint docs against the audit.
   - Mark completed refactor docs stale/complete rather than deleting history.

5. **Notebook stage-function audit**
   - For each notebook, list stages and the public entry point it can call.
   - If a stage lacks a public callable, add a narrowly scoped public inspection helper only after documenting the gap.

6. **Notebook rewrites in place**
   - Rewrite notebooks in stable filenames.
   - Add setup, stage blocks, assertions, edge/failure cases, artifact inspection, debugging notes, and summaries.
   - Keep live network actions optional or bounded.

7. **Notebook validation**
   - Run structural validation.
   - Execute notebooks where tooling allows.
   - Document any tooling limitation explicitly.

8. **Fresh rerun readiness**
   - After cleanup and notebook reset, leave commands for the user to rerun the system.
   - Do not claim fresh data exists until the user reruns or an approved task runs the collection.

9. **Next-feature roadmap**
   - Rebuild the next checkpoint sequence from fresh data:
     - candidate selection,
     - real raw document download,
     - metadata sidecar verification,
     - preview notebook,
     - then Phase 3 classification spec.

## Integration Points

| Existing module or artifact | What changes for it |
|---|---|
| `AGENTS.md` | Records the numbered planning hierarchy override |
| `docs/README.md` | Routes humans/agents to the canonical current state and notebook workflow |
| `docs/01_status/MASTER_STATE.md` | Becomes the live-state baseline again |
| `docs/02_architecture/codebase_map.md` | Documents current module ownership and notebooks |
| `docs/06_plans/CHECKPOINT_PLAN.md` | Becomes the active execution roadmap |
| `notebooks/mutual_fund_ingestion/*.ipynb` | Become structured inspection surfaces, not stale demos |
| `mutual_fund_ingestion/agent/runner.py` | Remains the preferred public runner entry point; only small public inspection additions if required |
| `data/` | Old generated outputs are cleared only after an approved cleanup task confirms exact paths |

## Risks and Open Questions

- The worktree is already dirty. The executing agent must preserve unrelated changes and avoid overwriting concurrent edits.
- Data cleanup is destructive. The task must request confirmation before deletion.
- Rewriting notebooks in place can make diffs noisy. The task file should isolate notebooks by filename so review remains manageable.
- Some notebooks currently import internals. If public stage callables do not exist, the plan allows minimal interface work, but that must stay narrow.
- `nbconvert` may not be installed. The execution task should try it and fall back to structural validation or direct sequential cell execution.
- No open product questions remain from the spec.

## Validation Criteria

- [ ] `./financial_env/bin/python -m pytest tests/ -q --tb=no` passes with the current expected count documented from live output.
- [ ] `rg -n "821 lines|148 passed|50 tests|125 passed|docs/ai_context|docs/design|confirmed_disclosure_url|--max-downloads" docs notebooks README.md AGENTS.md` returns no stale active-doc claims, except historical/archive references explicitly allowed.
- [ ] `rg -n "from mutual_fund_ingestion\\.(agent|profiling)\\.(discovery|extract|validate|profiler|source_discovery)" notebooks/mutual_fund_ingestion` returns no disallowed retained-notebook imports.
- [ ] Every retained notebook has at least three assertions.
- [ ] Every retained production workflow notebook has at least five substantive stage cells or is intentionally converted to an index/pointer notebook.
- [ ] Data cleanup manifest exists and lists exact cleanup paths and exclusions.
- [ ] No destructive cleanup command is run without confirmation.
- [ ] `docs/01_status/session_state.md` points to the active plan, task file, and next execution step.
