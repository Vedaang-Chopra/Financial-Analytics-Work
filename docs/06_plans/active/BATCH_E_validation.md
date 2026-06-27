# Batch E — Validation Coverage
# Milestone served: 2 (pipeline fully tested)
# Status: active
# Gate: All 6 G-epic validation tests pass

## Purpose

Add validators for dataset types currently unvalidated: scheme_master, AMC.

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "validation or quarantine" -v -q
# All validation tests pass including scheme_master and AMC cases
```

## Tasks

### TASK-G001: Add validate_scheme_master_record function
**Goal:** Implement `validate_scheme_master_record(record: dict) -> tuple[bool, str]` in agent/validate.py.
**Files to read:** `mutual_fund_ingestion/agent/validate.py`, `mutual_fund_ingestion/agent/models.py`
**Files to modify:** `mutual_fund_ingestion/agent/validate.py`
**Exact work:**
1. Add `validate_scheme_master_record(record)` that checks required fields (scheme_code, scheme_name, amc_code)
2. Returns `(True, "")` if valid, `(False, "reason: <description>")` if invalid
3. Follow exact same pattern as `validate_nav_record`
**Acceptance criteria:** Function exists, returns correct bool+reason tuple
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "scheme_master" -v`
**Do not do:** Wire into runner (that's G003); add to __init__.py exports (check if needed)
**Status:** pending

---

### TASK-G002: Add validate_amc_record function
**Goal:** Implement `validate_amc_record(record: dict) -> tuple[bool, str]` in agent/validate.py.
**Files to read:** `mutual_fund_ingestion/agent/validate.py`, `mutual_fund_ingestion/agent/models.py`
**Files to modify:** `mutual_fund_ingestion/agent/validate.py`
**Exact work:**
1. Add `validate_amc_record(record)` that checks required fields (amc_code, amc_name)
2. Returns `(True, "")` if valid, `(False, "reason: <description>")` if invalid
**Acceptance criteria:** Function exists with correct signature
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "amc_record" -v`
**Do not do:** Wire into runner yet (G003); duplicate existing validation logic
**Status:** pending

---

### TASK-G003: Wire scheme_master and AMC validators into validate_and_filter_records
**Goal:** Add `scheme_master` and `amc` dataset_type branches to `validate_and_filter_records`.
**Files to read:** `mutual_fund_ingestion/agent/validate.py`
**Files to modify:** `mutual_fund_ingestion/agent/validate.py`
**Exact work:**
1. In `validate_and_filter_records`, add elif branches for `dataset_type == "scheme_master"` and `dataset_type == "amc"`
2. Call `validate_scheme_master_record` and `validate_amc_record` respectively
3. Do not change existing NAV/portfolio branches
**Acceptance criteria:** `validate_and_filter_records(records, "scheme_master", ...)` works correctly
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "validate_and_filter" -v`
**Do not do:** Modify runner.py in this task
**Status:** pending

---

### TASK-G004: Add tests for scheme_master and AMC validation
**Goal:** Write tests for G001-G003 validators.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/validate.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. `test_validate_scheme_master_record_valid` — valid record passes
2. `test_validate_scheme_master_record_missing_code` — missing scheme_code fails with reason
3. `test_validate_amc_record_valid` — valid amc record passes
4. `test_validate_amc_record_missing_name` — missing amc_name fails with reason
**Acceptance criteria:** 4 new tests pass
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "scheme_master or amc_record" -v`
**Do not do:** Mock the validators; test internal implementation details
**Status:** pending

---

### TASK-G005: Verify staging_rows.raw_row_json preserves original record
**Goal:** Confirm that `staging_rows.raw_row_json` stores the original parsed record before validation.
**Files to read:** `tests/test_agent_db.py`, `mutual_fund_ingestion/agent/runner.py`, `mutual_fund_ingestion/agent/db.py`
**Files to modify:** `tests/test_agent_db.py`
**Exact work:**
1. Write or extend an existing fixture e2e test to check staging_rows.raw_row_json is non-null
2. Assert that the raw_row_json key matches the original record fields
**Acceptance criteria:** 1 new test or assertion added and passing
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent_db.py -k "staging" -v`
**Do not do:** Modify runner.py or db.py
**Status:** pending

---

### TASK-G006: Add test: quarantine reason codes are non-empty
**Goal:** Confirm that every quarantine_row has a non-empty reason_code when a record fails validation.
**Files to read:** `tests/test_agent_db.py`, `mutual_fund_ingestion/agent/validate.py`
**Files to modify:** `tests/test_agent_db.py`
**Exact work:**
1. Write test that injects a bad record into the pipeline (invalid NAV or portfolio)
2. Assert quarantine_rows table has a row with non-empty reason_code
**Acceptance criteria:** 1 new test passing; quarantine reason_code is never empty string or None
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent_db.py -k "quarantine" -v`
**Do not do:** Modify the validation logic (this is a test only)
**Status:** pending
