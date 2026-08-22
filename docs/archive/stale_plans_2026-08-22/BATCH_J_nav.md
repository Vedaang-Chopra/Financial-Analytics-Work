# Batch J — NAV Ingestion Tests
# Milestone served: 2 (pipeline fully tested)
# Status: backlog
# Gate: NAV text, CSV, HTML all tested end-to-end

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "nav" -v -q
```

## Tasks

### TASK-N001: Create NAV text fixture file
**Goal:** Create `tests/fixtures/data/nav_all_schemes.txt` if not already present.
**Files to read:** `tests/fixtures/data/` (check what exists)
**Files to modify:** `tests/fixtures/data/nav_all_schemes.txt` (create)
**Exact work:**
1. Check if `tests/fixtures/data/nav_all_schemes.txt` already exists
2. If not: create a minimal TAB-delimited AMFI NAV file with 3–5 rows
3. Format: `Scheme Code|ISIN Div Payout|ISIN Div Reinvestment|Scheme Name|Net Asset Value|Date`
**Acceptance criteria:** File exists, has ≥3 data rows, parseable by `parse_nav_text`
**Test command:** `./financial_env/bin/python -c "from mutual_fund_ingestion.agent.parser.nav import parse_nav_text; print(parse_nav_text(open('tests/fixtures/data/nav_all_schemes.txt').read()))"`
**Do not do:** Use real AMFI data (privacy/size); make network calls
**Status:** pending

---

### TASK-N002: Test parse_nav_text with realistic fixture
**Goal:** Verify `parse_nav_text` parses the N001 fixture and returns correct record structure.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/parser/nav.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Load `tests/fixtures/data/nav_all_schemes.txt`
2. Call `parse_nav_text(content)`
3. Assert result has ≥1 record with `scheme_code` and `nav_value` fields
4. Assert `nav_value` is a float
**Acceptance criteria:** 1 test passing
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "parse_nav_text" -v`
**Status:** pending

---

### TASK-N004: Test parse_nav_html with fixture
**Goal:** Verify `parse_nav_html` parses the existing HTML fixture and returns correct records.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/parser/nav.py`, `tests/fixtures/`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Locate or create a minimal NAV HTML table fixture
2. Call `parse_nav_html(html_content)`
3. Assert result has ≥1 record with `scheme_code` and `nav_value`
**Acceptance criteria:** 1 test passing
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "parse_nav_html" -v`
**Status:** pending
