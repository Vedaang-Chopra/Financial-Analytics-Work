# Small Model Execution Guide

This guide tells a smaller coding model (~120B) exactly how to use `TASKS_FULL_SYSTEM_MICRO_PLAN.md` safely.

---

## The One Rule

**Execute exactly one task per session. Stop when it is done.**

---

## How to Choose the Next Task

1. Open `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md`.
2. Find the first task with `Status: pending`.
3. Check its `Dependencies` field. All listed task IDs must have `Status: complete`.
4. If a dependency is not complete, skip to the next task whose dependencies are met.
5. Start that task and only that task.

---

## How Much Context to Load

Load only:
- `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` — for the task definition
- `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md` — for system context if needed
- The exact files listed under **Files to read** for the current task
- The exact files listed under **Files to edit** for the current task

Do not load the full repository. Do not read files not listed in the task.

---

## Rules During Execution

1. **One task only.** Do not fix unrelated bugs you notice. Do not refactor adjacent code.
2. **Read listed files only.** If implementation requires a file not listed, stop and report it.
3. **Run the exact test command** listed under `Test command`. Do not substitute a different command.
4. **Stop on failure.** If tests fail, do not attempt a second approach. Report the failure.
5. **Do not combine tasks.** Even if two tasks look similar, execute them separately.
6. **Do not rewrite modules** unless the task explicitly says to replace a function or class.
7. **Do not delete files** unless the task explicitly says to delete a specific file.
8. **Do not add imports** beyond what the task requires.
9. **Make the smallest correct change.** Prefer adding lines over rewriting blocks.
10. **Never change test files** unless the task is in Epic R or says "Files to edit: tests/...".

---

## Prompt Template: Execute One Task

Copy this prompt when launching a small model on a task:

```
You are executing exactly one task from plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md.

Task ID: <TASK-ID>
Task title: <title from the plan>

Read only:
- plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md (for the task definition)
- plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md (for system context if needed)
- <list every file under "Files to read" for this task>

Edit only:
- <list every file under "Files to edit" for this task>

Follow the implementation steps exactly as written. Make the smallest correct change.
Run this exact command when done:
  <test command from the task>

Report back:
1. Files changed and what was changed
2. Full test output (pass/fail)
3. Whether the task is complete or blocked
4. Any files you needed to read that were not listed (so the plan can be updated)
```

---

## Prompt Template: Debug a Failed Task

```
Task <TASK-ID> failed. Here is the test output:

<paste test output>

Read only:
- plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md (task definition)
- <files listed in task>

Do not attempt a different approach. Diagnose the failure:
1. What exactly failed?
2. Is the failure in the code change or in the test setup?
3. What is the minimal fix?

If you cannot determine the root cause from the listed files, report what additional file you need to read. Do not read files speculatively.
```

---

## Prompt Template: Mark Task Complete

After a task passes, update its status line in `TASKS_FULL_SYSTEM_MICRO_PLAN.md`:

```
Change:
  Status: pending
To:
  Status: complete
```

Do this immediately. Do not batch status updates.

---

## When to Escalate to a Larger Model

Stop and escalate if any of the following are true:

1. A task requires understanding system behavior across more than 3 files not listed in the task.
2. A task fails and the root cause cannot be determined from the listed files.
3. The implementation steps in the task appear incorrect or contradictory.
4. The test command does not exist or tests a different behavior than described.
5. You discover that a dependency task produced incorrect output that breaks this task.
6. The task requires a design decision (e.g., "which approach is correct?") not answered in the task or spec.
7. A test reveals a bug in a different part of the system that must be fixed first.

When escalating, provide:
- Task ID and title
- What you attempted
- Exact error or ambiguity
- Which files you read

---

## Task Status Values

| Status | Meaning |
|---|---|
| `pending` | Not started |
| `in_progress` | Currently executing (set this before starting) |
| `complete` | Test passed, changes committed |
| `blocked` | Cannot proceed; dependency or ambiguity must be resolved |
| `skipped` | Intentionally skipped (note reason) |

---

## Dependency Resolution

- If task B depends on A and A is `blocked`, mark B as `blocked` too.
- Never execute a task whose dependency is `blocked` unless the plan explicitly says it is independent.
- If a dependency is `skipped`, verify that the skip does not break the current task before proceeding.

---

## Key File Locations

| What | Where |
|---|---|
| Task plan | `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` |
| Status/audit doc | `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md` |
| Target state spec | `plans/TECHNICAL_SPEC_AGENT_TARGET_STATE.md` |
| Testing strategy | `plans/TESTING_STRATEGY_AND_FIXTURE_PLAN.md` |
| Governance rules | `AGENTS.md` |
| Module ownership | `docs/ai_context/CODEBASE_MAP.md` |
| CLI entry point | `mutual_fund_ingestion/cli.py` |
| Agent orchestration | `mutual_fund_ingestion/agent/runner.py` |
| DB schema | `mutual_fund_ingestion/agent/db.py` |
| Parser router | `mutual_fund_ingestion/agent/parser/__init__.py` |
