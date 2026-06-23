"""Bounded live smoke tests. Run with: python -m pytest -m smoke tests/"""
import os
import tempfile
import unittest

import pytest

from mutual_fund_ingestion.agent.config import AgentConfig
from mutual_fund_ingestion.agent.db import create_tables, get_session_maker, IngestionRun, SourcePage
from mutual_fund_ingestion.agent.runner import IngestionRunner


def _check_network():
    import requests

    try:
        requests.get("https://www.amfiindia.com", timeout=5)
        return True
    except Exception:
        return False


@pytest.mark.smoke
def test_smoke_amfi_seed_page_reachable():
    """Verify AMFI is reachable and agent can fetch and process one page."""
    if not _check_network():
        pytest.skip("Network unavailable")
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        create_tables(f"sqlite:///{db_path}")
        config = AgentConfig(
            task_urls=["https://www.amfiindia.com"],
            database_url=f"sqlite:///{db_path}",
            max_pages=1,
            max_files=0,
            use_browser=False,
        )
        runner = IngestionRunner(config)
        result = runner.run()

        assert result["status"] == "completed", f"Run failed: {result}"
        assert result["pages_visited"] >= 1, f"No pages visited: {result}"
    finally:
        os.unlink(db_path)


@pytest.mark.smoke
def test_smoke_amfi_discovers_nav_candidate():
    """Verify bounded run discovers at least one nav_history DatasetCandidate."""
    if not _check_network():
        pytest.skip("Network unavailable")
    from sqlalchemy import select

    from mutual_fund_ingestion.agent.db import DatasetCandidate

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        create_tables(f"sqlite:///{db_path}")
        config = AgentConfig(
            task_urls=["https://www.amfiindia.com/spages/NAVAll.txt"],
            database_url=f"sqlite:///{db_path}",
            max_pages=1,
            max_files=0,
            use_browser=False,
        )
        runner = IngestionRunner(config)
        runner.run()

        session_maker = get_session_maker(f"sqlite:///{db_path}")
        session = session_maker()
        try:
            candidates = session.execute(select(DatasetCandidate)).scalars().all()
            nav_candidates = [c for c in candidates if c.dataset_type == "nav_history"]
            assert len(nav_candidates) >= 1, (
                f"No nav_history candidates found. All: {[c.dataset_type for c in candidates]}"
            )
        finally:
            session.close()
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])