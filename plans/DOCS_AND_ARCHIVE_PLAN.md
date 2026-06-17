# Documentation and Archive Plan

_Plan only — no files are moved, deleted, or changed by this document._

---

## 1. Authoritative Documents (Never Delete)

These are the ground truth for all implementation decisions.

| File | Why authoritative |
|---|---|
| `AGENTS.md` | 18 mandatory governance rules for all AI agents. All coding agents must read this before any change. |
| `docs/ai_context/CODEBASE_MAP.md` | Module ownership, layer assignments, public APIs. Single source of truth for "where does X live?" |
| `docs/design/task_url_agent_design_pack/` | 14 design specs + implementation report. Behavioral contracts for the entire agent pipeline. |
| `plans/TECHNICAL_SPEC_AGENT_TARGET_STATE.md` | Concise target-state spec for the agent. Use this when a smaller model needs system context. |
| `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md` | Full audit of what is implemented, partial, and broken. |
| `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` | The executable task plan. |

---

## 2. Documents That Are Stale (Update, Do Not Delete)

These documents contain accurate historical content but have sections that no longer match the code.

| File | What is stale | When to update |
|---|---|---|
| `PLAN.md` | Tasks 1 and 2 are marked as pending but are already complete. Section 1.5 incorrectly states "runner does not write to DB". | TASK-B001 |
| `plans/task_url_ingestion_agent.md` | Claims 50 passing tests; actual count is 85. Gap list is incomplete (does not mention portfolio column mapping bug, VLM not invoked, retry-failed crash). | TASK-B002 |
| `CHATGPT_PROJECT_MEMORY.md` | Current Status section reflects pre-audit state. Does not mention actual bugs found. | TASK-B003 |
| `docs/ai_context/CODEBASE_MAP.md` | Does not classify `amfi_disclosure/` as legacy. Does not note portfolio.py column mapping bug. | TASK-B004 |
| `README.md` | Test count says 50; should say 85. | TASK-B006 |

**Update rule:** When a task from the micro-plan completes a fix described as stale above, update the corresponding doc in the same task or as a follow-up marked TASK-Bxxx.

---

## 3. Documents to Keep as Historical Memory

These documents capture design decisions, evolution, and context that should not be lost even when the content is superseded.

| File | Historical value |
|---|---|
| `docs/design/phase_1/` | Captures Phase 1A/1B design decisions. Explains why the provider-first strategy was chosen. |
| `docs/design/phase_2/` | Phase 2 design. Not yet implemented. Keep as the authoritative spec for Phase 2 work. |
| `docs/design/mutual_fund_project_memory_pack/` | 8 continuity files capturing the project's evolution. AI agents should read these when resuming after long gaps. |
| `CHATGPT_PROJECT_MEMORY.md` | Even after updates, keep prior sections intact (add a new "Updated: YYYY-MM-DD" block rather than overwriting). |
| `plans/task_url_ingestion_detailed_implementation_plan.md` | Historical build plan. Explains the original task decomposition. |

---

## 4. Documents That May Be Archived Later (Not Now)

These will become redundant once the system is fully implemented but should not be deleted until that point.

| File | Archive condition |
|---|---|
| `PLAN.md` | Archive after all 6 tasks in it are complete and incorporated into the micro-plan |
| `plans/task_url_ingestion_agent.md` | Archive after CURRENT_CODEBASE_STATUS document supersedes its content |
| Individual design specs in `task_url_agent_design_pack/` | Archive per-spec when corresponding Epic is fully tested and verified |

**Archive process:** Move to `docs/archive/YYYY-MM-DD/<filename>` with a one-line note at the top explaining why it was archived. Do not delete.

**No file should be archived without explicit user approval.**

---

## 5. The `amfi_disclosure/` Prototype

`amfi_disclosure/` is a standalone proof-of-concept for AMFI portfolio disclosure crawling. It is fully functional but isolated from the main agent pipeline.

**Current status:** Not referenced by `mutual_fund_ingestion/` in any import. 11 tests in `test_amfi_disclosure.py` cover it.

**Recommended disposition:**
1. Add `amfi_disclosure/README.md` (TASK-C001) marking it as "Phase 0 proof-of-concept — isolated prototype, not part of main agent pipeline."
2. Do not integrate it into the agent (it solves a subset of what the agent already does).
3. Do not delete it — it contains working Playwright + HTTP patterns that may be useful as reference.
4. Consider archiving to `docs/archive/prototypes/amfi_disclosure/` once Phase P (portfolio ingestion) is complete and verified.

---

## 6. The `Code Base/` Directory

`Code Base/` contains early dataset collection experiments (pandas-based NAV scripts, schema definitions). It predates the current architecture.

**Current status:** Not referenced anywhere. Not tested. Not gitignored.

**Recommended disposition:**
1. Add a `Code Base/README.md` (TASK-C002) marking it as "legacy experiments — superseded by mutual_fund_ingestion/".
2. Add `Code Base/` to `.gitignore` or move its contents to `docs/archive/legacy_code_base/`.
3. Do not delete without explicit user approval.

---

## 7. Root-Level Generated `.db` Files

`test.db`, `test2.db`, `test3.db`, `final_test.db`, `test_mock.db` are SQLite databases left over from development and test runs.

**Recommended disposition:**
1. Add `*.db` to `.gitignore` immediately (TASK-A001).
2. Do not commit these files.
3. Do not delete manually — they will stop appearing in `git status` once gitignored.
4. Test infrastructure should use `tempfile.mkstemp(suffix=".db")` to ensure temp files go to `/tmp`, not the project root. Investigate and fix the test that creates them in the project root.

---

## 8. Old Phase-Specific Plans

`plans/task_url_ingestion_detailed_implementation_plan.md` is a 360-line build plan from before implementation began. Most of it has been executed.

**Recommended disposition:**
1. Keep as-is for now — it explains the original build rationale.
2. After Epic T (final docs and handoff) is complete, move it to `docs/archive/plans/`.

---

## 9. Keeping `CODEBASE_MAP.md` Current

**Rule:** Every time a new module, class, or public function is added, `CODEBASE_MAP.md` must be updated in the same task.

**Update procedure:**
1. Add the new file under the correct layer heading.
2. List public entry points (functions/classes exposed via `__init__.py` or direct import).
3. Note which module owns the behavior (to prevent duplication).
4. Run `grep -r "from mutual_fund_ingestion" tests/` to verify imports are consistent.

**Tasks that must update CODEBASE_MAP:**
- Any Epic G task that adds a new validation function
- Any Epic N–Q task that adds a new parser
- Any Epic J task that adds network capture logic
- Epic T001 (final docs update) must verify CODEBASE_MAP is fully current

---

## 10. Keeping `README.md` Aligned with CLI

`README.md` documents CLI commands with flags. After every task that changes CLI behavior, update README.md in the same task.

**Sections to keep current:**
- Phase 1A/1B commands (should remain stable)
- `run-agent` flag list (any new flag added in Epic D must appear here)
- `init-db` usage
- `inspect-run` usage
- `retry-failed` usage (update after TASK-D001 fixes the `--run-id` behavior)
- Test command and expected count (update after each Epic that adds tests)

---

## 11. What Must Never Be Deleted Without Explicit Approval

| File/Directory | Reason |
|---|---|
| `AGENTS.md` | Governance rules — deleting would remove all safety constraints on AI agents |
| `docs/design/task_url_agent_design_pack/` | Behavioral contracts — needed to verify implementation is correct |
| `configs/amc_sources.yaml` | 53 manually curated AMC entries — would take significant effort to reconstruct |
| `docs/ai_context/CODEBASE_MAP.md` | Module ownership map — prevents duplication and import confusion |
| `tests/` | All test files — deleting reduces system confidence |
| `data/raw/mutual_funds/` | Provider profiles and source registry — real crawl output, not regenerated automatically |
| Any file under `docs/design/` | Design decisions and behavioral specs |
