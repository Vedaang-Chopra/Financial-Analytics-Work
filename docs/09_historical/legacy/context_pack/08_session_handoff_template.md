# Session Handoff Template

_Reusable template for end-of-session context transfer._
_Copy and fill in before ending a session. Save to `docs/session_state.md` (replace old content)._

---

```markdown
# Session Handoff — Financial Analytics Work

Date: YYYY-MM-DD
Session: [brief description, e.g., "Epic G validation coverage"]

---

## Verified State at Handoff

Test suite:
```
./financial_env/bin/python -m pytest tests/ -q
[paste output here — must include final pass count]
```

Current pass count: NNN

---

## Current Task / Batch

Batch: [e.g., Batch E — Validation Coverage]
Task in progress: TASK-GXXX — [title]
Status at handoff: [complete / in_progress / blocked]

---

## Completed This Session

- TASK-XXXX: [title] — [what was done]
- TASK-XXXX: [title] — [what was done]

---

## Files Changed This Session

- `path/to/file.py` — [what changed and why]
- `path/to/test_file.py` — [what was added]

---

## Tests Run

Command:
```bash
./financial_env/bin/python -m pytest tests/ -q
```

Result: NNN passed / N failed

If failed, paste the failure output:
```
[failure output here]
```

---

## Known Blockers

[List any issues that must be resolved before the next task can proceed]

- BLOCKER: [description]
  - Root cause: [what was found]
  - Files involved: [list]
  - Escalation needed: [yes/no]

If none: None.

---

## Next Exact Task

Task ID: TASK-XXXX
Task title: [from TASKS_FULL_SYSTEM_MICRO_PLAN.md]
Why this is next: [dependency chain or priority rationale]

---

## Files the Next Agent Must Read

1. `plans/SMALL_MODEL_EXECUTION_GUIDE.md` — execution rules
2. `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` — find task TASK-XXXX
3. `docs/agent_context/01_current_system_state.md` — current state
4. [List files from the task's "Files to read" section]

---

## Files the Next Agent May Edit

[List files from the task's "Files to edit" section]

---

## What NOT to Touch

- `mutual_fund_ingestion/profiling/` — Phase 1A/1B, frozen
- `mutual_fund_ingestion/amfi_disclosure/` — legacy prototype, not coupled to agent pipeline
- `docs/design/` — specs, only update if implementation diverges
- Any file not listed in the task spec
```

---

## Guidance for Filling This Template

**Test count**: Always run the test suite before filling in. Never estimate.

**Files changed**: List exact paths. Do not abbreviate.

**Next task**: Look at `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md`, find the first `Status: pending` task whose dependencies have `Status: complete`.

**Blockers**: Only list real blockers. A task that "seems hard" is not a blocker. A missing file, failing test, or ambiguous requirement is.

**Do not**: fill in "Next task" as "continue from where I left off." Name the exact task ID.
