# Batch F — Discovery and Relevance Tests
# Milestone served: 2 (pipeline fully tested)
# Status: active
# Gate: All 5 H-epic discovery tests pass

## Purpose

Verify BFS discovery, relevance scoring, and dataset classification behave as specified.

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "relevance or discovery or classification" -v -q
```

## Tasks

### TASK-H001: Test high-relevance NAV link scoring
**Goal:** Verify that a URL containing "nav" scores above threshold in relevance scoring.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/discovery.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Call `DiscoveryEngine._score_relevance("https://example.com/nav_all.txt", "NAV Download")` (or equivalent)
2. Assert score ≥ 0.5 (or whatever threshold is defined)
3. Also test a low-relevance URL like "https://example.com/about-us" scores < 0.3
**Acceptance criteria:** 2 tests pass — high and low relevance cases
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "relevance" -v`
**Do not do:** Modify discovery.py scoring logic
**Status:** pending

---

### TASK-H002: Test link extraction from HTML fixture
**Goal:** Verify that `DiscoveryEngine` extracts links from a realistic HTML fixture.
**Files to read:** `tests/test_agent.py`, `tests/fixtures/amc_disclosure_page.html`, `mutual_fund_ingestion/agent/discovery.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Load `tests/fixtures/amc_disclosure_page.html` in test
2. Call link extraction on it
3. Assert at least 1 link is returned
4. Assert links are absolute URLs (not relative)
**Acceptance criteria:** 1 test passing with 1+ links extracted
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "link_extraction" -v`
**Do not do:** Mock the HTML — use the real fixture file
**Status:** pending

---

### TASK-H003: Test dataset classification by URL pattern
**Goal:** Verify `classify_dataset(url)` returns correct dataset_type for known URL patterns.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/discovery.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. `classify_dataset("https://example.com/nav_all.txt")` → `"nav_text"` (or similar)
2. `classify_dataset("https://example.com/portfolio_disclosure.xlsx")` → `"portfolio_excel"`
3. `classify_dataset("https://example.com/scheme_master.csv")` → `"scheme_master_csv"`
**Acceptance criteria:** 3 classification tests pass
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "classify_dataset" -v`
**Do not do:** Modify discovery.py unless a classification is genuinely wrong
**Status:** pending

---

### TASK-H004: Add SID/KIM/TER/AUM/factsheet to DATASET_TYPE_HINTS
**Goal:** Add URL hint patterns for factsheet, SID, KIM, TER, AUM dataset types in discovery.py.
**Files to read:** `mutual_fund_ingestion/agent/discovery.py`
**Files to modify:** `mutual_fund_ingestion/agent/discovery.py`
**Exact work:**
1. Find `DATASET_TYPE_HINTS` constant (or equivalent)
2. Add entries for: `factsheet` (PDF pattern), `sid` (SID PDF), `kim` (KIM PDF), `ter` (TER CSV/Excel), `aum_aaum` (AUM Excel)
3. No new functions — just extend the hints dict/list
**Acceptance criteria:** The 5 new type hints are present in discovery.py
**Test command:** `grep -n "factsheet\|sid\|kim\|ter\|aum" mutual_fund_ingestion/agent/discovery.py`
**Do not do:** Wire new types into the parser router (that's Q001)
**Status:** pending

---

### TASK-H005: Test factsheet and TER URL classification
**Goal:** Verify that factsheet and TER URLs are now classified correctly after H004.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/discovery.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. `classify_dataset("https://example.com/factsheet_Q1_2024.pdf")` → `"factsheet"`
2. `classify_dataset("https://example.com/TER_disclosure.csv")` → `"ter"`
**Acceptance criteria:** 2 classification tests pass for new types
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "factsheet or ter" -v`
**Do not do:** Test types not added in H004
**Status:** pending
