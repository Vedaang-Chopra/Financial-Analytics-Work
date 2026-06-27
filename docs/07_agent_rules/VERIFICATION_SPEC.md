# Verification Spec — Verifier Pi Session
# Audience: A fresh Pi session acting as Verifier (read-only audit)
# Do NOT modify any code. Do NOT run any agent pipeline. Read and assess only.

---

## 1. When Verifier Runs

Verifier runs when:
- Pi has written EXECUTION_RESULT.md with Status: ✓ Complete AND
- That completion claims a checkpoint's exit condition has been satisfied.

The human developer pastes the VERIFY prompt from docs/06_plans/PI_PROMPTS.md.
Verifier produces docs/01_status/VERIFICATION_REPORT.md and stops.

---

## 2. What Verifier Reads (in order)

```
1. docs/07_agent_rules/VERIFICATION_SPEC.md     (this file)
2. docs/06_plans/CHECKPOINT_PLAN.md             (exit condition for the checkpoint being verified)
3. docs/06_plans/EXECUTION_RESULT.md            (Pi's claimed completion + test output)
4. docs/01_status/AGENT_EXECUTION_LOG.md        (what Pi said it did)
5. docs/01_status/MASTER_STATE.md               (expected system state)
```

Then read the specific files for the checkpoint being verified (listed in §3 below by checkpoint).

---

## 3. What Verifier Checks

### For ALL checkpoints:
- [ ] Test count in EXECUTION_RESULT.md matches what pytest actually reports (re-run if needed)
- [ ] All acceptance criteria in EXECUTION_RESULT.md are marked [x] (not ☐)
- [ ] Only the files in MICROTASK_SPEC "Files to Create or Modify" were touched
- [ ] No files in profiling/ or amfi_disclosure/ were modified
- [ ] AGENT_EXECUTION_LOG.md has a new entry for this task

### Checkpoint 0 specific:
- [ ] `mutual_fund_ingestion/agent/upserts.py` exists
- [ ] `mutual_fund_ingestion/agent/artifact_processor.py` exists
- [ ] `mutual_fund_ingestion/agent/runner.py` is ≤350 lines
- [ ] All 125 tests pass (run: `./financial_env/bin/python -m pytest tests/ -q --tb=no`)
- [ ] `docs/02_architecture/system_overview.md` exists and has a Mermaid diagram
- [ ] `docs/02_architecture/database_schema.md` exists and mentions all 17 tables
- [ ] `docs/01_status/MASTER_STATE.md` has a "Database" section with DATABASE_URL
- [ ] `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb` runs without error

### Checkpoint 1.1 specific:
- [ ] `validate_scheme_master_record` function exists in `agent/validate.py`
- [ ] `validate_amc_record` function exists in `agent/validate.py`
- [ ] Both are wired into `validate_and_filter_records`
- [ ] `./financial_env/bin/python -m pytest tests/test_agent.py -k "scheme_master or amc_record" -v` → ≥4 passing
- [ ] Total test count ≥ 131

### Checkpoint 1.2 specific:
- [ ] `discovery.py` has factsheet, sid, kim, ter, aum_aaum in DATASET_TYPE_HINTS
- [ ] `./financial_env/bin/python -m pytest tests/test_agent.py -k "relevance or discovery or classification or browser" -v` → ≥8 passing
- [ ] Total test count ≥ 139

### Checkpoint 1.3 specific:
- [ ] `docs/06_plans/SPRINT_CURRENT.md` shows Phase 2 gate criteria all [x]
- [ ] Total test count ≥ 145
- [ ] `docs/04_in_progress/test_coverage_epics/overview.md` shows Epics G, H, P, N as "Done"

### Checkpoint 2 specific:
- [ ] `docs/06_plans/active/PHASE2_seed_amcs.md` exists with ≥3 AMC entries
- [ ] `docs/06_plans/active/PHASE2_discovery_log.md` exists with discovery run records
- [ ] `notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb` exists
- [ ] Total test count ≥ 145 (no regression)

### Checkpoint 3 specific:
- [ ] `data/raw/mutual_funds/` contains ≥1 file + ≥1 .json sidecar
- [ ] Sidecar has required fields: amc_name, dataset_type, source_url, downloaded_at
- [ ] `notebooks/mutual_fund_ingestion/04_phase3_real_data_review.ipynb` exists and shows DB records
- [ ] `docs/01_status/MASTER_STATE.md` has "First Real Document" entry

---

## 4. VERIFICATION_REPORT.md Format

Write to: `docs/01_status/VERIFICATION_REPORT.md` (overwrite each time).

```markdown
# VERIFICATION_REPORT.md
# Checkpoint: [0 / 1.1 / 1.2 / 1.3 / 2 / 3]
# Verifier: Pi (verification session)
# Date: YYYY-MM-DD

## Grade
[PASS | PASS_WITH_NOTES | FAIL]

## Test Count Verified
Expected: NNN
Actual (re-run): NNN
Match: [yes | no]

## Checklist Results
[copy the relevant checklist from §3, mark each [x] or [FAIL: reason]]

## Notes
[Any issues that are minor but worth flagging. Empty if PASS.]

## Failure Details
[Only fill if Grade is FAIL. For each failed check:]
  - What failed: [description]
  - Evidence: [paste relevant output]
  - Required fix: [what Pi must do to pass]
  - Files to change: [specific files]

## Go / No-Go
[PASS / PASS_WITH_NOTES: developer may approve and proceed to next checkpoint.]
[FAIL: Pi must fix the listed issues and re-submit. Do not start next checkpoint.]
```

---

## 5. Quality Grades

**PASS**
All checklist items marked [x]. Test count matches. No issues found.
Developer may approve and move to the next checkpoint.

**PASS_WITH_NOTES**
All critical items pass (test count, file existence, no forbidden modifications).
Minor issues exist that do not block progress (e.g., a doc section is thin, a log message is missing).
Developer reads Notes section and decides whether to fix before proceeding.

**FAIL**
At least one of the following is true:
- Test count is below the exit condition minimum.
- A required file does not exist.
- A forbidden file was modified (profiling/, amfi_disclosure/).
- An acceptance criterion is unchecked.
- A function the task was supposed to implement is missing.

**FAIL means Pi must fix the listed issues before the next checkpoint begins.**
The developer reads "Required fix" for each FAIL item and rewrites MICROTASK_SPEC.md with a corrective task.

---

## 6. Where Report Is Written

Always: `docs/01_status/VERIFICATION_REPORT.md`

Overwrite the previous report each time a new checkpoint is verified.
Old reports are preserved in git history — do not archive them manually.

---

## 7. What the Developer Reads

After Verifier finishes, the developer reads:
1. `docs/01_status/VERIFICATION_REPORT.md` — Grade + checklist + any failure details.
2. If FAIL: the "Required fix" lines tell the developer exactly what to put in the next MICROTASK_SPEC.
3. If PASS or PASS_WITH_NOTES: the developer approves and pastes the START prompt for the next checkpoint from `docs/06_plans/PI_PROMPTS.md`.

The developer's decision:
- PASS → paste next checkpoint START prompt
- PASS_WITH_NOTES → fix or accept → paste next checkpoint START prompt
- FAIL → rewrite MICROTASK_SPEC.md with corrective task → paste RESUME prompt for same checkpoint
