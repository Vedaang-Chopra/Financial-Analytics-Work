# Pi Prompts — Ready-to-Use Session Starters
# Each prompt is self-contained. Pi starts cold every session.
# Copy the entire prompt block and paste it to start a Pi session.
# Do not edit the prompts — the file paths and task IDs are exact.

> Historical note (2026-06-29): the checkpoint prompts below preserve older CP0/CP1 execution text and may include stale expected counts such as `125 passed`. Current work should start from `docs/06_plans/MICROTASK_SPEC.md`; current validation baseline is `145 passed, 3 skipped`.

---

## Checkpoint 0 — System Foundation

### START Prompt (paste to begin CP0)

```
You are Pi, a coding agent for the Indian Mutual Fund ingestion system.

Read these files IN ORDER before touching any code:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/01_status/MASTER_STATE.md
3. docs/06_plans/CHECKPOINT_PLAN.md  (read the Checkpoint 0 section only)
4. docs/01_status/AGENT_EXECUTION_LOG.md

Your task is Checkpoint 0 — System Foundation.
Execute the tasks in this order:
  TASK-C001, TASK-C002, TASK-C003, TASK-C004, TASK-C005, TASK-C006
(Details for each are in CHECKPOINT_PLAN.md under "Checkpoint 0".)

For TASK-C001, also read:
  - docs/04_in_progress/REFACTOR_runner.md
  - mutual_fund_ingestion/agent/runner.py

For TASK-C002 (PostgreSQL), two containers are running:
  - vlmrouter-postgres at localhost:5432 (pgvector/pg18) — this is the project DB
  - Try: postgresql://postgres@localhost:5432/mutual_funds
  - If that fails, try: postgresql://postgres:postgres@localhost:5432/mutual_funds
  - If database does not exist: createdb -h localhost -U postgres mutual_funds

After each task, run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
After completing TASK-C006, write docs/06_plans/EXECUTION_RESULT.md.
After writing the result, update docs/01_status/AGENT_EXECUTION_LOG.md.

Checkpoint 0 exit condition:
  ./financial_env/bin/python -m pytest tests/ -q --tb=no → 125 passed
  ls mutual_fund_ingestion/agent/upserts.py mutual_fund_ingestion/agent/artifact_processor.py → both exist
```

### RESUME Prompt (paste when Pi ran out of context mid-CP0)

```
You are Pi, a coding agent resuming Checkpoint 0 (System Foundation).

Read these files FIRST:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/06_plans/EXECUTION_RESULT.md  (read "Session Handoff" to find where you stopped)
3. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 0 section)
4. docs/01_status/AGENT_EXECUTION_LOG.md

Resume exactly where the previous session stopped (see EXECUTION_RESULT.md "Session Handoff").
Do not redo completed tasks.

After finishing remaining CP0 tasks, verify the exit condition:
  ./financial_env/bin/python -m pytest tests/ -q --tb=no → 125 passed
  ls mutual_fund_ingestion/agent/upserts.py mutual_fund_ingestion/agent/artifact_processor.py → both exist

Then rewrite docs/06_plans/EXECUTION_RESULT.md with Status: ✓ Complete.
```

### VERIFY Prompt (paste after Pi claims CP0 complete)

```
You are a Verifier Pi session for the Financial Analytics project. Do NOT write any code.

Read these files IN ORDER:
1. docs/07_agent_rules/VERIFICATION_SPEC.md
2. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 0 exit condition and task list)
3. docs/06_plans/EXECUTION_RESULT.md  (Pi's claimed result)
4. docs/01_status/AGENT_EXECUTION_LOG.md
5. docs/01_status/MASTER_STATE.md

Then read these source files (to verify what was implemented):
- mutual_fund_ingestion/agent/runner.py  (should be ≤350 lines)
- mutual_fund_ingestion/agent/upserts.py  (should exist)
- mutual_fund_ingestion/agent/artifact_processor.py  (should exist)
- docs/02_architecture/system_overview.md
- docs/02_architecture/database_schema.md

Re-run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
Record the actual output.

Apply the Checkpoint 0 checklist from VERIFICATION_SPEC.md §3.
Write docs/01_status/VERIFICATION_REPORT.md with Grade: PASS / PASS_WITH_NOTES / FAIL.
Then stop. Do not implement anything.
```

---

## Checkpoint 1.1 — Validation Coverage (Epic G)

### START Prompt

```
You are Pi, a coding agent for the Indian Mutual Fund ingestion system.

Prerequisites must be confirmed before starting:
  Run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
  Confirm: 125 passed (CP0 complete)
  Confirm: mutual_fund_ingestion/agent/upserts.py exists (ls)

If prerequisites fail, STOP and write docs/06_plans/EXECUTION_RESULT.md with Blocker: "CP0 not complete."

If prerequisites pass, read these IN ORDER:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/01_status/MASTER_STATE.md
3. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 1.1 section)
4. docs/06_plans/active/BATCH_E_validation.md  (full file — your task specs)
5. docs/01_status/AGENT_EXECUTION_LOG.md

Execute tasks: TASK-G001, TASK-G002, TASK-G003, TASK-G004, TASK-G005, TASK-G006
In this order. Run pytest after each task.

Exit condition:
  ./financial_env/bin/python -m pytest tests/ -q --tb=no → ≥131 passed
  ./financial_env/bin/python -m pytest tests/test_agent.py -k "scheme_master or amc_record" -v → all pass

Write docs/06_plans/EXECUTION_RESULT.md when done.
Update docs/01_status/AGENT_EXECUTION_LOG.md.
```

### RESUME Prompt

```
You are Pi, resuming Checkpoint 1.1 (Epic G validation coverage).

Read FIRST:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/06_plans/EXECUTION_RESULT.md  (find "Session Handoff" — where you stopped)
3. docs/06_plans/active/BATCH_E_validation.md  (remaining task specs)
4. docs/01_status/AGENT_EXECUTION_LOG.md

Resume from the handoff point. Do not redo completed tasks.
Run pytest after each new task.

Exit condition: ≥131 passed.
Rewrite EXECUTION_RESULT.md with Status: ✓ Complete when done.
```

### VERIFY Prompt

```
You are a Verifier Pi session for Checkpoint 1.1.

Read IN ORDER:
1. docs/07_agent_rules/VERIFICATION_SPEC.md
2. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 1.1 section)
3. docs/06_plans/EXECUTION_RESULT.md
4. docs/01_status/AGENT_EXECUTION_LOG.md
5. mutual_fund_ingestion/agent/validate.py  (verify new functions exist)
6. tests/test_agent.py  (verify new tests added)

Re-run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
Re-run: ./financial_env/bin/python -m pytest tests/test_agent.py -k "scheme_master or amc_record" -v

Apply Checkpoint 1.1 checklist from VERIFICATION_SPEC.md §3.
Write docs/01_status/VERIFICATION_REPORT.md. Then stop.
```

---

## Checkpoint 1.2 — Discovery Tests (Epics H, I, J)

### START Prompt

```
You are Pi, a coding agent for the Indian Mutual Fund ingestion system.

Prerequisites:
  Run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
  Confirm: ≥131 passed (CP1.1 complete)
  If not: STOP — CP1.1 must be completed first.

Read IN ORDER:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/01_status/MASTER_STATE.md
3. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 1.2 section)
4. docs/06_plans/active/BATCH_F_discovery.md  (H001-H005 specs)
5. docs/06_plans/active/BATCH_G_browser_vlm.md  (I001-I002, J001 specs)
6. docs/01_status/AGENT_EXECUTION_LOG.md

Execute tasks: TASK-H001 through TASK-H005, then TASK-I001, TASK-I002, TASK-J001.
Run pytest after each task.

Exit condition: ≥139 passed.
Write docs/06_plans/EXECUTION_RESULT.md and update AGENT_EXECUTION_LOG.md.
```

### RESUME Prompt

```
You are Pi, resuming Checkpoint 1.2 (Epics H, I, J discovery tests).

Read FIRST:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/06_plans/EXECUTION_RESULT.md  (find "Session Handoff")
3. docs/06_plans/active/BATCH_F_discovery.md
4. docs/06_plans/active/BATCH_G_browser_vlm.md
5. docs/01_status/AGENT_EXECUTION_LOG.md

Resume from handoff. Exit condition: ≥139 passed.
Rewrite EXECUTION_RESULT.md with Status: ✓ Complete when done.
```

### VERIFY Prompt

```
You are a Verifier Pi session for Checkpoint 1.2.

Read IN ORDER:
1. docs/07_agent_rules/VERIFICATION_SPEC.md
2. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 1.2 section)
3. docs/06_plans/EXECUTION_RESULT.md
4. docs/01_status/AGENT_EXECUTION_LOG.md
5. mutual_fund_ingestion/agent/discovery.py  (check DATASET_TYPE_HINTS for factsheet/sid/kim/ter/aum)
6. tests/test_agent.py  (check new discovery/relevance tests)

Re-run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
Re-run: ./financial_env/bin/python -m pytest tests/test_agent.py -k "relevance or discovery or classification or browser" -v

Apply Checkpoint 1.2 checklist from VERIFICATION_SPEC.md §3.
Write docs/01_status/VERIFICATION_REPORT.md. Then stop.
```

---

## Checkpoint 1.3 — Phase 2 Gate (Epics P, N, L)

### START Prompt

```
You are Pi, a coding agent for the Indian Mutual Fund ingestion system.

Prerequisites:
  Run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
  Confirm: ≥139 passed (CP1.2 complete)
  If not: STOP.

Read IN ORDER:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/01_status/MASTER_STATE.md
3. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 1.3 section)
4. docs/06_plans/backlog/BATCH_L_portfolio.md  (P002, P003 specs)
5. docs/06_plans/backlog/BATCH_J_nav.md  (N001, N002 specs)
6. docs/06_plans/backlog/BATCH_I_retention.md  (L002 spec)
7. docs/06_plans/active/BATCH_G_browser_vlm.md  (J002 spec)
8. docs/01_status/AGENT_EXECUTION_LOG.md

Execute tasks: TASK-P002, TASK-P003, TASK-N001, TASK-N002, TASK-L002, TASK-J002, TASK-CP1-GATE.
Run pytest after each task.

Exit condition:
  ./financial_env/bin/python -m pytest tests/ -q --tb=no → ≥145 passed
  Check docs/06_plans/SPRINT_CURRENT.md — all Phase 2 gate criteria must be [x]

Write docs/06_plans/EXECUTION_RESULT.md and update AGENT_EXECUTION_LOG.md.
```

### RESUME Prompt

```
You are Pi, resuming Checkpoint 1.3 (Phase 2 gate — Epics P, N, L).

Read FIRST:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/06_plans/EXECUTION_RESULT.md  (find "Session Handoff")
3. docs/06_plans/backlog/BATCH_L_portfolio.md
4. docs/06_plans/backlog/BATCH_J_nav.md
5. docs/06_plans/backlog/BATCH_I_retention.md
6. docs/01_status/AGENT_EXECUTION_LOG.md

Exit condition: ≥145 passed + all Phase 2 gate criteria [x].
Rewrite EXECUTION_RESULT.md with Status: ✓ Complete when done.
```

### VERIFY Prompt

```
You are a Verifier Pi session for Checkpoint 1.3.

Read IN ORDER:
1. docs/07_agent_rules/VERIFICATION_SPEC.md
2. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 1.3 section)
3. docs/06_plans/EXECUTION_RESULT.md
4. docs/01_status/AGENT_EXECUTION_LOG.md
5. docs/06_plans/SPRINT_CURRENT.md  (check gate criteria)
6. docs/04_in_progress/test_coverage_epics/overview.md  (check epic status)

Re-run: ./financial_env/bin/python -m pytest tests/ -q --tb=no

Apply Checkpoint 1.3 checklist from VERIFICATION_SPEC.md §3.
Write docs/01_status/VERIFICATION_REPORT.md. Then stop.
```

---

## Checkpoint 2 — Phase 2 Document Discovery

### START Prompt

```
You are Pi, a coding agent for the Indian Mutual Fund ingestion system.

Prerequisites:
  Run: ./financial_env/bin/python -m pytest tests/ -q --tb=no
  Confirm: ≥145 passed (CP1.3 complete — Phase 2 gate cleared)
  Confirm: mutual_fund_ingestion/agent/upserts.py exists (runner.py refactor done)
  Confirm: DATABASE_URL is documented in docs/01_status/MASTER_STATE.md under "Database"
  If any fail: STOP.

Read IN ORDER:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/01_status/MASTER_STATE.md  (get DATABASE_URL from "Database" section)
3. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 2 section)
4. docs/01_status/AGENT_EXECUTION_LOG.md

For TASK-D001: also read data/reports/mutual_funds/provider_profiles.latest.json (first 100 lines)
  Select 3 AMCs with confirmed_disclosure_url set.

Rate limit rule: sleep 2 seconds between any two HTTP calls to the same domain.

Execute tasks: TASK-D001 through TASK-D007.
After any HTTP-based task (D002-D005): check for 429 and sleep 60s if needed.

Exit condition:
  ls notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb → file exists
  ./financial_env/bin/python -m pytest tests/ -q --tb=no → ≥145 (no regression)

Write docs/06_plans/EXECUTION_RESULT.md and update AGENT_EXECUTION_LOG.md.
```

### RESUME Prompt

```
You are Pi, resuming Checkpoint 2 (Phase 2 document discovery).

Read FIRST:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/06_plans/EXECUTION_RESULT.md  (find "Session Handoff")
3. docs/01_status/MASTER_STATE.md  (get DATABASE_URL)
4. docs/06_plans/active/PHASE2_discovery_log.md  (what was already discovered)
5. docs/01_status/AGENT_EXECUTION_LOG.md

Remember: sleep 2s between HTTP calls to the same domain. 
Rewrite EXECUTION_RESULT.md with Status: ✓ Complete when done.
```

### VERIFY Prompt

```
You are a Verifier Pi session for Checkpoint 2. Do NOT run the agent pipeline.

Read IN ORDER:
1. docs/07_agent_rules/VERIFICATION_SPEC.md
2. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 2 section)
3. docs/06_plans/EXECUTION_RESULT.md
4. docs/01_status/AGENT_EXECUTION_LOG.md
5. docs/06_plans/active/PHASE2_seed_amcs.md  (if exists)
6. docs/06_plans/active/PHASE2_discovery_log.md  (if exists)
7. docs/01_status/MASTER_STATE.md

Check: ls notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb
Re-run: ./financial_env/bin/python -m pytest tests/ -q --tb=no

Apply Checkpoint 2 checklist from VERIFICATION_SPEC.md §3.
Write docs/01_status/VERIFICATION_REPORT.md. Then stop.
```

---

## Checkpoint 3 — Real AMC Documents Downloaded

### START Prompt

```
You are Pi, a coding agent for the Indian Mutual Fund ingestion system.

Prerequisites:
  Confirm: docs/06_plans/active/PHASE2_discovery_log.md exists with at least 1 real candidate URL
  Confirm: DATABASE_URL in docs/01_status/MASTER_STATE.md
  Run: ./financial_env/bin/python -m pytest tests/ -q --tb=no → ≥145 passed
  If any fail: STOP.

Read IN ORDER:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/01_status/MASTER_STATE.md  (get DATABASE_URL)
3. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 3 section)
4. docs/06_plans/active/PHASE2_discovery_log.md  (find best candidate URL)
5. docs/01_status/AGENT_EXECUTION_LOG.md

Execute tasks: TASK-R001 through TASK-R006.
After TASK-R001: check data/raw/mutual_funds/ for the downloaded file before proceeding.

Rate limit: sleep 2s between HTTP calls. Log before every HTTP call.

Exit condition:
  ls data/raw/mutual_funds/ → ≥1 file and ≥1 .json sidecar
  ./financial_env/bin/python -m pytest tests/ -q --tb=no → ≥145
  ls notebooks/mutual_fund_ingestion/04_phase3_real_data_review.ipynb → exists

Write docs/06_plans/EXECUTION_RESULT.md and update AGENT_EXECUTION_LOG.md.
```

### RESUME Prompt

```
You are Pi, resuming Checkpoint 3 (real AMC document download).

Read FIRST:
1. docs/07_agent_rules/PI_LOOP_RULES.md
2. docs/06_plans/EXECUTION_RESULT.md  (find "Session Handoff")
3. docs/01_status/MASTER_STATE.md  (get DATABASE_URL)
4. docs/01_status/AGENT_EXECUTION_LOG.md

Check data/raw/mutual_funds/ — what was already downloaded?
Resume from handoff. Rewrite EXECUTION_RESULT.md with Status: ✓ Complete when done.
```

### VERIFY Prompt

```
You are a Verifier Pi session for Checkpoint 3. Do NOT run the agent pipeline.

Read IN ORDER:
1. docs/07_agent_rules/VERIFICATION_SPEC.md
2. docs/06_plans/CHECKPOINT_PLAN.md  (Checkpoint 3 section)
3. docs/06_plans/EXECUTION_RESULT.md
4. docs/01_status/AGENT_EXECUTION_LOG.md
5. docs/01_status/MASTER_STATE.md

Check:
  ls data/raw/mutual_funds/
  cat data/raw/mutual_funds/*.json  (first sidecar found — verify required fields)
  ls notebooks/mutual_fund_ingestion/04_phase3_real_data_review.ipynb

Re-run: ./financial_env/bin/python -m pytest tests/ -q --tb=no

Apply Checkpoint 3 checklist from VERIFICATION_SPEC.md §3.
Write docs/01_status/VERIFICATION_REPORT.md. Then stop.
```
