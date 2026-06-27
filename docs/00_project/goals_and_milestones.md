# Goals and Milestones

---

## Primary Goal

Reproducible provider-first ingestion of Indian mutual fund disclosures → PostgreSQL → analytics over fund holdings.

---

## Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | System is inspectable: notebooks run, 125+ tests passing | **CURRENT** |
| 2 | Pipeline fully tested: ≥145 tests, all parser paths verified | In progress |
| 3 | Phase 2 produces real documents: 3+ AMCs, 1+ Excel downloaded | Not started |
| 4 | Canonical tables populated with real data: 2+ AMCs in PostgreSQL | Not started |
| 5 | Analytics queries exist: fund overlap, accumulation signals, sector exposure | Not started |

---

## Not a Goal Now

- Frontend / dashboard
- Investment recommendations
- All-PDF parsing
- Analytics before real data exists (Milestone 4 must come first)
- Real-time data
- Phase 1.5 strategy resolution (only if many AMCs stuck at manual_review)

---

## Alignment Check

Before any new task, answer these:
1. Which milestone does this task advance?
2. Is it blocked by anything incomplete?
3. Does it touch ≤3 files? (if not, split it)
4. Does it produce a verifiable test output?
