# Spec: System Governance, Notebook Redesign, and Roadmap Reset
**ID:** 001
**Status:** Confirmed

## Purpose

Bring the Financial Analytics mutual fund ingestion repository back into a state where agents can continue goal-driven development without conflicting instructions, stale status claims, stale runtime artifacts, or notebooks that obscure system behavior.

This work is needed now because the live system has advanced beyond several planning documents. The test suite currently reports `145 passed, 3 skipped`, while some status docs claim `148 passed`. The runner refactor appears complete in the live tree, but older refactor and layer-model docs still describe it as pending. Several notebooks exist, but they do not consistently follow the governance notebook rules: stage blocks, assertions, public-entry imports, failure cases, and artifact inspection.

The outcome should be a clean planning and inspection foundation before further Phase 2/3/4 implementation proceeds.

## Confirmed Planning Decisions

- Future formal planning artifacts for this project use the numbered docs hierarchy, not the global `docs/specs/`, `docs/plans/`, `docs/tasks/`, and `docs/execution-plans/` paths.
- This spec is canonical at `docs/05_planned/system_governance_notebook_roadmap/001_system_governance_notebook_roadmap.md`.
- The corresponding technical plan should live under `docs/06_plans/`.
- The executable task breakdown should live under `docs/06_plans/active/`.
- The sequential execution prompt should live under `docs/06_plans/active/`.
- Existing notebooks should be rewritten in place so their visible filenames remain stable.
- Older runtime data should be cleared before the user reruns the system, but the cleanup must be planned as an explicit task with confirmation before any destructive command is executed.

## Affected Modules

Approximate scope for the later plan:

- `docs/01_status/`
  - Reconcile `MASTER_STATE.md`, `session_state.md`, and `AGENT_EXECUTION_LOG.md` against live verification.
- `docs/02_architecture/`
  - Reconcile `codebase_map.md`, `layer_model.md`, `system_overview.md`, and `database_schema.md` against the current tree.
- `docs/04_in_progress/`
  - Retire or update stale refactor/test-coverage documents.
- `docs/05_planned/`
  - Reframe Phase 2/3/4+ boundaries so discovery, raw download, classification, parsing, canonical loading, and analytics are not conflated.
- `docs/06_plans/`
  - Replace stale sprint/microtask pointers with the next executable checkpoint sequence.
- `notebooks/mutual_fund_ingestion/`
  - Redesign system, Phase 1, agent, Phase 2, and future real-document notebooks as inspection surfaces.
- `data/`
  - Clear older generated runtime/artifact data as an explicit reset task so the next user-run collects fresh evidence.
- `mutual_fund_ingestion/`
  - Only touched if notebook stage-function audits prove a stable public inspection entry point is missing.
- `tests/`
  - Only touched if documentation or notebook validation requires lightweight smoke coverage for public inspection helpers.

## Out of Scope

- No new ingestion behavior in this spec.
- No full Phase 2 raw-document download implementation.
- No Phase 3 document classifier implementation.
- No Phase 4 parser/staging implementation.
- No analytics layer implementation.
- No changes to `api.env`, credentials, secrets, or database credentials.
- No immediate deletion of old data in the planning phase. Data cleanup must be an approved execution task with exact paths and confirmation before destructive commands.
- No cleanup of unrelated dirty-worktree changes unless a later approved task explicitly owns that cleanup.
- No import from `mutual_fund_ingestion/amfi_disclosure/` into the provider-first Phase 1+ pipeline.
- No broad reorganization of the repository beyond planning/documentation/notebook paths explicitly approved in the plan.

## Acceptance Criteria

- [ ] A single current-state truth exists for test baseline, phase status, active checkpoint, and next task.
- [ ] Live validation command is documented with the observed result: `./financial_env/bin/python -m pytest tests/ -q --tb=no`.
- [ ] Stale runner-refactor claims are resolved across status and architecture docs.
- [ ] The project documentation states that future planning artifacts use the numbered docs hierarchy.
- [ ] Architecture docs reflect the current module structure, including `agent/upserts.py` and `agent/artifact_processor.py`.
- [ ] `docs/04_in_progress/REFACTOR_runner.md` is either marked complete/stale or replaced by a current refactor audit.
- [ ] Phase boundaries are clear:
  - Phase 1A: source registry.
  - Phase 1B: provider profiling.
  - Phase 1.5: strategy resolution only if still needed by unresolved profiles.
  - Phase 2: raw document discovery/download artifacts.
  - Phase 3: document classification.
  - Phase 4: parsing/staging/canonical loading.
  - Phase 5+: analytics.
- [ ] Notebook inventory is documented in `codebase_map.md` or the project documentation hub.
- [ ] Every retained notebook has a clear purpose, setup, stage blocks, at least three assertions, at least one failure/edge case, artifact inspection where relevant, debugging notes, and a summary.
- [ ] Existing notebook filenames remain stable, with notebooks rewritten in place rather than replaced by differently named notebooks.
- [ ] Notebooks use public entry points only, or the plan explicitly adds minimal public inspection interfaces before notebook rewrites.
- [ ] Old generated runtime/artifact data is cleared through an explicit, confirmed cleanup task before the user reruns the system.
- [ ] The next agent can start from a single approved task file and know exactly what to do, verify, update, and where to stop.

## Validation Plan

- Run the live test suite:

```bash
./financial_env/bin/python -m pytest tests/ -q --tb=no
```

- Validate notebooks structurally:
  - Every notebook has required sections.
  - Every production workflow notebook has at least five substantive stage cells.
  - Every retained notebook has at least three assertions.
  - No retained notebook imports implementation internals when a public entry point exists.

- Execute notebook smoke checks where tooling is available:

```bash
./financial_env/bin/python -m jupyter nbconvert --to notebook --execute notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb --stdout
```

If `nbconvert` or Jupyter tooling is unavailable, document that limitation and use sequential cell execution or structural validation as the fallback.

- Verify documentation consistency with targeted searches:

```bash
rg -n "821 lines|148 passed|50 tests|125 passed|docs/ai_context|docs/design|confirmed_disclosure_url|--max-downloads" docs notebooks README.md AGENTS.md
```

- Verify public entry points for notebooks:

```bash
rg -n "from mutual_fund_ingestion\\.(agent|profiling)\\.(discovery|extract|validate|profiler|source_discovery)" notebooks/mutual_fund_ingestion
```

Expected: no retained notebook imports internal implementation modules unless the approved plan explicitly permits it for a documented reason.

- Verify cleanup task safety before any deletion:

```bash
find data/tmp/mutual_funds data/raw/mutual_funds data/reports/mutual_funds data/debug/mutual_funds -maxdepth 3 -type f 2>/dev/null | sort
```

Expected: the execution task lists exact cleanup paths and excludes source code, configs, docs, notebooks, tests, credentials, and historical archives.

## Known Risks / Limitations

- The worktree is already dirty, including docs, ingestion code, tests, runtime outputs, and new Phase 2 artifacts. The plan must preserve unrelated edits and avoid overwriting user or prior-agent work.
- Some notebook validation may require Jupyter/nbconvert packages that are not guaranteed to be installed in `financial_env`.
- Live provider websites can change. Network-dependent notebook sections must be bounded, optional by default, or based on existing artifacts.
- The status docs mention both `145 passed, 3 skipped` and `148 passed`; the plan must treat live test output as authoritative.
- Clearing old data is intentionally destructive. The execution task must ask for confirmation before running deletion commands.
- After old data is cleared, Checkpoint 3 should not assume the prior Aditya Birla candidate remains meaningful; the user will rerun the system and fresh evidence should drive candidate selection.

## Resolved Questions

1. Planning artifacts use the numbered project hierarchy.
2. Existing notebooks are rewritten in place.
3. Older generated data is cleared before rerun; Checkpoint 3 should select candidates from fresh outputs rather than relying on stale prior runtime artifacts.

## Open Questions

None for the spec.

Proceed to the technical plan after this spec is accepted as the governing scope.
