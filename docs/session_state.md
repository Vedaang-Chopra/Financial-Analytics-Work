# Session Handoff: Financial Analytics Work - Mutual Fund Ingestion

## Current State

Continuing task 88 of 140 for the mutual fund ingestion system. Working on **Epic L (Raw Artifact Retention)** and **Epic R (Fixture Website Tests)**.

## Progress Summary

- **83 tasks completed** before this session
- **Epic L**: L001 implemented (raw file retention in runner.py), L002/L003 tests added but SKIPPED (need network/mock refinement)
- **Epic R**: R001 (passed), R002 (passed), R003 and R004 tests attempted but failed due to file corruption

## Current Blocker: R003/R004 Tests

### The Problem

Tests for Epic R (fixture-based end-to-end tests) keep failing due to file corruption when editing `tests/test_agent_db.py`. The file keeps getting indentation errors.

### What Needs to Be Done

Add two tests to `tests/test_agent_db.py`:

1. **`test_fixture_seed_page_writes_source_pages`** (R003): Test that seed page discovery writes source_pages and discovered_links
2. **`test_fixture_nav_file_upserted_to_nav_history`** (R004): Test NAV file parse and upsert to nav_history

### Fixtures Already Created

- `tests/fixtures/amfi_seed_page.html` - AMFI seed page fixture
- `tests/fixtures/amc_disclosure_page.html` - AMC disclosure page fixture
- `tests/fixtures/data/nav_all_schemes.txt` - NAV data fixture
- `tests/fixtures/data/scheme_master.csv` - Scheme master fixture
- `tests/fixtures/data/portfolio_sample.xlsx` - Portfolio fixture

### Correct Test Implementation Pattern

The tests should be added between the last test in `DBIntegrationTests` class (which ends at `test_run_agent_creates_source_pages`) and the `ParserUpsertTests` class.

Here's the correct implementation to add:

```python
def test_fixture_seed_page_writes_source_pages(self):
    """R003: Test seed page discovery writes source_pages and discovered_links."""
    from pathlib import Path
    import unittest.mock as mock
    from mutual_fund_ingestion.agent.db import SourcePage, DiscoveredLink
    from sqlalchemy import select
    
    seed_html = (Path(__file__).parent / "fixtures" / "amfi_seed_page.html").read_text()
    config = AgentConfig(
        task_urls=["https://fixture.amfi.com/"],
        database_url=self.db_path,
        max_pages=1, max_files=0, use_browser=False,
    )
    with mock.patch("mutual_fund_ingestion.agent.discovery.DiscoveryEngine.fetch",
                    return_value=(200, seed_html)):
        runner = IngestionRunner(config)
        runner.run()
    session = self.session_maker()
    try:
        pages = session.execute(select(SourcePage)).scalars().all()
        self.assertGreaterEqual(len(pages), 1)
    finally:
        session.close()
    session = self.session_maker()
    try:
        links = session.execute(select(DiscoveredLink)).scalars().all()
        self.assertGreaterEqual(len(links), 3)
    finally:
        session.close()

def test_fixture_nav_file_upserted_to_nav_history(self):
    """R004: Test NAV file parse and upsert to nav_history."""
    from pathlib import Path
    import unittest.mock as mock
    from mutual_fund_ingestion.agent.db import NAVHistory
    from sqlalchemy import select
    
    seed_html = (Path(__file__).parent / "fixtures" / "amc_disclosure_page.html").read_text()
    nav_content = (Path(__file__).parent / "fixtures" / "data" / "nav_all_schemes.txt").read_bytes()
    
    def fake_fetch(url):
        return (200, seed_html)
    
    def fake_download(url, run_id):
        if "nav_all_schemes" in url:
            return {
                "url": url, "file_type": "text", "content_type": "text/plain",
                "checksum": "abc123", "size_bytes": len(nav_content),
                "local_path": None, "retained": False, "content": nav_content
            }
        return {"error": "not found"}
    
    config = AgentConfig(
        task_urls=["https://fixture.amc.com/"],
        database_url=self.db_path,
        max_pages=2, max_files=1, use_browser=False,
    )
    with mock.patch("mutual_fund_ingestion.agent.discovery.DiscoveryEngine.fetch", side_effect=fake_fetch), \
         mock.patch("mutual_fund_ingestion.agent.extract.ArtifactCollector.download", side_effect=fake_download):
        runner = IngestionRunner(config)
        runner.run()
    
    session = self.session_maker()
    try:
        nav_rows = session.execute(select(NAVHistory)).scalars().all()
        self.assertGreaterEqual(len(nav_rows), 1, "No NAV rows in nav_history")
    finally:
        session.close()
```

### Important Notes

1. The tests must use **proper 4-space indentation** within the class
2. Import `SourcePage` and `DiscoveredLink` from `mutual_fund_ingestion.agent.db`
3. Use `database_url=self.db_path` (NOT `f"sqlite:///{self.db_path}"` - the db_path already has the prefix)
4. Add the tests between `test_run_agent_creates_source_pages` and `class ParserUpsertTests`

## Next Steps After R003/R004

After R003/R004 pass:

1. **Epic S (S001-S002)**: Smoke tests for AMFI reachability and NAV discovery
2. **Epic T (T001-T004)**: Final documentation updates
3. **Final verification**: Run full test suite (should reach ~115+ tests)

## File Locations

- Tests: `tests/test_agent_db.py`, `tests/test_agent.py`
- Runner: `mutual_fund_ingestion/agent/runner.py`
- Parsers: `mutual_fund_ingestion/agent/parser/`
- DB models: `mutual_fund_ingestion/agent/db.py`
- Full task list: `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md`

## Running Tests

```bash
cd "/Users/vedaangchopra/all_data/complete_technical_work/all_projects_implemented/Financial Analytics Work"
./financial_env/bin/python -m pytest tests/ -q  # Run all
./financial_env/bin/python -m pytest tests/test_agent_db.py::DBIntegrationTests::test_fixture_seed_page_writes_source_pages -v  # Run R003
./financial_env/bin/python -m pytest tests/test_agent_db.py::DBIntegrationTests::test_fixture_nav_file_upserted_to_nav_history -v  # Run R004
```

## Key Files to Read First

- `plans/TASKS_FULL_SYSTEM_MICRO_PLAN.md` - Full task list
- `tests/test_agent_db.py` - Where to add R003/R004
- `mutual_fund_ingestion/agent/runner.py` - Main runner logic
