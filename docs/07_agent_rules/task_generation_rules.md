# Task Generation Rules

Claude Code must apply these rules when writing any MICROTASK_SPEC.md for Pi.

---

## Mandatory references per task type

| Task touches | Must reference skill | Canonical source |
|---|---|---|
| New notebook | `docs/07_agent_rules/skills/write_notebook.md` | `~/agent-governance/skills/core/design-feature-notebook.md` |
| New module or new file in agent/ | `docs/07_agent_rules/skills/design_layered_module.md` | `~/agent-governance/skills/core/design-layered-module.md` |
| Session end / handoff | `docs/07_agent_rules/skills/session_handoff.md` | `~/agent-governance/skills/core/handoff-coding-agent.md` |
| Multiple files in same module | `docs/07_agent_rules/skills/design_layered_module.md` | `~/agent-governance/skills/core/design-layered-module.md` |
| Writing tests | `~/agent-governance/skills/core/write-tests.md` | — |
| Implementing a feature task | `~/agent-governance/skills/core/implement-feature.md` | — |
| End of phase checkpoint | `~/agent-governance/skills/core/verify-checkpoint.md` | — |
| Adding logging/observability | `~/agent-governance/skills/core/add-observability.md` | — |

---

## Mandatory checks before writing a task spec

1. Does this task serve a milestone in `docs/06_plans/GOAL_ALIGNMENT.md`?
2. Does Pi have all the context it needs in "Files to Read"?
3. Is the task ≤3 files? If not, split it.
4. Does it have a single verifiable test command?
5. Does it have clear acceptance criteria?
6. Have you listed what NOT to do?
7. Does it reference the correct skill if applicable?
8. Is the task already done? (check `docs/01_status/MASTER_STATE.md` first)

---

## Required MICROTASK_SPEC.md format

```markdown
# MICROTASK_SPEC — TASK-XXX

## Task ID
TASK-XXX

## Title
[Short descriptive title]

## Milestone served
[N — from GOAL_ALIGNMENT.md]

## Skill to apply
[path to skill file, or "None"]

## Files to read before starting
1. `docs/01_status/MASTER_STATE.md`
2. `docs/07_agent_rules/SMALL_MODEL_GUIDE.md`
3. [specific files for this task]

## Files to modify
- `path/to/file.py` — what to change

## Exact work
[numbered steps, specific enough to execute without clarification]

## Acceptance criteria
- [measurable outcomes]

## Test command
```bash
./financial_env/bin/python -m pytest [specific args] -v
```

## Do not do
- [explicit prohibitions]

## On completion
1. Run the test command — it must pass
2. Update `docs/06_plans/SPRINT_CURRENT.md` — mark task complete
3. Update `docs/01_status/MASTER_STATE.md` if needed
4. Apply session_handoff skill to update `docs/01_status/session_state.md`
```

---

## Anti-patterns Pi must not produce (check before accepting result)

- Production logic inside a notebook cell
- Importing from deep internal files (not from public interfaces)
- `runner.py` growing beyond its current 821 lines before the refactor
- Duplicate schema definitions
- New validators not wired into `validate_and_filter_records`
- Tests that pass via mocking the thing being tested
- Task marked complete without running the test command
- Modifying files in `profiling/` (frozen) or `amfi_disclosure/` (legacy)
