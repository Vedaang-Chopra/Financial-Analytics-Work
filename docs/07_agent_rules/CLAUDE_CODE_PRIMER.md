# CLAUDE_CODE_PRIMER.md
# Drop this in the repository root. Claude Code reads this at the start of every session.
# It replaces the scattered context docs. Single source of truth for session orientation.

---

## What This System Is

Indian mutual fund disclosure ingestion and analytics pipeline.

Collects public investor documents from AMC/provider websites → parses them → validates →
loads into PostgreSQL → (eventually) analytics over holdings, overlap, sector allocation.

Not investment advice. Not a chatbot. A reproducible financial data pipeline.

---

## Repository Map (Start Here)

```
AGENTS.md                          ← Non-negotiable governance. Read before every change.
CLAUDE.md                          ← Claude Code operating rules.
configs/amc_sources.yaml           ← 53 AMC seed URLs. Do not modify structure.

docs/agent_context/                ← PRIMARY CONTEXT (authoritative, 2026-06-23)
  README.md                        ← Which file to read by session type
  01_current_system_state.md       ← Verified state (125 tests, done/partial/missing)
  02_verified_codebase_map.md      ← Module ownership with corrections
  05_next_execution_roadmap.md     ← What comes next and in what order

docs/implemented/                  ← Frozen: design specs for complete phases
docs/planned/                      ← Not started: specs for future phases
docs/historical/                   ← Archive: old docs, do not act on

plans/SPRINT_CURRENT.md            ← What Pi is executing RIGHT NOW
plans/GOAL_ALIGNMENT.md            ← High-level goals that every task must serve
plans/active/                      ← Current sprint batch plans
plans/SMALL_MODEL_EXECUTION_GUIDE.md ← Rules for Pi coding agent

notebooks/mutual_fund_ingestion/   ← Phase review notebooks (one per phase)
  00_system_checkpoint.ipynb       ← Run this to see overall system health
  02_agent_pipeline_inspection.ipynb ← Run this to inspect a pipeline run
```

---

## Phase Status (Current)

| Phase | What it does | Status |
|---|---|---|
| Phase 1A | Source registry bootstrap | ✅ Complete — frozen |
| Phase 1B | Provider website profiling | ✅ Complete — frozen |
| Task-URL Agent | Core ingestion pipeline | ✅ Substantially complete |
| Test Coverage | Epics G–Q | ⚠️ In progress (125/145+ target) |
| Phase 2 | Document discovery from Phase 1 profiles | ❌ Not started |
| Phase 3+ | Classification, parsers, analytics | ❌ Not started |

---

## The Frozen Modules (Do Not Modify)

```
mutual_fund_ingestion/profiling/    ← Phase 1A/1B — frozen
mutual_fund_ingestion/amfi_disclosure/ ← Legacy prototype — do not import into agent pipeline
docs/design/                        ← Specs — read-only unless implementation diverges
```

---

## Strategy Order (Never Skip Ahead)

```
static_html → network_api → playwright → vlm_required → manual_review
```

---

## Data Flow (Never Bypass Staging)

```
raw file download → parser → staging_rows → validate → canonical tables
                                                    ↓ (on failure)
                                              quarantine_rows
```

---

## Session Type → Read This

**Planning session (Claude Code as architect):**
Read `docs/agent_context/04_authoritative_sources.md` for exact reading order.

**Execution session (writing code):**
1. `AGENTS.md`
2. `docs/agent_context/02_verified_codebase_map.md`
3. `plans/SPRINT_CURRENT.md` — find your task
4. `plans/SMALL_MODEL_EXECUTION_GUIDE.md` — your operating rules
5. Only the files listed in your task spec

**Debugging session:**
1. `docs/agent_context/01_current_system_state.md`
2. `docs/agent_context/02_verified_codebase_map.md`
3. The failing test file
4. The module under test

**Handoff / checkpoint session:**
1. Run `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb`
2. Fill in `docs/agent_context/08_session_handoff_template.md`
3. Save to `docs/session_state.md` (replace old content)

---

## What Claude Code Decides (Not Pi)

- Which task is next
- Whether Phase 2 gate is met
- Architecture or design changes
- Whether to add a new task to the micro plan
- Interpreting test failures as blockers or known gaps

## What Pi Decides (Not Claude Code)

- How to implement "Exact Work" within spec constraints
- Which lines to write
- When to write a BLOCKER in EXECUTION_RESULT.md

## What Needs Human Approval

- Changing the DB schema
- New CLI subcommands
- Modifying frozen modules
- Starting Phase 2 before gate criteria met
- Changing strategy hierarchy

---

## Phase 2 Gate (Do Not Start Until All Checked)

- [ ] Epic G (validation coverage) — all 6 tasks complete
- [ ] Epic H (discovery/relevance tests) — all 5 tasks complete
- [ ] Epic P (portfolio parser with real column fixture) — complete
- [ ] Epic N (NAV HTML end-to-end test) — complete
- [ ] Total test count ≥ 145
- [ ] `docs/planned/phase_2_discovery/` read in full before any Phase 2 code

---

## Verified Working CLI

```bash
./financial_env/bin/python -m pytest tests/ -q   # 125 passing
python -m mutual_fund_ingestion bootstrap-sources --dry-run
python -m mutual_fund_ingestion profile-providers --limit 3
python -m mutual_fund_ingestion init-db --database-url sqlite:///test.db
python -m mutual_fund_ingestion run-agent --task-url URL --database-url sqlite:///test.db
python -m mutual_fund_ingestion inspect-run --database-url sqlite:///test.db --run-id RUN_ID
```

---

## Conflicts: What To Trust

If any document conflicts with live code + test output, trust the live code.
If any document conflicts with `docs/agent_context/`, trust `docs/agent_context/` (audited 2026-06-23).
Do not trust test counts other than 125 (verified 2026-06-23).
Do not trust claims that VLM is unwired (it is wired — runner.py L179–195).
Do not trust claims that portfolio.py column mapping is broken (it is fixed).
Do not trust test counts other than 122 passed + 3 skipped (verified 2026-06-27).

---

## Skills to Apply

Before writing each MICROTASK_SPEC, check which skills apply:

| Situation | Skill file |
|---|---|
| Writing any task spec | `docs/07_agent_rules/task_generation_rules.md` |
| Task involves a new notebook | `docs/07_agent_rules/skills/write_notebook.md` |
| Task involves a new module or file in agent/ | `docs/07_agent_rules/skills/design_layered_module.md` |
| Session ending / handoff | `docs/07_agent_rules/skills/session_handoff.md` |

**Mandatory**: READ the relevant skill file before writing the spec. Do not write from memory.
