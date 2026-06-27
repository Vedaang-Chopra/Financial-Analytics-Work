---
name: handoff-coding-agent
description: >
  Use at the end of any coding agent session that will be resumed later — whether
  at a phase checkpoint or mid-task. Produces docs/session_state.md so the next
  agent can resume without re-reading the full task history, without asking the
  human to re-explain context, and without risking duplicate or conflicting work.
  Triggers: session ending, "save state", "I'll continue later", phase checkpoint
  passed and stopping, or before switching agent models.
---

# SKILL: handoff-coding-agent

## Purpose

Coding agent sessions have no memory. Without a state document, the next agent
session must re-read the full task history, may repeat completed work, and will
not know about decisions made mid-session that aren't in the plan.

`session_state.md` is the bridge between sessions. Keep it current.

---

## Output Location

`docs/session_state.md`

This file is always **overwritten** — it reflects the current state, not history.
If you want a log of completed phases, that is tracked via `[x]` in `tasks.md`.

---

## When to Produce/Update This File

* At every phase checkpoint — even if continuing immediately.
* When a session is ending mid-phase (any stopping point).
* When switching between agent models or tools (e.g., Codex → Claude Code).
* When a blocker is encountered that requires human input.

---

## Required Format

```markdown
# Session State
**Last updated:** YYYY-MM-DD
**Agent:** <model or tool used — e.g., Codex CLI, Claude Code>

## Feature Being Built
**Name:** <feature name>
**Spec:** docs/specs/<NNN>_<feature>.md
**Plan:** docs/plans/<NNN>_<feature>.md
**Tasks:** docs/tasks/<NNN>_<feature>.md

---

## Current Status
**Phase:** N of M — <current phase name>
**Phase status:** In Progress | Checkpoint Passed | Blocked

### Completed Tasks
- [x] Task 1.1 — Created `module/schemas/record.py` with `Record` dataclass
- [x] Task 1.2 — Created `module/schemas/config.py` with `PipelineConfig`
- [x] **Checkpoint 1 PASSED** — all schema imports clean, pytest test_schemas.py 3/3

### Next Task
- [ ] Task 2.1 — Add `load_inputs(config: PipelineConfig) -> list[Record]`
  to `module/core/loader.py`
  - (copy exact task description from tasks.md here)

---

## Current Codebase State

| File | Status | Notes |
|---|---|---|
| module/schemas/record.py | ✓ Created | Record dataclass, validate_record() |
| module/schemas/config.py | ✓ Created | PipelineConfig dataclass |
| module/core/loader.py | ⚠ Partial | File exists, function stub only |
| tests/test_schemas.py | ✓ Created | 3 tests, all passing |

---

## Decisions Made This Session

Any decision not in the plan that affects future tasks. Future agents must know these.

- Chose `dataclass` over `Pydantic` for `Record` because X.
- `validate_record()` returns `bool` not raises — affects how processor handles it.
- Skipped Task 1.2 parallel run because schema files shared a utility function.

---

## Blockers / Open Questions

If none: write "None — proceed to next task."

If blocked:
- **Blocker:** `_read_file()` returns bytes not str on Windows — affects loader implementation
- **Needs:** Human decision on encoding handling before Task 2.1 can complete
- **Do not proceed** past Task 2.1 until resolved

---

## How to Resume

1. Read `docs/tasks/<NNN>.md` — understand the full task list
2. Read this file — understand current state and decisions
3. Run this command to verify codebase is in expected state:
   `pytest tests/test_schemas.py -v`
   Expected: 3 passed, 0 failed
4. Start with: **Task 2.1** as described in tasks.md
5. If resuming mid-task (partial implementation above):
   `<describe exact state of the partial file and what remains>`
```

---

## Rules

1. This file is always overwritten — not appended. It reflects now, not history.
2. The "Next Task" section must contain the exact text from `tasks.md`.
   Do not paraphrase — the next agent must be able to match it precisely.
3. The "Codebase State" table must reflect actual disk state, not intended state.
4. Every decision in "Decisions Made" must include the reason — not just what was decided.
5. The "How to Resume" section must include a runnable verification command.
   If no test exists yet, provide a python import check or smoke command.
6. If there is a blocker, explicitly state "Do not proceed past Task X.Y until resolved."

---

## Checklist

- [ ] `session_state.md` has been written or updated.
- [ ] Current phase and status are accurate.
- [ ] Completed tasks are listed with actual outcomes (not planned outcomes).
- [ ] Next task text is copied exactly from `tasks.md`.
- [ ] Codebase state reflects actual disk state.
- [ ] Decisions not in the plan are documented with reasons.
- [ ] Resume verification command is runnable and correct.
- [ ] Blockers are explicitly called out (or "None" stated).

---

## Related Skills

* `SKILL: verify-checkpoint` — run before this at the end of a phase
* `SKILL: decompose-tasks` — the tasks.md this file references
* `SKILL: implement-feature` — the outer workflow that calls this
