# Pi Loop Rules — Operating Manual
# Audience: Pi coding agent (and any small model executing tasks in this project)
# Read EVERY line of this file before touching anything.

---

## 1. Session Start Ritual

Every Pi session starts by reading these files in order. No exceptions.

```
1. docs/07_agent_rules/PI_LOOP_RULES.md         (this file)
2. docs/01_status/MASTER_STATE.md               (current system state + DATABASE_URL)
3. docs/06_plans/CHECKPOINT_PLAN.md             (active checkpoint + task list)
4. docs/06_plans/MICROTASK_SPEC.md              (exact task you are about to run)
5. docs/01_status/AGENT_EXECUTION_LOG.md        (what failed before — do not repeat)
```

Only after reading all 5 may you look at any source code file.

Do NOT read:
- future checkpoint tasks (only your current task)
- docs/09_historical/ (archived, read-only)
- Any file not listed in your MICROTASK_SPEC's "Files to Read" section

---

## 2. Context Budget Rule

You have a limited context window. When your context is 70–80% full:

1. STOP the current task immediately — do not continue writing code.
2. Write docs/06_plans/EXECUTION_RESULT.md with Status: ⚠ Partial.
3. In the "What Was Not Done" section, list EXACTLY where you stopped (file name, function name, line number if known).
4. In the "Session Handoff" section, write the exact first step for the next session to resume.
5. End the session.

The next session will read EXECUTION_RESULT.md under "Session Handoff" before reading MICROTASK_SPEC.

**How to detect 70–80%**: If you notice yourself re-deriving context you already established earlier in the session, or if tool responses feel very slow, you are likely near the limit. When in doubt, write the partial result and stop — a clean handoff is better than a corrupted completion.

---

## 3. Rate Limiting Rules

When making HTTP calls to external endpoints (AMC websites, AMFI, SEBI):

- Minimum 2 seconds sleep between any two HTTP requests to the same domain.
- If a 429 (rate limited) response is received: sleep 60 seconds, retry once.
- If still rate-limited after one retry: skip the URL, record it in EXECUTION_RESULT.md under "Blockers".
- Never retry more than once per URL per session.
- Log every HTTP call before making it: `LOGGER.info("GET %s", url)`.
- The pytest suite uses mock HTTP — no sleep needed during tests.

---

## 4. Task Execution Pattern

One session = one microtask. Follow this loop exactly:

```
1. READ the 5 mandatory files (§1)
2. READ only the source files listed in MICROTASK_SPEC "Files to Read"
3. IMPLEMENT exactly what "Exact Work" says — no more, no less
4. RUN: ./financial_env/bin/python -m pytest tests/ -q --tb=no
5. If any previously-passing test now fails: REVERT the change, write BLOCKER in EXECUTION_RESULT.md
6. If all tests pass (or count is higher): write EXECUTION_RESULT.md with Status: ✓ Complete
7. Update docs/01_status/AGENT_EXECUTION_LOG.md with what you did
```

Do NOT:
- Implement the next task in the same session
- Refactor code that is not in scope
- Add logging beyond what the task requires
- Read files not listed in the spec

---

## 5. EXECUTION_RESULT.md Format

Always write to: `docs/06_plans/EXECUTION_RESULT.md` (overwrite each time).

```markdown
# EXECUTION_RESULT.md
# Task: [TASK-ID from MICROTASK_SPEC]
# Agent: Pi
# Model: [model name/version]
# Date: YYYY-MM-DD

## Status
[✓ Complete | ✗ Failed | ⚠ Partial]

## Test Output
[paste full pytest -q output here — do not truncate]

Final count: NNN passed

## Files Modified
- `path/to/file.py` — [one sentence: what changed]
- `tests/test_file.py` — [what was added]

## Acceptance Criteria Check
- [x or ☐] [criterion 1]
- [x or ☐] [criterion 2]
- [x or ☐] Full suite: NNN passed (was NNN previously)

## What Was Not Done
[Anything from the spec not completed. Leave blank if fully done.]

## Session Handoff
[Only fill if Status is ⚠ Partial. Write the exact first step for the next session:
"Resume at: create function X in file Y, starting from line Z."]

## Blockers
[Any issue that prevented completion. Leave blank if none.
For rate limiting: list the URL and the HTTP status code received.
For ambiguity: describe exactly what is unclear.]

## DO NOT REPEAT
[Any approach that failed — be specific. Include error messages.]
```

---

## 6. Exit Condition Checking

A checkpoint is done when its "Exit Condition" command (from CHECKPOINT_PLAN.md) produces the expected output.

Rules:
- Run the exact command from CHECKPOINT_PLAN.md — do not substitute.
- Paste the actual output into EXECUTION_RESULT.md under "Test Output".
- Do not declare a checkpoint done based on your own judgment.
- If the exit condition is a file existence check (`ls`), paste the ls output.
- If the exit condition is a test count, paste the full pytest final line.
- A checkpoint is only done when BOTH the test count AND the file existence checks pass.

---

## 7. Circuit Breaker

If 3 consecutive sessions produce no progress (same task, Status: ✗ Failed or ⚠ Partial each time):

1. Write docs/06_plans/ALERT.md with:
   - Task ID that is stuck
   - What was tried (all 3 approaches)
   - What error or blocker appeared each time
   - Recommended action for the human developer
2. Write EXECUTION_RESULT.md with Status: ✗ Failed and Blocker: "CIRCUIT BREAKER — 3 failed attempts, see ALERT.md"
3. Stop. Do not attempt the task again.

The human developer reads ALERT.md and either modifies the spec or provides a different approach.

---

## 8. Session Handoff

Before ending any session, even if all tasks are complete:

1. Write or update EXECUTION_RESULT.md (§5 format).
2. Write a one-line update to docs/01_status/AGENT_EXECUTION_LOG.md:
   ```
   [DATE] [TASK-ID] [✓/✗/⚠] [one sentence: what was done or failed]
   ```
3. If the checkpoint exit condition passed: update docs/06_plans/CHECKPOINT_PLAN.md to mark the checkpoint done.
4. If the checkpoint exit condition passed: set up MICROTASK_SPEC.md for the next checkpoint's first task.

Never end a session without writing EXECUTION_RESULT.md.

---

## 9. What Pi Must NEVER Do

- Modify anything in `mutual_fund_ingestion/profiling/` — it is frozen (Phase 1A/1B complete).
- Modify anything in `mutual_fund_ingestion/amfi_disclosure/` — it is an archived prototype.
- Import from `amfi_disclosure` in any agent pipeline code.
- Import from `legacy_experiments/` (if that directory exists).
- Add new CLI subcommands not in the spec.
- Add new SQLAlchemy table models without explicit human approval.
- Modify `configs/amc_sources.yaml`.
- Write output files (downloads, CSVs, reports) to source directories — use `data/` or `/tmp/`.
- Mark a task `[x]` complete before its acceptance criteria check passes.
- Repeat any approach listed as FAILED in `docs/01_status/AGENT_EXECUTION_LOG.md`.
- Push to git (git push is a hard stop — always confirm with human).

---

## 10. Handling Open Model Failures

When the model (minimax, kimi, nemotron, etc.) fails to follow a complex instruction:

- Simplify the instruction: break one multi-step task into two single-step tasks.
- Do NOT reprompt with the same complex instruction — simpler is better.
- Do NOT use placeholders like "# TODO: implement this" in production code.
- If a code generation fails to compile or import: write the exact error in EXECUTION_RESULT.md Blockers.
- If the model cannot find a function in the files it read: add the exact file path and function name to the spec.
- After any model failure that produces wrong code: run the test suite before writing EXECUTION_RESULT.md, regardless of whether you think the code is correct.

---

## Database Connection

The project database (vlmrouter-postgres) runs locally at:
```
Host: localhost
Port: 5432
Type: pgvector/PostgreSQL 18
```

Check MASTER_STATE.md under "Database" for the verified DATABASE_URL.
If DATABASE_URL is not yet documented in MASTER_STATE.md, the current task is TASK-C002 (see CHECKPOINT_PLAN.md CP0).

All CLI commands that need the DB require --database-url:
```bash
./financial_env/bin/python -m mutual_fund_ingestion init-db --database-url $DATABASE_URL
./financial_env/bin/python -m mutual_fund_ingestion run-agent --task-url URL --database-url $DATABASE_URL
```

Tests use SQLite (no DATABASE_URL needed for pytest).

---

## Definition of Done

A task is done when ALL of the following are true:
1. All acceptance criteria are marked [x] in EXECUTION_RESULT.md.
2. `./financial_env/bin/python -m pytest tests/ -q --tb=no` passes with count ≥ previous count.
3. Only the files listed in MICROTASK_SPEC "Files to Create or Modify" were modified.
4. EXECUTION_RESULT.md is written and complete.
5. AGENT_EXECUTION_LOG.md has a new entry.

"I think it works" is not done. "The function exists" is not done.
Done means the test command ran and produced the expected output, pasted into EXECUTION_RESULT.md.
