# MICROTASK_SPEC — TASK-B001

## Task ID
TASK-B001

## Title
Update PLAN.md to mark completed tasks and correct test count

## Milestone served
1 — System inspectable

## Skill to apply
None (documentation edit only)

## Files to read before starting

1. `docs/01_status/MASTER_STATE.md` — verified current state (122 passed, 3 skipped)
2. `docs/07_agent_rules/SMALL_MODEL_GUIDE.md` — execution rules
3. `docs/06_plans/SPRINT_CURRENT.md` — confirms B001 is the next task
4. `PLAN.md` — the file to modify

## Verification: is this already done?

Run:
```bash
grep -n "passing\|125\|118\|complete\|done" PLAN.md | head -20
```

If the output shows test count is already 122 and completed items are marked, this task is already done — mark it complete and move to B002.

## Files to modify

- `PLAN.md` (root-level)

## Exact work

1. Open `PLAN.md`
2. Find every reference to test counts (e.g. "85 passing", "125 tests", "50 tests", "118 tests")
3. Update all counts to: **122 passed, 3 skipped**
4. Find the task list — mark as complete any tasks whose implementation is confirmed in `docs/01_status/MASTER_STATE.md`:
   - A001 (gitignore), A002 (pika), A003 (temp files), A004 (financial_env)
   - D001 (retry-failed crash), D002 (logging timestamps)
   - E001–E007 (all observability tasks)
   - K004 (VLM wired), L001 (raw retention), N003 (parse_nav_html)
   - P001 (portfolio fix), P004 (portfolio CSV)
   - R001–R004 (fixture e2e tests), S001–S002 (smoke tests)
5. Do not add new content; do not rewrite structure

## Acceptance criteria

- No stale test counts remain in PLAN.md
- Confirmed-done tasks are marked `[x]` or `Status: complete`
- File still parses as valid markdown

## Test command

```bash
grep -n "85 pass\|50 pass\|118 pass\|21 agent\|does NOT insert\|never called" PLAN.md
# Should return no matches

grep -n "122\|complete\|done" PLAN.md | head -10
# Should show updated count and completed markers
```

## Do not do

- Rewrite PLAN.md from scratch
- Mark tasks complete that are NOT in MASTER_STATE.md "Completed" section
- Modify plans/ directory files or docs/ files in this task
- Add new tasks or sections

## On completion

1. Run the test command — confirm zero stale matches
2. Run `./financial_env/bin/python -m pytest tests/ -q` — must still show 122 passed, 3 skipped
3. Update `docs/06_plans/SPRINT_CURRENT.md` — move B001 to "Recently Completed"
4. Apply `docs/07_agent_rules/skills/session_handoff.md` — update `docs/01_status/session_state.md`
5. Next task: **TASK-B002** — `docs/06_plans/active/BATCH_B_docs.md`
