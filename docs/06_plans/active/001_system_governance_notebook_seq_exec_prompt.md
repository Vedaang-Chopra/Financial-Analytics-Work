# Sequential Execution Prompt — System Governance, Notebook Redesign, and Roadmap Reset
# Copy this entire prompt and paste it as the first message to Pi or another executing agent.

---

You are executing a pre-planned governance and notebook reset for Financial Analytics Work.
Read and follow exactly. Do not improvise.

## Before Starting

1. Read `~/agent-governance/AGENTS.md` fully.
2. Read this project's `AGENTS.md` fully.
3. Read `docs/README.md`.
4. Read `docs/05_planned/system_governance_notebook_roadmap/001_system_governance_notebook_roadmap.md`.
5. Read `docs/06_plans/001_system_governance_notebook_roadmap_plan.md`.
6. Read `docs/06_plans/active/001_system_governance_notebook_tasks.md`.
7. Read `docs/02_architecture/codebase_map.md`.
8. Read `docs/01_status/AGENT_EXECUTION_LOG.md`; do not repeat anything marked failed.
9. Read `docs/01_status/session_state.md`; resume from where it indicates if mid-session.

## Project Planning Path Override

This project uses the numbered docs hierarchy:

- Specs: `docs/05_planned/`
- Plans: `docs/06_plans/`
- Active task files: `docs/06_plans/active/`
- Sequential execution prompts: `docs/06_plans/active/`

Do not create `docs/specs/`, `docs/plans/`, `docs/tasks/`, or `docs/execution-plans/` unless the human explicitly changes the project convention.

## Task File

All tasks are in:

```text
docs/06_plans/active/001_system_governance_notebook_tasks.md
```

Current status of each task is tracked there:

- `[ ]` pending
- `[x]` complete

If a task is not marked with a checkbox yet, add one only when you begin execution, and mark it `[x]` only after its verify step passes.

## Execution Loop

For each task in order:

1. Read the task entry fully.
2. Check `docs/01_status/AGENT_EXECUTION_LOG.md` for known failure patterns on files this task touches.
3. Select model from the task's `Model hint` field using the project Model Registry.
4. Execute only the task's listed work.
5. Run the task's `Verify` command.
6. If verification fails:
   - Diagnose the failure.
   - Fix and rerun verify.
   - Max 2 fix attempts.
   - If still failing after 2 attempts: stop, write failure to `AGENT_EXECUTION_LOG.md`, update `session_state.md`, output a summary, and stop the session.
7. Mark the task `[x]` only after Verify passes.
8. Write the required Change Report.
9. Write an `AGENT_EXECUTION_LOG.md` entry.
10. Update `docs/01_status/session_state.md`.

## Parallel Group Handling

Most tasks are sequential because they touch shared docs.

Group 2-B notebook rewrite tasks may be run in parallel only if separate agents are assigned separate task IDs. If a single agent is executing, run them one at a time without a human gate until Sync Point 2-B.

At Sync Point 2-B:

1. Confirm Tasks 2.2, 2.3, 2.4, 2.5, and 2.6 are marked `[x]`.
2. Confirm each task's Verify command passed.
3. Confirm no task has unresolved errors.
4. Write one sync point entry to `AGENT_EXECUTION_LOG.md`.
5. Stop if any task failed.

## Phase Boundaries

At every `*.final` task:

1. READ `~/agent-governance/skills/core/verify-checkpoint.md`.
2. Run all phase gates.
3. After the checkpoint task is `[x]`, STOP and output a summary.
4. Wait for human confirmation before starting the next phase.

## Data Cleanup Safety

Task 1.3 writes the cleanup manifest only.

Do not delete generated data during planning or manifest writing.

Any destructive cleanup command such as `rm` requires explicit human confirmation before execution. When requesting confirmation, show the exact paths to be deleted and the exclusions from `001_data_cleanup_manifest.md`.

Never touch:

- `api.env`
- `.env*`
- credentials or key files
- `configs/`
- source code
- tests
- notebooks
- docs
- historical archives
- curated fixtures

## Notebook Rules

When rewriting notebooks:

- Rewrite existing notebook filenames in place.
- Do not create replacement filenames unless the task explicitly says to.
- Do not put production logic in notebooks.
- Do not import implementation internals if a public runner/CLI/module surface exists.
- Include setup, stage blocks, assertions, edge/failure case, artifact inspection, debugging notes, and summary.
- Keep live network actions optional, bounded, or artifact-based.
- Make notebooks handle cleared/empty generated data gracefully.

## Context Window Management

Monitor context usage. At approximately 60-70% context consumed:

1. Complete the current task fully.
2. Run its Verify command.
3. Write `AGENT_EXECUTION_LOG.md` entry.
4. Update `docs/01_status/session_state.md` with exact resume point.
5. Output:

```text
Context at [X]%. Stopping cleanly after task [N.M].
Next task: [N.M+1 - name].
Resume by starting a new session with this execution prompt.
```

6. Stop. Do not start the next task.

## Rate Limit Handling

If a model returns 429:

1. Wait 60 seconds.
2. Retry once.
3. If still rate-limited, use the task's fallback model.
4. Log the fallback in the Change Report and `AGENT_EXECUTION_LOG.md`.

## What You May Not Do

- Do not skip a task.
- Do not mark a task `[x]` before its Verify passes.
- Do not proceed past Sync Point 2-B if any notebook task failed.
- Do not proceed past a phase checkpoint without human confirmation.
- Do not invent structure or modify files outside the task's specified files.
- Do not repeat any approach marked failed in `AGENT_EXECUTION_LOG.md`.
- Do not run destructive cleanup without explicit human confirmation.
- Do not claim fresh data exists until the user reruns the system or an approved task collects it.

## Completion Report Format

After every task, output:

```markdown
## Change Report

### Files Modified
- `path` — what changed, layer, why

### Files Created
- `path` — purpose and layer

### Files Archived
- None

### Documentation Updated
- ...

### Diagrams Updated
- ...

### Validation Run
- Command and result

### Validation NOT Run
- What was not tested and why

### Known Limitations / Follow-up Work
- ...

### Execution Log Updated
- Summary
```
