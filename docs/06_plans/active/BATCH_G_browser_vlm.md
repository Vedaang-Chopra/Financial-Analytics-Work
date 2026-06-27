# Batch G — Browser and Network Tests
# Milestone served: 2 (pipeline fully tested)
# Status: active
# Gate: All 4 I/J-epic browser+network tests pass

## Purpose

Verify Playwright and network-capture paths are tested.

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "browser or network or playwright" -v -q
```

## Tasks

### TASK-I001: Test BrowserUnavailable raised when Playwright not installed
**Goal:** Verify that `extract_with_browser` raises a clear error when Playwright is unavailable.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/browser.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Mock `playwright.sync_api.sync_playwright` to raise ImportError
2. Call `extract_with_browser(url, config)`
3. Assert a `BrowserUnavailable` (or `RuntimeError` with "playwright" in message) is raised
**Acceptance criteria:** 1 test passing — browser error is not a silent failure
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "browser_unavailable" -v`
**Do not do:** Install/uninstall Playwright; test actual browser rendering
**Status:** pending

---

### TASK-I002: Test extract_with_browser with mocked Playwright
**Goal:** Verify `extract_with_browser` returns a `BrowserResult` with expected fields when Playwright runs.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/browser.py`, `mutual_fund_ingestion/agent/models.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Mock the Playwright sync API to return a minimal page with known HTML
2. Call `extract_with_browser(url, config)`
3. Assert result is a `BrowserResult` (or dict) with `html`, `links`, `status_code` fields populated
**Acceptance criteria:** 1 test passing — BrowserResult has expected structure
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "extract_with_browser_mocked" -v`
**Do not do:** Make real network calls; use actual browser
**Status:** pending

---

### TASK-J001: Test network download detection in BrowserResult
**Goal:** Verify that `BrowserResult.network_downloads` is populated when browser captures file downloads.
**Files to read:** `tests/test_agent.py`, `mutual_fund_ingestion/agent/browser.py`, `mutual_fund_ingestion/agent/models.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Mock Playwright to simulate a network response with `content-type: application/vnd.ms-excel`
2. Assert that `BrowserResult.network_downloads` (or equivalent field) contains the URL
**Acceptance criteria:** 1 test passing
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "network_download" -v`
**Do not do:** Real network calls
**Status:** pending

---

### TASK-J002: Add AMFI direct API URL to DATASET_TYPE_HINTS
**Goal:** Add AMFI NAV API URL pattern to DATASET_TYPE_HINTS in discovery.py.
**Files to read:** `mutual_fund_ingestion/agent/discovery.py`
**Files to modify:** `mutual_fund_ingestion/agent/discovery.py`
**Exact work:**
1. Add entry for `https://www.amfiindia.com/spages/NAVAll.txt` (or pattern) → `nav_text`
2. Add entry for AMFI scheme master URL pattern → `scheme_master_csv`
**Acceptance criteria:** 2 AMFI URL patterns in DATASET_TYPE_HINTS
**Test command:** `grep -n "amfiindia\|AMFI" mutual_fund_ingestion/agent/discovery.py`
**Do not do:** Remove existing hints; modify routing logic
**Status:** pending
