# PLAN.md — Mutual Fund Ingestion System Implementation Plan

## Status Update — 2026-06-21

**Full audit completed. 88/88 tests pass.** Key findings:

- Phase 1A/1B: complete and frozen
- Task-URL Agent: orchestration loop complete with DB persistence
- runner.py writes to all 17 tables (prior note that it did not was incorrect)
- portfolio.py column mapping bug FIXED (TASK-P001)
- VLM is wired but analyze_page() never called (TASK-K005)
- retry-failed CLI crashes without --run-id (TASK-D001 - FIXED)
- 5 root-level .db files not in .gitignore (TASK-A001 - FIXED, patterns exist and work)
- pika removed from requirements.txt (TASK-A002 - FIXED)
- logging format fixed with timestamps (TASK-D002 - FIXED)

See: plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md for full audit.

---

## Task 1: EvidenceParser → LinkExtractor [DONE]

**Status: COMPLETE** — `agent/discovery.py` now uses `LinkExtractor` class for link extraction. The EvidenceParser from Phase 1 profiling was not needed for the agent pipeline.

---

## Task 2: Wire runner.run() to DB [DONE]

**Status: COMPLETE** — `runner.py` now writes to all major tables (ingestion_runs, task_urls, source_pages, discovered_links, dataset_candidates, raw_artifacts, staging_rows, quarantine_rows, retry_queue, and canonical tables). The original audit finding that "runner.run() does NOT insert to PostgreSQL" was incorrect.

---

## Section 1.5: Design vs. Code Mismatches

**NOTE 2026-06-21:** The runner.run() gap listed here was already fixed before this document was created. See CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md for accurate status.

---

## Remaining Implementation Tasks (from TASKS_FULL_SYSTEM_MICRO_PLAN.md)

### Epic A — Repository Hygiene (COMPLETE)

- TASK-A001: *.db patterns in .gitignore ✓ (verified working)
- TASK-A002: Remove pika from requirements.txt ✓ (done)
- TASK-A003: Verify temp files in /tmp ✓ (verified)
- TASK-A004: financial_env/ in .gitignore ✓ (already present)

### Epic D — CLI Stability (COMPLETE)

- TASK-D001: Fix retry-failed crash ✓ (guard added)
- TASK-D002: Fix logging format ✓ (timestamps added)

### Next: Epic B — Documentation Truth Cleanup (IN PROGRESS)

- TASK-B001: Update PLAN.md ✓ (this file)
- TASK-B002: Update task_url_ingestion_agent.md test count and gaps
- TASK-B003: Update CHATGPT_PROJECT_MEMORY.md current status
- TASK-B004: Update CODEBASE_MAP.md with portfolio bug and amfi_disclosure status
- TASK-B005: Update README.md test count

### Epic P — Portfolio Disclosure (HIGH PRIORITY)

- TASK-P001: Fix portfolio.py column mapping for real Excel files

### Epic K — VLM Integration

- TASK-K005: Wire VLM invocation in runner for low-confidence pages

### Epic L — Raw Artifact Retention

- TASK-L001: Implement raw file retention (move to raw_dir)

---

## Verification Commands

```bash
# Full test suite
python -m pytest tests/ -q
# Expected: 85 passed

# CLI logging format
python -m mutual_fund_ingestion init-db --database-url sqlite:///test.db --log-level DEBUG 2>&1 | head -3
# Expected: Timestamped log lines

# Retry-failed guard
python -m mutual_fund_ingestion retry-failed --database-url sqlite:///test.db; echo "exit: $?"
# Expected: "Error: --run-id is required" + exit code 1
```
