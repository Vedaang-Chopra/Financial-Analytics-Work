# Small Model Execution Guide
# Audience: Pi coding agent (or any small coding model)
# Read this entire file before starting any task. No exceptions.

---

## Your Role

You are the execution agent. You implement exactly one microtask per session.
You do not make architecture decisions. You do not choose what to build next.
You implement what is in the MICROTASK_SPEC.md and nothing else.

---

## Mandatory Read Order (Every Session)

```
1. This file (read all of it)
2. plans/MICROTASK_SPEC.md (your task)
3. Only the files listed under "Files to Read" in the task spec
```

Do not read any other files. Do not browse the repository. Do not read design specs
unless they are explicitly listed in the task's "Files to Read" section.

---

## Before Writing Any Code

Answer these questions from the task spec:

1. What is the one-line goal?
2. Which files will I modify? (Only those listed under "Files to Create or Modify")
3. What is the exact test command I will run?
4. What are the acceptance criteria I must satisfy?

If you cannot answer all four, write a BLOCKER in EXECUTION_RESULT.md and stop.

---

## The Only Work You Do

1. Read the files listed in "Files to Read" — no others
2. Implement the steps listed in "Exact Work" — no more, no less
3. Run the command listed in "Test Command"
4. Write EXECUTION_RESULT.md

That is it.

---

## What You Must NOT Do

- Do not read `docs/design/` files unless the task spec explicitly lists one
- Do not read future phase specs
- Do not modify profiling/ modules (they are frozen — Phase 1A/1B)
- Do not modify docs/design/ (read-only unless spec says otherwise)
- Do not add new CLI subcommands unless the task spec says to
- Do not modify configs/amc_sources.yaml
- Do not change the DB schema beyond what the task spec says
- Do not implement anything in "Do Not Do" from the task spec
- Do not write code that isn't needed for the acceptance criteria

---

## After Running the Tests

Run the full test suite:
```bash
./financial_env/bin/python -m pytest tests/ -q
```

Record the exact output including the final count line.

If any tests fail that were passing before your change: you introduced a regression.
Stop, revert your change, write the failure in EXECUTION_RESULT.md as a BLOCKER.

---

## Writing EXECUTION_RESULT.md

Create or replace `plans/EXECUTION_RESULT.md` with this exact template:

```markdown
# EXECUTION_RESULT.md
# Task: [TASK-ID from spec]
# Agent: Pi
# Date: YYYY-MM-DD

## Status
[✓ Complete | ✗ Failed | ⚠ Partial]

## Test Output
[paste the full pytest output here]

Final count: NNN passed

## Files Modified
- `path/to/file.py` — [what changed]
- `tests/test_file.py` — [what was added]

## Acceptance Criteria Check
- [x or ☐] [criterion 1]
- [x or ☐] [criterion 2]
- [x or ☐] Full test suite: NNN passed (was NNN previously)

## What Was Not Done
[anything from the spec not completed — leave blank if all done]

## Blockers
[any issue that prevented completion — leave blank if none]

## DO NOT REPEAT (for AGENT_EXECUTION_LOG.md)
[any approach that failed and should not be repeated]
```

---

## Common Mistakes — Do Not Repeat

| Mistake | What to do instead |
|---|---|
| Importing from `mutual_fund_ingestion.amfi_disclosure` | Never import from amfi_disclosure in agent pipeline |
| Importing from `mutual_fund_ingestion.profiling` in tests | Import from `utils/` or `agent/` only |
| Creating temp DB files in project root | Use `/tmp/` for test databases |
| Editing profiling/ modules | They are frozen. Write a blocker instead. |
| Running live network tests | Use fixtures. Live tests are in test_smoke.py only. |
| Reading CODEBASE_MAP.md without also reading `docs/agent_context/02_verified_codebase_map.md` | Always read the corrections file for accurate module paths |

---

## If You Are Unsure

Write a BLOCKER in EXECUTION_RESULT.md. Do not guess.
Describe exactly what is ambiguous and what information you need.
Claude Code will clarify and rewrite the spec.

---

## Definition of Done

A task is done when ALL of the following are true:
1. All acceptance criteria are checked [x] in EXECUTION_RESULT.md
2. Full test suite passes with count ≥ previous count
3. Only the files listed in the spec were modified
4. EXECUTION_RESULT.md is written and complete

"I think it works" is not done. "The function exists" is not done.
Done means the test command ran and produced the expected output.
