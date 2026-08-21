# Refactor Candidate: agent/runner.py

_Created: 2026-06-26. Per CLAUDE_CODE_MASTER_BRIEF.md Part 2A._
_Status update 2026-06-29: resolved. This document is historical and should not be executed._

---

## Violation

Resolved by extracting upsert logic to `mutual_fund_ingestion/agent/upserts.py` and artifact processing to `mutual_fund_ingestion/agent/artifact_processor.py`.

Original issue: `agent/runner.py` was 821 lines and mixed Layer 3 (orchestration) with Layer 4 (core data logic).

### Embedded Layer 4 logic (should be in separate module):

| Method | Lines | Should move to |
|---|---|---|
| `_download_and_process_artifact()` | ~371–531 | `agent/artifact_processor.py` (Layer 4) |
| `_upsert_canonical()` | ~532–543 | `agent/upserts.py` (Layer 4) |
| `_upsert_nav_history()` | ~544–587 | `agent/upserts.py` |
| `_upsert_amcs()` | ~588–613 | `agent/upserts.py` |
| `_upsert_schemes()` | ~614–657 | `agent/upserts.py` |
| `_upsert_portfolio()` | ~658–773 | `agent/upserts.py` |
| `_write_validation_result()` | ~774–792 | `agent/upserts.py` |

### What should remain in runner.py:

- `__init__()` — setup and DB connection
- `run()` — high-level pipeline orchestration (calls other modules)
- `_add_retry_task()`, `_commit_batch()`, `_get_task_domain()` — thin helpers

### Proposed new files:

| File | Layer | Contents |
|---|---|---|
| `agent/upserts.py` | 4 | All `_upsert_*` methods + `_write_validation_result` |
| `agent/artifact_processor.py` | 4 | `_download_and_process_artifact` |

---

## Scope Estimate

- ~4 hours to extract and rewire
- ~300 lines move from runner.py to new files
- runner.py shrinks from 821 → ~300 lines (within limit)
- All 122 tests must pass after refactor (no behavior change)

---

## Gate

This refactor is complete and no longer gates Phase 2 or story notebook work.

**Do not execute this document as a current task.**

Reason: Phase 2 will add discovery-from-profiles orchestration to runner.py. If runner.py already violates layer separation, Phase 2 will make it significantly worse and harder to refactor later.

---

## How to Execute

1. Create `agent/upserts.py` with extracted upsert functions (accept `session` as parameter)
2. Create `agent/artifact_processor.py` with extracted download+process logic
3. Update `runner.py` to import and call these modules
4. Run `./financial_env/bin/python -m pytest tests/ -q` — all 122 must pass
5. Update `docs/02_architecture/codebase_map.md` to add the two new files
6. Update `docs/01_status/MASTER_STATE.md` — remove violation entry
