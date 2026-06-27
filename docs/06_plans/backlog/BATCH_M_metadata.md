# Batch M — Metadata Parser Stubs
# Milestone served: 2 (pipeline fully tested)
# Status: backlog
# Gate: Router entries for factsheet/SID/KIM/TER/AUM exist; stubs don't crash

## Purpose

Add router entries and stub parsers for factsheet, SID, KIM, TER, AUM so these document types don't silently drop.

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "metadata or factsheet or sid or ter" -v -q
```

## Tasks

### TASK-Q001: Add factsheet, sid, kim, ter, aum_aaum to PARSER_ROUTER
**Goal:** Add 5 new dataset_type entries to the parser router in `agent/parser/__init__.py`.
**Files to read:** `mutual_fund_ingestion/agent/parser/__init__.py`
**Files to modify:** `mutual_fund_ingestion/agent/parser/__init__.py`
**Exact work:**
1. Add router entries: `factsheet`, `sid`, `kim`, `ter`, `aum_aaum`
2. Each entry points to a stub function in `agent/parser/metadata.py`
3. Do not implement the parsers yet — stubs only (return empty list with a log message)
**Acceptance criteria:** Router has 5 new entries; no import errors
**Test command:** `./financial_env/bin/python -c "from mutual_fund_ingestion.agent.parser import route_parser; print(route_parser('factsheet', 'pdf'))"`
**Status:** pending

---

### TASK-Q002: Create parser/metadata.py with HTML and CSV stubs
**Goal:** Create `agent/parser/metadata.py` with stub functions for all 5 document types.
**Files to read:** `mutual_fund_ingestion/agent/parser/nav.py` (for pattern reference)
**Files to modify:** `mutual_fund_ingestion/agent/parser/metadata.py` (create or update)
**Exact work:**
1. `parse_factsheet_pdf(path) -> list[dict]` — returns `[]`, logs "factsheet parsing not yet implemented"
2. `parse_sid_pdf(path) -> list[dict]` — same stub
3. `parse_kim_pdf(path) -> list[dict]` — same stub
4. `parse_ter_csv(path) -> list[dict]` — same stub
5. `parse_aum_excel(path) -> list[dict]` — same stub
**Acceptance criteria:** All 5 functions importable; no crash on call
**Test command:** `./financial_env/bin/python -c "from mutual_fund_ingestion.agent.parser.metadata import parse_factsheet_pdf; print(parse_factsheet_pdf('/tmp/x.pdf'))"`
**Status:** pending

---

### TASK-Q003: Test metadata_html parser returns document record
**Goal:** Verify that calling a metadata stub returns an empty list without crashing.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/parser/metadata.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Call `parse_factsheet_pdf("/tmp/nonexistent.pdf")`
2. Assert result is an empty list (not an exception)
3. Repeat for `parse_sid_pdf`
**Acceptance criteria:** 2 tests passing — stubs don't raise
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "metadata_stub" -v`
**Status:** pending
