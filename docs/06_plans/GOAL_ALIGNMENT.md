# GOAL_ALIGNMENT.md
# Every micro-plan and every batch must serve at least one goal listed here.
# Claude Code uses this file to assess whether planned tasks are on track.
# Pi reads this to understand WHY the task matters.

---

## The Primary Goal

Build a reproducible, provider-first ingestion pipeline that:
1. Discovers and downloads public Indian AMC disclosure documents
2. Parses them into structured records (holdings, NAV, sector allocation)
3. Validates the records and loads trusted data into PostgreSQL
4. Eventually supports analytics over: which stocks are held by most funds,
   accumulation/reduction signals, fund overlap, sector rotation

This is a financial transparency and research system. Not investment advice.

---

## Milestone Map (What "Done" Looks Like)

```
MILESTONE 1 — System is testable (CURRENT FOCUS)
  The user can run a story notebook series and see source discovery, provider
  profiling, discovery, raw artifact download, parsing, validation, quarantine,
  and canonical DB persistence.
  Current baseline: 145 passed, 3 skipped.

MILESTONE 2 — Pipeline is fully tested
  ≥145 tests passing.
  All parsers tested with real fixture data.
  All validators tested with valid + invalid input.
  No parser path that silently drops records.

MILESTONE 3 — Phase 2 produces real documents
  At least 3 AMC provider profiles traversed.
  At least 1 portfolio Excel downloaded with metadata sidecar.
  Phase 2 review notebook renders successfully.

MILESTONE 4 — Canonical tables populated with real data
  Real portfolio holdings from at least 2 AMCs in PostgreSQL.
  NAV history from at least 10 schemes.
  Validation results show <5% quarantine rate for known-good sources.

MILESTONE 5 — Analytics layer exists
  Can query: which stocks appear in most funds (top 10)
  Can query: month-over-month holding change for a stock
  Can query: fund overlap between 2 selected funds
```

---

## Sub-Goals in Priority Order

### SUB-GOAL 1: Make the system inspectable
**Why:** The user cannot evaluate progress without being able to see what the system has done.
**Done when:** The story notebook series is implemented and validated.
**Tasks that serve this:** `STORY-NB-*` notebook tasks, session_state.md updates.

### SUB-GOAL 2: Ensure the pipeline is verifiably correct
**Why:** Phase 2 will build on the agent pipeline. Silent bugs now become compounding failures later.
**Done when:** Milestone 2 complete.
**Tasks that serve this:** Epics G, H, I, J, K, L, M, N, O, P, Q.

### SUB-GOAL 3: Discover and download real AMC documents
**Why:** No real data = no real validation = no analytics.
**Done when:** Milestone 3 complete.
**Tasks that serve this:** Phase 2 implementation (not yet started).

### SUB-GOAL 4: Populate canonical tables with trusted data
**Why:** The analytics layer can only work with real validated data in PostgreSQL.
**Done when:** Milestone 4 complete.
**Tasks that serve this:** Phase 3+, validation expansion, canonical upsert coverage.

### SUB-GOAL 5: Enable analytics queries
**Why:** This is the long-term research value — fund overlap, accumulation signals, sector exposure.
**Done when:** Milestone 5 complete.
**Tasks that serve this:** Analytics agent (not yet spec'd).

---

## What Is NOT a Goal Right Now

Defer any task that serves only these:
- Frontend dashboard or UI
- Investment recommendations or buy/sell signals
- Real-time or streaming data
- Full PDF parsing for all document types
- Ingesting all 53 AMCs simultaneously (start with 3–5)
- Multi-region or non-Indian fund sources
- User authentication or access control

If a proposed task only serves the above, it goes to a parking lot — not the active plan.

---

## Plan Assessment Checklist

Before writing any batch plan or micro-task, Claude Code answers:

```
1. Which sub-goal does this task serve? (must be Sub-Goal 1–5)
2. Which milestone does it advance?
3. Is it blocked by another incomplete task? (if yes, list the dependency)
4. Is it too large? (if it touches more than 3 files or 2 modules, split it)
5. Does it produce a testable output? (test, artifact, or notebook cell)
6. Is it in the right batch? (active sprint vs. backlog)
```

If any question cannot be answered, the task is not ready to be assigned to Pi.

---

## Batch-to-Milestone Mapping

| Batch | Sub-Goal | Milestone |
|---|---|---|
| Batch B (docs) | Sub-Goal 1 | Milestone 1 |
| Batch E (validation) | Sub-Goal 2 | Milestone 2 |
| Batch F (discovery tests) | Sub-Goal 2 | Milestone 2 |
| Batch G (browser/VLM tests) | Sub-Goal 2 | Milestone 2 |
| Batch H-M (parser tests) | Sub-Goal 2 | Milestone 2 |
| Batch N (final handoff) | Sub-Goal 1 | Milestone 2 |
| Phase 2 tasks | Sub-Goal 3 | Milestone 3 |
| Phase 3+ tasks | Sub-Goal 4 | Milestone 4 |
| Analytics tasks | Sub-Goal 5 | Milestone 5 |

---

## Warning Signs (Task Is Off-Track)

A task is off-track if:
- It modifies `mutual_fund_ingestion/profiling/` without a documented reason
- It adds a new parser before real documents from Phase 2 exist to test against
- It adds database tables not in the 17-table schema without human approval
- It implements Phase 2 logic before the Phase 2 gate criteria are met
- It creates a new CLI subcommand not in the spec
- It touches `amfi_disclosure/` module
- It imports from `legacy_experiments/`

When Claude Code sees a task that hits any of these: flag to the user before executing.
