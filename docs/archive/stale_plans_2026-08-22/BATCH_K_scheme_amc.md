# Batch K — AMC and Scheme Master Tests
# Milestone served: 2 (pipeline fully tested)
# Status: backlog
# Gate: Scheme master CSV parsing and AMC-scheme linkage tested

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/ -k "scheme_master or amc" -v -q
```

## Tasks

### TASK-O001: Create scheme_master.csv fixture
**Goal:** Create `tests/fixtures/data/scheme_master.csv` with realistic AMFI scheme master format.
**Files to read:** `mutual_fund_ingestion/agent/parser/scheme_master.py`
**Files to modify:** `tests/fixtures/data/scheme_master.csv` (create)
**Exact work:**
1. Create CSV with columns: Scheme Code, Scheme Name, AMC Code, Category, Sub-Category
2. Include ≥3 rows from different AMCs
**Acceptance criteria:** File parseable by `parse_scheme_master_csv`
**Test command:** `./financial_env/bin/python -c "from mutual_fund_ingestion.agent.parser.scheme_master import parse_scheme_master_csv; import csv; print(parse_scheme_master_csv(open('tests/fixtures/data/scheme_master.csv').read()))"`
**Status:** pending

---

### TASK-O002: Test parse_scheme_master_csv with fixture
**Goal:** Verify `parse_scheme_master_csv` returns correct record structure.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/parser/scheme_master.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Load `tests/fixtures/data/scheme_master.csv`
2. Assert result has ≥1 record with `scheme_code` and `scheme_name`
**Acceptance criteria:** 1 test passing
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "parse_scheme_master_csv" -v`
**Status:** pending

---

### TASK-O003: Test _upsert_schemes links scheme to AMC
**Goal:** Verify that scheme rows written to DB reference the correct AMC via FK.
**Files to read:** `tests/test_agent_db.py`, `mutual_fund_ingestion/agent/runner.py`, `mutual_fund_ingestion/agent/db.py`
**Files to modify:** `tests/test_agent_db.py`
**Exact work:**
1. In an e2e fixture test, after a scheme_master parse+upsert run, query `schemes` table
2. Assert `schemes.amc_id` is non-null and links to an existing row in `amcs`
**Acceptance criteria:** 1 test passing — referential integrity confirmed
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent_db.py -k "scheme_amc" -v`
**Status:** pending
