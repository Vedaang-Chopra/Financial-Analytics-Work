# Batch L — Portfolio Parser Tests
# Milestone served: 2 (pipeline fully tested)
# Status: backlog
# Gate: Portfolio Excel fixture test passing; P001/P004 already done

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/ -k "portfolio" -v -q
```

## Tasks

### TASK-P002: Create portfolio Excel fixture with real AMFI column names
**Goal:** Create `tests/fixtures/data/portfolio_sample.xlsx` with AMFI real column names.
**Files to read:** `mutual_fund_ingestion/agent/parser/portfolio.py`
**Files to modify:** `tests/fixtures/data/portfolio_sample.xlsx` (create)
**Exact work:**
1. Use `openpyxl` to create minimal Excel with columns: Security Name, ISIN, Rating, Percentage to Net Assets, Market Value (Rs. In Lakhs)
2. Add ≥3 data rows
3. Match exact column names that AMFI uses (see portfolio.py header detection)
**Acceptance criteria:** File parseable by `parse_portfolio_excel`
**Test command:** `./financial_env/bin/python -c "from mutual_fund_ingestion.agent.parser.portfolio import parse_portfolio_excel; print(parse_portfolio_excel('tests/fixtures/data/portfolio_sample.xlsx'))"`
**Status:** pending

---

### TASK-P003: Test parse_portfolio_excel with real AMFI column names
**Goal:** Verify `parse_portfolio_excel` returns correct record structure.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/parser/portfolio.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Load `tests/fixtures/data/portfolio_sample.xlsx`
2. Call `parse_portfolio_excel(path)`
3. Assert result has ≥1 record with `security_name` and `percentage_to_nav` populated
4. Assert `percentage_to_nav` is a float
**Acceptance criteria:** 1 test passing with real column name detection
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "parse_portfolio_excel" -v`
**Do not do:** Mock openpyxl; use a hand-written fixture file
**Status:** pending
