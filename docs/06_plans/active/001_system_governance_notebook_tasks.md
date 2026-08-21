# Tasks: System Governance, Notebook Redesign, and Roadmap Reset
**Spec:** `docs/05_planned/system_governance_notebook_roadmap/001_system_governance_notebook_roadmap.md`
**Plan:** `docs/06_plans/001_system_governance_notebook_roadmap_plan.md`
**Status:** Awaiting human approval

Execute one phase at a time. Do not proceed past a phase checkpoint without human confirmation.

## Phase 1 — Governance and Current-State Truth

**Goal:** Make the repository state, planning paths, stale-claim inventory, and cleanup scope explicit before rewriting notebooks.

**Entry condition:** Spec and plan are approved.

**Exit condition:** Active docs agree on the numbered planning hierarchy, live test baseline, current module structure, and exact generated-data cleanup scope.

### Dependency Analysis

| Task | Reads from | Writes to | Depends on |
|---|---|---|---|
| 1.1 | `AGENTS.md`, `docs/README.md`, `docs/05_planned/README.md` | same files | none |
| 1.2 | live tree, docs, notebooks | `docs/06_plans/active/001_current_state_audit.md` | 1.1 |
| 1.3 | `data/`, `docs/06_plans/active/001_current_state_audit.md` | `docs/06_plans/active/001_data_cleanup_manifest.md` | 1.2 |
| 1.4 | status and architecture docs, audit | status and architecture docs | 1.2, 1.3 |
| 1.final | all Phase 1 outputs | status/log docs | 1.1-1.4 |

### Group 1-A — Sequential

#### Task 1.1 — Record Numbered Planning Hierarchy
**Phase:** 1
**Parallel group:** 1-A sequential
**Depends on:** none
**Model hint:** local
**Rate limit flag:** no
**Fallback model:** complex-reasoning
**Layer:** Documentation
**File(s):**
  - `AGENTS.md` — modify
  - `docs/README.md` — modify
  - `docs/05_planned/README.md` — modify
**What to build:** Document that this project uses the numbered docs hierarchy for formal planning: specs under `docs/05_planned/`, plans under `docs/06_plans/`, executable task files and sequential execution prompts under `docs/06_plans/active/`. Remove or override active guidance that sends agents to `docs/specs/`, `docs/plans/`, `docs/tasks/`, or `docs/execution-plans/` as canonical for this project.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown docs only.
**Verify:**
```bash
rg -n "docs/specs|docs/plans|docs/tasks|docs/execution-plans" AGENTS.md docs/README.md docs/05_planned/README.md
```
Expected: any matches clearly explain these are global defaults overridden by the numbered project hierarchy.
**Checkpoint:** Phase 1
**AGENT_EXECUTION_LOG notes:** Log the planning-path decision. Do not duplicate global AGENTS content; add only project-specific override.

#### Task 1.2 — Write Current-State Audit
**Phase:** 1
**Parallel group:** 1-A sequential
**Depends on:** Task 1.1
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Documentation / Audit
**File(s):**
  - `docs/06_plans/active/001_current_state_audit.md` — create
**What to build:** Create a concise audit of live facts before editing status docs. Include current `git status --short` summary, test command/result, module file inventory for `mutual_fund_ingestion/agent/`, notebook inventory with assertion/stage/import findings, stale active-doc claims found by `rg`, and generated-data paths currently present.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown audit with command snippets and observed results.
**Verify:**
```bash
test -f docs/06_plans/active/001_current_state_audit.md
rg -n "145 passed, 3 skipped|runner.py|notebook|stale|data/tmp" docs/06_plans/active/001_current_state_audit.md
```
Expected: audit exists and contains the required evidence sections.
**Checkpoint:** Phase 1
**AGENT_EXECUTION_LOG notes:** Note that live test output is authoritative over stale status docs.

#### Task 1.3 — Draft Generated-Data Cleanup Manifest
**Phase:** 1
**Parallel group:** 1-A sequential
**Depends on:** Task 1.2
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Documentation / Operations
**File(s):**
  - `docs/06_plans/active/001_data_cleanup_manifest.md` — create
**What to build:** List exact generated data/runtime paths proposed for cleanup before the user reruns the system. Include exclusions: source code, configs, docs, notebooks, tests, credentials, curated fixtures, `api.env`, historical archives. Include the exact destructive commands as proposed commands only, not executed commands. State that execution requires human confirmation.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown cleanup manifest.
**Verify:**
```bash
test -f docs/06_plans/active/001_data_cleanup_manifest.md
rg -n "REQUIRES CONFIRMATION|Do not delete|api.env|configs|notebooks|tests|rm" docs/06_plans/active/001_data_cleanup_manifest.md
```
Expected: manifest exists, lists exclusions, and marks destructive commands as confirmation-gated.
**Checkpoint:** Phase 1
**AGENT_EXECUTION_LOG notes:** Do not run `rm`; only write the manifest.

#### Task 1.4 — Reconcile Status and Architecture Docs
**Phase:** 1
**Parallel group:** 1-A sequential
**Depends on:** Tasks 1.2, 1.3
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Documentation
**File(s):**
  - `docs/01_status/MASTER_STATE.md` — modify
  - `docs/01_status/session_state.md` — modify
  - `docs/02_architecture/codebase_map.md` — modify
  - `docs/02_architecture/layer_model.md` — modify
  - `docs/02_architecture/system_overview.md` — modify if stale
  - `docs/02_architecture/database_schema.md` — modify if stale
  - `docs/04_in_progress/REFACTOR_runner.md` — modify
  - `docs/04_in_progress/test_coverage_epics/overview.md` — modify
  - `docs/06_plans/CHECKPOINT_PLAN.md` — modify
  - `docs/06_plans/SPRINT_CURRENT.md` — modify
  - `docs/06_plans/GOAL_ALIGNMENT.md` — modify if stale
  - `README.md` — modify if stale
**What to build:** Update active docs to match the audit. The runner refactor must be marked complete/stale instead of pending. Test baseline must match live output. Notebook inventory must include all retained notebooks. Phase 2 must be described as not complete until fresh raw document download evidence exists after cleanup/rerun.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown docs.
**Verify:**
```bash
rg -n "821 lines|148 passed|50 tests|125 passed|confirmed_disclosure_url|--max-downloads" docs/01_status docs/02_architecture docs/04_in_progress docs/06_plans README.md
```
Expected: no stale active-doc claims remain, except lines explicitly marked historical/stale with current correction.
**Checkpoint:** Phase 1
**AGENT_EXECUTION_LOG notes:** Do not delete historical docs; mark stale active docs clearly.

#### Task 1.final — Verify Phase 1 Checkpoint
**Phase:** 1
**Parallel group:** 1-A sequential
**Depends on:** Tasks 1.1-1.4
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Checkpoint
**File(s):**
  - `docs/01_status/AGENT_EXECUTION_LOG.md` — modify
  - `docs/01_status/session_state.md` — modify
**What to build:** READ `~/agent-governance/skills/core/verify-checkpoint.md`. Verify Phase 1 outputs and write the required execution log entry and session-state resume point.
**Function signatures:** Not applicable.
**Input shape / output shape:** Checkpoint report in docs/logs.
**Verify:**
```bash
test -f docs/06_plans/active/001_current_state_audit.md
test -f docs/06_plans/active/001_data_cleanup_manifest.md
rg -n "001_system_governance_notebook" docs/01_status/session_state.md docs/01_status/AGENT_EXECUTION_LOG.md
```
Expected: Phase 1 artifacts exist and session/log docs reference the reset work.
**Checkpoint:** Phase 1 hard stop
**AGENT_EXECUTION_LOG notes:** Write a sync/checkpoint entry. HARD STOP after this task and wait for human approval before Phase 2.

---

## Phase 2 — Notebook Stage Audit and Rewrites

**Goal:** Rewrite existing notebooks in place so they are proper inspection surfaces and do not depend on stale outputs or internal imports.

**Entry condition:** Phase 1 checkpoint approved.

**Exit condition:** Retained notebooks pass structural checks, contain required assertions/stage blocks, and either execute or have documented tooling limitations.

### Dependency Analysis

| Task | Reads from | Writes to | Depends on |
|---|---|---|---|
| 2.1 | notebooks, codebase map, public APIs | `docs/06_plans/active/001_notebook_stage_audit.md` | Phase 1 |
| 2.2 | stage audit | `00_system_checkpoint.ipynb` | 2.1 |
| 2.3 | stage audit | `01_phase_1_provider_profiling_review.ipynb`, `01a_phase_1_source_registry_review.ipynb` | 2.1 |
| 2.4 | stage audit | `01b_phase_1_provider_profiling_review.ipynb` | 2.1 |
| 2.5 | stage audit | `02_agent_pipeline_inspection.ipynb`, `02_task_url_ingestion_agent_inspection.ipynb` | 2.1 |
| 2.6 | stage audit | `03_phase2_discovery_review.ipynb` | 2.1 |
| 2.final | all notebooks | status/log docs | 2.2-2.6 |

### Group 2-A — Sequential

#### Task 2.1 — Notebook Stage-Function Audit
**Phase:** 2
**Parallel group:** 2-A sequential
**Depends on:** Phase 1 approval
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Documentation / Notebook audit
**File(s):**
  - `docs/06_plans/active/001_notebook_stage_audit.md` — create
**What to build:** For every notebook in `notebooks/mutual_fund_ingestion/`, list purpose, intended stages, public callable used for each stage, current assertion count, current `[STAGE]` block count, and whether it imports internals. If any required stage lacks a public callable, document the minimal public interface task needed and stop before notebook rewrites.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown audit table.
**Verify:**
```bash
test -f docs/06_plans/active/001_notebook_stage_audit.md
rg -n "00_system_checkpoint|01a_phase_1|01b_phase_1|02_agent|03_phase2|public callable|assertions" docs/06_plans/active/001_notebook_stage_audit.md
```
Expected: each retained notebook has an audit row and public-callable decision.
**Checkpoint:** Phase 2
**AGENT_EXECUTION_LOG notes:** If interface gaps block notebook rewrites, stop and report instead of importing internals.

### Group 2-B — Parallel After 2-A

Tasks in this group write different notebook files and can be executed independently after Task 2.1. If one agent is executing, run them sequentially without a human gate until the sync point.

#### Task 2.2 — Rewrite System Checkpoint Notebook
**Phase:** 2
**Parallel group:** 2-B
**Depends on:** Task 2.1
**Model hint:** fast-code
**Rate limit flag:** yes
**Fallback model:** local
**Layer:** Layer 1 — Notebook
**File(s):**
  - `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb` — modify
**What to build:** Rewrite in place to show current tests, module inventory, DB/schema availability, artifact presence after cleanup, and rerun readiness. Include setup, at least five substantive stage cells, at least three assertions, one failure/tooling case, artifact inspection, debugging notes, and summary.
**Function signatures:** Not applicable.
**Input shape / output shape:** Jupyter notebook.
**Verify:**
```bash
./financial_env/bin/python - <<'PY'
import json
from pathlib import Path
nb=json.loads(Path('notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb').read_text())
src=''.join(''.join(c.get('source', [])) for c in nb['cells'])
assert src.count('assert ') >= 3
assert src.count('[STAGE]') >= 5
print('00 notebook structural checks passed')
PY
```
Expected: structural checks pass.
**Checkpoint:** Phase 2
**AGENT_EXECUTION_LOG notes:** Keep live network off by default.

#### Task 2.3 — Rewrite Phase 1 Index and Source Registry Notebook
**Phase:** 2
**Parallel group:** 2-B
**Depends on:** Task 2.1
**Model hint:** fast-code
**Rate limit flag:** yes
**Fallback model:** local
**Layer:** Layer 1 — Notebook
**File(s):**
  - `notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb` — modify
  - `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb` — modify
**What to build:** Keep `01_phase_1_provider_profiling_review.ipynb` as a thin index with current links and artifact expectations. Rewrite `01a` in place to inspect `configs/amc_sources.yaml`, source registry artifacts, provenance distribution, unresolved sources, and Phase 1B readiness. Include required stage blocks, assertions, edge/failure case, artifact inspection, debugging notes, and summary.
**Function signatures:** Not applicable.
**Input shape / output shape:** Jupyter notebooks.
**Verify:**
```bash
./financial_env/bin/python - <<'PY'
import json
from pathlib import Path
for name in ['01a_phase_1_source_registry_review.ipynb']:
    nb=json.loads((Path('notebooks/mutual_fund_ingestion')/name).read_text())
    src=''.join(''.join(c.get('source', [])) for c in nb['cells'])
    assert src.count('assert ') >= 3, name
    assert src.count('[STAGE]') >= 5, name
print('phase 1A notebook structural checks passed')
PY
```
Expected: Phase 1A notebook structural checks pass.
**Checkpoint:** Phase 2
**AGENT_EXECUTION_LOG notes:** Do not reimplement registry logic in notebook cells.

#### Task 2.4 — Rewrite Phase 1B Provider Profiling Notebook
**Phase:** 2
**Parallel group:** 2-B
**Depends on:** Task 2.1
**Model hint:** fast-code
**Rate limit flag:** yes
**Fallback model:** local
**Layer:** Layer 1 — Notebook
**File(s):**
  - `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb` — modify
**What to build:** Rewrite in place to inspect provider profile artifacts, detected strategies, candidate links, debug artifacts, unresolved providers, and whether Phase 1.5 is needed. Include required stage blocks, assertions, edge/failure case, artifact inspection, debugging notes, and summary.
**Function signatures:** Not applicable.
**Input shape / output shape:** Jupyter notebook.
**Verify:**
```bash
./financial_env/bin/python - <<'PY'
import json
from pathlib import Path
nb=json.loads(Path('notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb').read_text())
src=''.join(''.join(c.get('source', [])) for c in nb['cells'])
assert src.count('assert ') >= 3
assert src.count('[STAGE]') >= 5
print('phase 1B notebook structural checks passed')
PY
```
Expected: structural checks pass.
**Checkpoint:** Phase 2
**AGENT_EXECUTION_LOG notes:** Do not claim Phase 2 readiness from stale provider profiles after cleanup.

#### Task 2.5 — Rewrite Agent Pipeline Notebooks
**Phase:** 2
**Parallel group:** 2-B
**Depends on:** Task 2.1
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Layer 1 — Notebook
**File(s):**
  - `notebooks/mutual_fund_ingestion/02_agent_pipeline_inspection.ipynb` — modify
  - `notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb` — modify
**What to build:** Rewrite `02_agent_pipeline_inspection` as the canonical public-runner pipeline inspection. Rewrite `02_task_url_ingestion_agent_inspection` in place to either become a compatibility pointer to the canonical notebook or a proper inspection notebook without stale test counts or internal imports. Include stage blocks, assertions, failure case, artifact/DB inspection, debugging notes, and summary.
**Function signatures:** Not applicable unless stage audit approved a public helper.
**Input shape / output shape:** Jupyter notebooks.
**Verify:**
```bash
rg -n "from mutual_fund_ingestion\\.(agent|profiling)\\.(discovery|extract|validate|profiler|source_discovery)|50 tests" notebooks/mutual_fund_ingestion/02_agent_pipeline_inspection.ipynb notebooks/mutual_fund_ingestion/02_task_url_ingestion_agent_inspection.ipynb
```
Expected: no disallowed internal imports or stale `50 tests` claim.
**Checkpoint:** Phase 2
**AGENT_EXECUTION_LOG notes:** If a public inspection helper is needed, stop before adding it unless the task file is updated.

#### Task 2.6 — Rewrite Phase 2 Discovery Notebook
**Phase:** 2
**Parallel group:** 2-B
**Depends on:** Task 2.1
**Model hint:** fast-code
**Rate limit flag:** yes
**Fallback model:** local
**Layer:** Layer 1 — Notebook
**File(s):**
  - `notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb` — modify
**What to build:** Rewrite in place as a fresh-output discovery review. It should handle empty/cleared data gracefully, show how to inspect a new run after the user reruns the system, and avoid treating stale Aditya Birla output as current truth. Include required stage blocks, assertions, edge case, artifact/DB inspection, debugging notes, and summary.
**Function signatures:** Not applicable.
**Input shape / output shape:** Jupyter notebook.
**Verify:**
```bash
./financial_env/bin/python - <<'PY'
import json
from pathlib import Path
nb=json.loads(Path('notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb').read_text())
src=''.join(''.join(c.get('source', [])) for c in nb['cells'])
assert src.count('assert ') >= 3
assert src.count('[STAGE]') >= 5
assert 'fd1040ef-2ede-4433-94e5-7f282ec3e392' not in src
print('phase 2 discovery notebook structural checks passed')
PY
```
Expected: structural checks pass and no hardcoded stale run ID remains.
**Checkpoint:** Phase 2
**AGENT_EXECUTION_LOG notes:** Notebook should work after cleanup with no fresh data yet.

---
### *** SYNC POINT 2-B ***
Before proceeding to Task 2.final:
- [ ] Task 2.2 verify passes
- [ ] Task 2.3 verify passes
- [ ] Task 2.4 verify passes
- [ ] Task 2.5 verify passes
- [ ] Task 2.6 verify passes
- [ ] No unresolved errors in notebook Change Reports
---

### Group 2-C — Sequential Integration

#### Task 2.final — Verify Notebook Checkpoint
**Phase:** 2
**Parallel group:** 2-C sequential
**Depends on:** Tasks 2.2-2.6 and Sync Point 2-B
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Checkpoint
**File(s):**
  - `docs/01_status/AGENT_EXECUTION_LOG.md` — modify
  - `docs/01_status/session_state.md` — modify
  - `docs/02_architecture/codebase_map.md` — modify if notebook inventory changed
**What to build:** READ `~/agent-governance/skills/core/verify-checkpoint.md`. Run structural notebook checks across all retained notebooks. Execute notebooks with nbconvert if available; if not available, document fallback validation. Update status docs with which notebooks passed and what was not run.
**Function signatures:** Not applicable.
**Input shape / output shape:** Checkpoint report.
**Verify:**
```bash
./financial_env/bin/python - <<'PY'
import json
from pathlib import Path
for path in sorted(Path('notebooks/mutual_fund_ingestion').glob('*.ipynb')):
    nb=json.loads(path.read_text())
    src=''.join(''.join(c.get('source', [])) for c in nb['cells'])
    if 'index' not in path.name:
        assert src.count('assert ') >= 3, path
        assert src.count('[STAGE]') >= 5, path
print('all retained workflow notebooks passed structural checks')
PY
```
Expected: structural checks pass or intentional index/pointer exception is documented.
**Checkpoint:** Phase 2 hard stop
**AGENT_EXECUTION_LOG notes:** Write sync point entry and HARD STOP after this task.

---

## Phase 3 — Fresh Rerun Readiness and Next-Feature Roadmap

**Goal:** Leave the user with clean rerun instructions and leave agents with a fresh-data-dependent next-feature plan.

**Entry condition:** Phase 2 checkpoint approved.

**Exit condition:** User has explicit rerun commands; next tasks depend on fresh outputs rather than stale data.

### Dependency Analysis

| Task | Reads from | Writes to | Depends on |
|---|---|---|---|
| 3.1 | cleanup manifest, notebooks, docs | `docs/06_plans/active/001_user_rerun_guide.md` | Phase 2 |
| 3.2 | fresh-data roadmap requirements | `docs/06_plans/backlog/001_post_rerun_next_tasks.md` | 3.1 |
| 3.final | all outputs | status/log docs | 3.1, 3.2 |

### Group 3-A — Sequential

#### Task 3.1 — Write User Rerun Guide
**Phase:** 3
**Parallel group:** 3-A sequential
**Depends on:** Phase 2 approval
**Model hint:** local
**Rate limit flag:** no
**Fallback model:** complex-reasoning
**Layer:** Documentation / Operations
**File(s):**
  - `docs/06_plans/active/001_user_rerun_guide.md` — create
**What to build:** Write a concise guide for the user to clear generated data using the approved manifest, then rerun source registry/profile/discovery steps and open the rewritten notebooks. Include commands but do not execute collection. Make clear that fresh evidence is user-generated after cleanup.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown guide.
**Verify:**
```bash
test -f docs/06_plans/active/001_user_rerun_guide.md
rg -n "bootstrap-sources|profile-providers|run-agent|00_system_checkpoint|03_phase2" docs/06_plans/active/001_user_rerun_guide.md
```
Expected: guide exists and includes rerun commands/notebook paths.
**Checkpoint:** Phase 3
**AGENT_EXECUTION_LOG notes:** Do not run live collection in this task.

#### Task 3.2 — Write Post-Rerun Next Tasks Backlog
**Phase:** 3
**Parallel group:** 3-A sequential
**Depends on:** Task 3.1
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Planning
**File(s):**
  - `docs/06_plans/backlog/001_post_rerun_next_tasks.md` — create
**What to build:** Define the next feature tasks that become executable only after the user reruns the system and fresh artifacts exist: candidate quality review, real document download, sidecar verification, preview notebook, Phase 3 classification spec. Each task must state its fresh-data prerequisite.
**Function signatures:** Not applicable.
**Input shape / output shape:** Markdown backlog.
**Verify:**
```bash
test -f docs/06_plans/backlog/001_post_rerun_next_tasks.md
rg -n "fresh|candidate|download|sidecar|classification spec" docs/06_plans/backlog/001_post_rerun_next_tasks.md
```
Expected: backlog exists and all tasks are gated on fresh outputs.
**Checkpoint:** Phase 3
**AGENT_EXECUTION_LOG notes:** Do not mark post-rerun tasks active until fresh artifacts exist.

#### Task 3.final — Verify Roadmap Reset Checkpoint
**Phase:** 3
**Parallel group:** 3-A sequential
**Depends on:** Tasks 3.1, 3.2
**Model hint:** complex-reasoning
**Rate limit flag:** no
**Fallback model:** local
**Layer:** Checkpoint
**File(s):**
  - `docs/01_status/AGENT_EXECUTION_LOG.md` — modify
  - `docs/01_status/session_state.md` — modify
  - `docs/06_plans/SPRINT_CURRENT.md` — modify
**What to build:** READ `~/agent-governance/skills/core/verify-checkpoint.md`. Verify the rerun guide and post-rerun backlog, update the sprint to show the current reset complete, and set the next human action as rerunning the system.
**Function signatures:** Not applicable.
**Input shape / output shape:** Checkpoint report.
**Verify:**
```bash
test -f docs/06_plans/active/001_user_rerun_guide.md
test -f docs/06_plans/backlog/001_post_rerun_next_tasks.md
rg -n "rerun|fresh|001_post_rerun_next_tasks" docs/01_status/session_state.md docs/06_plans/SPRINT_CURRENT.md
```
Expected: final docs point to rerun guide and fresh-data backlog.
**Checkpoint:** Phase 3 hard stop
**AGENT_EXECUTION_LOG notes:** Write final reset-complete entry.

---

## Checkpoint Coverage Audit

- [x] Every module touched has a public-surface task where needed: notebook stage audit must identify public callables before notebook rewrites; no `interfaces.py` file exists in this project, so the public surfaces are `cli.py`, `runner.py`, and approved public modules.
- [x] Every required output file has an owning task: current-state audit (1.2), cleanup manifest (1.3), notebook stage audit (2.1), rerun guide (3.1), post-rerun backlog (3.2), execution prompt (separate generated file).
- [x] Every behavior in the confirmed spec maps to at least one task.
- [x] Every phase ends with an explicit verify-checkpoint task.
- [x] Every parallel group has a sync point: Group 2-B has Sync Point 2-B; other groups are sequential.
- [x] Known failed/stale patterns are incorporated: stale test counts, stale runner refactor, internal notebook imports, stale Phase 2 candidate, and destructive cleanup confirmation.
- [x] Every task has a model hint and fallback.
- [x] Free-tier model tasks in Group 2-B are safe to run sequentially by one agent or staggered by humans if parallelized.
