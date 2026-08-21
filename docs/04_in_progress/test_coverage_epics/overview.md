# Test Coverage Epics — Overview

_Active. Updated as tasks complete. Target: ≥145 tests before Phase 2._

---

## Current Count

145 passed, 3 skipped (2026-06-29)

## Epic Status

| Epic | Name | Tasks | Done | Pending | Batch file |
|---|---|---|---|---|---|
| G | Validation coverage | 6 | 6 | 0 | `docs/06_plans/active/BATCH_E_validation.md` |
| H | Discovery / relevance | 5 | 5 | 0 | `docs/06_plans/active/BATCH_F_discovery.md` |
| I | Browser tests | 2 | 2 | 0 | `docs/06_plans/active/BATCH_G_browser_vlm.md` |
| J | Network / API discovery | 2 | 2 | 0 | `docs/06_plans/active/BATCH_G_browser_vlm.md` |
| K | VLM tests | 5 | 1 | 4 | backlog (K001-K003, K005) |
| L | Raw retention | 3 | 3 | 0 | `docs/06_plans/backlog/BATCH_I_retention.md` |
| M | Dataset classification | 1 | 0 | 1 | `docs/06_plans/backlog/BATCH_J_nav.md` |
| N | NAV ingestion | 4 | 4 | 0 | `docs/06_plans/backlog/BATCH_J_nav.md` |
| O | AMC / scheme master | 3 | 0 | 3 | `docs/06_plans/backlog/BATCH_K_scheme_amc.md` |
| P | Portfolio parser | 4 | 4 | 0 | `docs/06_plans/backlog/BATCH_L_portfolio.md` |
| Q | Metadata parser stubs | 3 | 0 | 3 | `docs/06_plans/backlog/BATCH_M_metadata.md` |

**Total pending**: 11 tasks → expected to add ~11 tests → projected count: ~156

## Execution Order

1. Batch E (G001–G006) — highest priority, correctness
2. Batch F (H001–H005) — core BFS behavior
3. Batch G (I001–I002, J001–J002) — browser/network paths
4. Batches I–M (remaining) — after above complete

## Gate

All epics complete + test count ≥ 145 → Phase 2 may begin.
