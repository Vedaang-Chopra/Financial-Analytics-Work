"""DB-backed integration tests for the task-URL ingestion agent."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from mutual_fund_ingestion.agent.config import AgentConfig
from mutual_fund_ingestion.agent.db import create_tables, get_session_maker
from mutual_fund_ingestion.agent.runner import IngestionRunner
from mutual_fund_ingestion.agent.models import ParserResult
from sqlalchemy import select


class DBIntegrationTests(unittest.TestCase):
    """Integration tests using SQLite in-memory database."""

    def setUp(self):
        """Create a temporary SQLite database for each test."""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.db_path = f"sqlite:///{db_path}"
        self._db_temp_path = db_path  # for tearDown cleanup
        create_tables(self.db_path)
        self.session_maker = get_session_maker(self.db_path)

    def tearDown(self):
        """Clean up temporary database file."""
        if hasattr(self, '_db_temp_path') and self._db_temp_path:
            try:
                os.unlink(self._db_temp_path)
            except OSError:
                pass

    def _count_rows(self, model):
        """Count rows in a table."""
        session = self.session_maker()
        try:
            return session.query(model).count()
        finally:
            session.close()

    def test_init_db_creates_all_tables(self):
        """Verify all 17 tables are created."""
        from mutual_fund_ingestion.agent.db import (
            IngestionRun, TaskURL, SourcePage, DiscoveredLink,
            DatasetCandidate, RawArtifact, AMC, Scheme, NAVHistory,
            Document, Instrument, PortfolioSnapshot, PortfolioHolding,
            StagingRow, ValidationResult, QuarantineRow, RetryQueue
        )
        
        tables = [
            IngestionRun, TaskURL, SourcePage, DiscoveredLink,
            DatasetCandidate, RawArtifact, AMC, Scheme, NAVHistory,
            Document, Instrument, PortfolioSnapshot, PortfolioHolding,
            StagingRow, ValidationResult, QuarantineRow, RetryQueue
        ]
        
        for table in tables:
            count = self._count_rows(table)
            self.assertEqual(count, 0, f"Table {table.__tablename__} should be empty initially")

    def test_run_agent_creates_ingestion_run(self):
        """Test that run-agent creates ingestion_runs row."""
        config = AgentConfig(
            task_urls=["https://example.com/test"],
            database_url=self.db_path,
            max_pages=1,
            max_depth=1,
            dry_run=True,
        )
        runner = IngestionRunner(config)
        result = runner.run()
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["pages_visited"], 1)
        
        # Check ingestion_runs row
        from mutual_fund_ingestion.agent.db import IngestionRun
        session = self.session_maker()
        try:
            runs = session.query(IngestionRun).all()
            self.assertEqual(len(runs), 1)
            run = runs[0]
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.pages_seen, 1)
        finally:
            session.close()

    def test_run_agent_creates_task_urls(self):
        """Test that task_urls rows are created."""
        config = AgentConfig(
            task_urls=["https://example.com/test1", "https://example.com/test2"],
            database_url=self.db_path,
            max_pages=1,
            dry_run=True,
        )
        runner = IngestionRunner(config)
        runner.run()
        
        from mutual_fund_ingestion.agent.db import TaskURL
        session = self.session_maker()
        try:
            task_urls = session.query(TaskURL).all()
            self.assertEqual(len(task_urls), 2)
        finally:
            session.close()

    def test_run_agent_creates_source_pages(self):
        """Test that source_pages rows are created during crawl."""
        config = AgentConfig(
            task_urls=["https://example.com/test"],
            database_url=self.db_path,
            max_pages=1,  # Limit to 1 page to avoid following external links
            dry_run=True,
        )
        runner = IngestionRunner(config)
        runner.run()
        
        from mutual_fund_ingestion.agent.db import SourcePage
        session = self.session_maker()
        try:
            pages = session.query(SourcePage).all()
            self.assertEqual(len(pages), 1)
            page = pages[0]
            self.assertEqual(page.url, "https://example.com/test")
        finally:
            session.close()

    def test_run_agent_creates_retry_queue_on_fetch_failure(self):
        """Test that retry_queue entries are created for failed fetches."""
        config = AgentConfig(
            task_urls=["https://httpstat.us/500"],
            database_url=self.db_path,
            max_pages=1,
            dry_run=True,
        )
        runner = IngestionRunner(config)
        result = runner.run()
        
        from mutual_fund_ingestion.agent.db import RetryQueue
        session = self.session_maker()
        try:
            retries = session.query(RetryQueue).all()
            self.assertEqual(len(retries), 1)
            retry = retries[0]
            self.assertEqual(retry.task_type, "fetch")
            self.assertEqual(retry.status, "pending")
            self.assertTrue(retry.retryable)
        finally:
            session.close()

    def test_run_agent_creates_discovered_links(self):
        """Test that discovered_links are created for extracted links."""
        config = AgentConfig(
            task_urls=["https://example.com/page"],
            database_url=self.db_path,
            max_pages=1,
            dry_run=True,
        )
        runner = IngestionRunner(config)
        
        html_content = '<html><body><a href="https://example.com/link1">Link 1</a></body></html>'
        
        from unittest.mock import patch
        def mock_fetch(url):
            return 200, html_content
        
        with patch.object(runner.discovery, 'fetch', side_effect=mock_fetch):
            runner.run()
        
        from mutual_fund_ingestion.agent.db import DiscoveredLink
        session = self.session_maker()
        try:
            links = session.query(DiscoveredLink).all()
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0].url, "https://example.com/link1")
        finally:
            session.close()

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
        import tempfile
        import os
        from mutual_fund_ingestion.agent.db import NAVHistory
        from sqlalchemy import select
        
        seed_html = (Path(__file__).parent / "fixtures" / "amc_disclosure_page.html").read_text()
        nav_content = (Path(__file__).parent / "fixtures" / "data" / "nav_all_schemes.txt").read_bytes()
        
        # Create a temp file with the nav content for the mock to return as local_path
        fd, temp_nav_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        Path(temp_nav_path).write_bytes(nav_content)
        
        def fake_fetch(url):
            return (200, seed_html)
        
        def fake_download(url, run_id):
            if "nav_all_schemes" in url:
                return {
                    "url": url, "file_type": "text", "content_type": "text/plain",
                    "checksum": "abc123", "size_bytes": len(nav_content),
                    "local_path": temp_nav_path, "retained": False, "content": nav_content
                }
            return {"error": "not found"}
        
        config = AgentConfig(
            task_urls=["https://fixture.amc.com/"],
            database_url=self.db_path,
            max_pages=2, max_files=1, use_browser=False,
        )
        try:
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
        finally:
            # Cleanup temp file
            if os.path.exists(temp_nav_path):
                os.unlink(temp_nav_path)


    def test_raw_artifact_retained_flag_set_when_keep_raw_files_true(self):
        """L002: ArtifactProcessor sets retained=True and writes to raw_dir when configured."""
        import unittest.mock as mock
        import os
        from mutual_fund_ingestion.agent.db import RawArtifact
        from mutual_fund_ingestion.agent.artifact_processor import ArtifactProcessor
        from mutual_fund_ingestion.agent.upserts import UpsertManager
        from mutual_fund_ingestion.agent.extract import ArtifactCollector
        from pathlib import Path
        import uuid

        # Create a real temp file for the download
        fd, temp_path = tempfile.mkstemp(suffix=".txt")
        os.write(fd, b"SCHEME_CODE\tNAV_DATE\tNAV\nABC123\t16-Jun-2026\t52.00\n")
        os.close(fd)

        raw_dir = Path(tempfile.mkdtemp())

        try:
            collector = mock.MagicMock(spec=ArtifactCollector)
            collector.download.return_value = {
                "url": "https://example.com/nav.txt",
                "file_type": "txt",
                "content_type": "text/plain",
                "checksum": "abc123",
                "size_bytes": 45,
                "local_path": temp_path,
                "retained": True,
            }

            run_id = str(uuid.uuid4())
            upsert_manager = UpsertManager()
            upsert_manager.set_run_id(run_id)

            processor = ArtifactProcessor(
                run_id=run_id,
                stats={"files_downloaded": 0},
                collector=collector,
                upsert_manager=upsert_manager,
            )

            from mutual_fund_ingestion.agent.db import DatasetCandidate
            session = self.session_maker()
            try:
                dc = DatasetCandidate(
                    run_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    url="https://example.com/nav.txt",
                    dataset_type="nav_history",
                    file_type="txt",
                    status="discovered",
                    requires_browser=False,
                    requires_form=False,
                    requires_vlm=False,
                    confidence=0.8,
                )
                session.add(dc)
                session.flush()

                processor.process(session, dc, raw_dir=raw_dir)
                session.commit()

                artifacts = session.query(RawArtifact).filter_by(checksum="abc123").all()
                self.assertEqual(len(artifacts), 1)
                self.assertTrue(artifacts[0].retained)
                self.assertIsNotNone(artifacts[0].local_path)
            finally:
                session.close()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            import shutil
            if raw_dir.exists():
                shutil.rmtree(raw_dir)


class ParserUpsertTests(unittest.TestCase):
    """Tests for parser upserts to canonical tables."""

    def setUp(self):
        self.db_path = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
        create_tables(self.db_path)
        self.session_maker = get_session_maker(self.db_path)

    def tearDown(self):
        if hasattr(self, "db_path"):
            path = self.db_path.replace("sqlite:///", "")
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_nav_parser_upserts_to_nav_history(self):
        """Test that NAV parser results are upserted to nav_history table."""
        from mutual_fund_ingestion.agent.db import Scheme, NAVHistory, AMC
        from utils.text_utils import normalize_amc_name
        
        # Create scheme first
        session = self.session_maker()
        try:
            amc = AMC(name="HDFC Mutual Fund", normalized_name=normalize_amc_name("HDFC Mutual Fund"))
            session.add(amc)
            session.flush()
            
            scheme = Scheme(
                amc_id=amc.id,
                scheme_code="HDFC123",
                scheme_name="HDFC Top 100 Fund",
                normalized_scheme_name=normalize_amc_name("HDFC Top 100 Fund"),
            )
            session.add(scheme)
            session.flush()
            scheme_id = scheme.id
            session.commit()
        finally:
            session.close()
        
        # Parse NAV content directly
        from mutual_fund_ingestion.agent.parser.nav import parse_nav_text
        nav_content = "SCHEME_CODE\tNAV_DATE\tNAV\nHDFC123\t14-Jun-2025\t31.456\n"
        parser_result = parse_nav_text(nav_content, {"source_url": "https://test.com/nav.txt"})
        result = parse_nav_text(nav_content, {"source_url": "https://test.com/nav.txt"})
        
        # Manually upsert to nav_history (simulating what runner does)
        from datetime import date
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy.dialects.postgresql import insert
        
        session = self.session_maker()
        try:
            for record in result.records:
                from mutual_fund_ingestion.agent.db import NAVHistory
                from datetime import date
                obj = NAVHistory(
                    scheme_id=scheme_id,
                    scheme_code=record["scheme_code"],
                    nav_date=date.fromisoformat(record["nav_date"]),
                    nav_value=record["nav_value"],
                    source_url=record["source_url"],
                )
                session.merge(obj)
            session.commit()
        finally:
            session.close()
        
        # Verify
        session = self.session_maker()
        try:
            nav_rows = session.query(NAVHistory).all()
            self.assertEqual(len(nav_rows), 1)
            nav = nav_rows[0]
            self.assertEqual(nav.scheme_code, "HDFC123")
            self.assertEqual(float(nav.nav_value), 31.456)
            self.assertEqual(nav.scheme_id, scheme_id)
        finally:
            session.close()

    def test_amc_parser_upserts_to_amcs(self):
        """Test that AMC parser results are upserted to amcs table."""
        from mutual_fund_ingestion.agent.parser.amc import parse_amc_html
        from mutual_fund_ingestion.agent.db import AMC
        from sqlalchemy.dialects.postgresql import insert
        from utils.text_utils import normalize_amc_name
        
        amc_html = '<html><body><a href="https://hdfc.com/mf">HDFC Mutual Fund</a></body></html>'
        result = parse_amc_html(amc_html, {"source_url": "https://test.com"})
        
        session = self.session_maker()
        try:
            for record in result.records:
                normalized = normalize_amc_name(record["name"])
                from mutual_fund_ingestion.agent.db import AMC
                obj = AMC(
                    name=record["name"],
                    normalized_name=normalized,
                    website_url=record.get("website_url"),
                    source_url=record["source_url"],
                )
                session.merge(obj)
            session.commit()
        finally:
            session.close()
        
        session = self.session_maker()
        try:
            amcs = session.query(AMC).all()
            self.assertEqual(len(amcs), 1)
            self.assertEqual(amcs[0].name, "HDFC Mutual Fund")
        finally:
            session.close()

    def test_scheme_master_parser_upserts_to_schemes(self):
        """Test that scheme master parser results are upserted to schemes table."""
        from mutual_fund_ingestion.agent.parser.scheme_master import parse_scheme_master_csv
        from mutual_fund_ingestion.agent.db import Scheme, AMC
        from sqlalchemy.dialects.postgresql import insert
        from utils.text_utils import normalize_amc_name
        
        # Create AMC first
        session = self.session_maker()
        try:
            amc = AMC(name="HDFC Mutual Fund", normalized_name=normalize_amc_name("HDFC Mutual Fund"))
            session.add(amc)
            session.flush()
            amc_id = amc.id
            session.commit()
        finally:
            session.close()
        
        scheme_csv = "Scheme Code,Scheme Name,AMC Name,Category\n123,Test Fund,HDFC Mutual Fund,Equity\n"
        result = parse_scheme_master_csv(scheme_csv, {"source_url": "https://test.com/scheme_master.csv"})
        
        session = self.session_maker()
        try:
            for record in result.records:
                normalized = normalize_amc_name(record["scheme_name"])
                from mutual_fund_ingestion.agent.db import Scheme
                obj = Scheme(
                    amc_id=amc_id,
                    scheme_code=record.get("scheme_code"),
                    scheme_name=record["scheme_name"],
                    normalized_scheme_name=normalized,
                    category=record.get("category"),
                    sub_category=record.get("sub_category"),
                )
                session.merge(obj)
            session.commit()
        finally:
            session.close()
        
        session = self.session_maker()
        try:
            schemes = session.query(Scheme).all()
            self.assertEqual(len(schemes), 1)
            self.assertEqual(schemes[0].scheme_name, "Test Fund")
            self.assertEqual(schemes[0].amc_id, amc_id)
        finally:
            session.close()

    def test_portfolio_parser_creates_holdings(self):
        """Test that portfolio parser creates portfolio_snapshots and holdings."""
        from mutual_fund_ingestion.agent.parser.portfolio import parse_portfolio_excel
        from mutual_fund_ingestion.agent.db import (
            AMC, Scheme, PortfolioSnapshot, PortfolioHolding, Instrument
        )
        from sqlalchemy.dialects.postgresql import insert
        from utils.text_utils import normalize_amc_name
        from datetime import date
        import io
        import pandas as pd
        
        # Create AMC and scheme first
        session = self.session_maker()
        try:
            amc = AMC(name="Test AMC", normalized_name=normalize_amc_name("Test AMC"))
            session.add(amc)
            session.flush()
            
            scheme = Scheme(
                amc_id=amc.id,
                scheme_code="TEST001",
                scheme_name="Test Fund",
                normalized_scheme_name=normalize_amc_name("Test Fund"),
            )
            session.add(scheme)
            session.flush()
            scheme_id = scheme.id
            session.commit()
        finally:
            session.close()
        
        # Create test Excel content in memory
        df = pd.DataFrame({
            "security_name": ["Reliance Industries", "TCS"],
            "isin": ["INE002A01018", "INE467B01029"],
            "sector": ["Oil & Gas", "IT"],
            "percentage_to_nav": [10.5, 8.2],
            "market_value": [10000000, 8000000],
        })
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)  # type: ignore[arg-type]
        excel_content = buffer.getvalue()
        
        # Parse
        result = parse_portfolio_excel(excel_content, {"source_url": "https://test.com/portfolio.xlsx"})
        
        # Create snapshot and holdings
        session = self.session_maker()
        try:
            snapshot = PortfolioSnapshot(
                scheme_id=scheme_id,
                reporting_date=date.today(),
                source_url="https://test.com/portfolio.xlsx",
                parser_version="portfolio_excel_v1",
                validation_status="validated",
            )
            session.add(snapshot)
            session.flush()
            
            for record in result.records:
                # Create instrument
                isin = record.get("isin")
                if isin:
                    instrument = session.query(Instrument).filter_by(isin=isin).first()
                    if not instrument:
                        instrument = Instrument(
                            isin=isin,
                            name=record["security_name"],
                            normalized_name=normalize_amc_name(record["security_name"]),
                            sector=record.get("sector"),
                        )
                        session.add(instrument)
                        session.flush()
                    instrument_id = instrument.id
                else:
                    instrument = Instrument(
                        name=record["security_name"],
                        normalized_name=normalize_amc_name(record["security_name"]),
                        sector=record.get("sector"),
                    )
                    session.add(instrument)
                    session.flush()
                    instrument_id = instrument.id
                
                holding = PortfolioHolding(
                    snapshot_id=snapshot.id,
                    instrument_id=instrument_id,
                    security_name=record["security_name"],
                    isin=record.get("isin"),
                    sector=record.get("sector"),
                    asset_class=record.get("asset_class"),
                    percentage_to_nav=record.get("percentage_to_nav"),
                    market_value=record.get("market_value"),
                )
                session.add(holding)
            
            session.commit()
        finally:
            session.close()
        
        session = self.session_maker()
        try:
            snapshots = session.query(PortfolioSnapshot).all()
            self.assertEqual(len(snapshots), 1)
            
            holdings = session.query(PortfolioHolding).all()
            self.assertEqual(len(holdings), 2)
        finally:
            session.close()


class ValidationQuarantineTests(unittest.TestCase):
    """Tests for validation and quarantine."""

    def setUp(self):
        self.db_path = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
        create_tables(self.db_path)
        self.session_maker = get_session_maker(self.db_path)

    def tearDown(self):
        if hasattr(self, "db_path"):
            path = self.db_path.replace("sqlite:///", "")
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_validation_creates_validation_results(self):
        """Test that validation creates validation_results rows."""
        from mutual_fund_ingestion.agent.validate import validate_nav_record, write_validation_result
        from mutual_fund_ingestion.agent.db import ValidationResult
        import uuid
        
        run_id = str(uuid.uuid4())
        
        # Valid record
        record = {"scheme_code": "ABC", "nav_date": "2024-01-01", "nav_value": 100, "source_url": "https://test.com"}
        errors = validate_nav_record(record)
        self.assertEqual(errors, [])
        
        vr = write_validation_result(run_id, "nav_history", None, "schema_validation", "info", "passed", "OK")
        self.assertEqual(vr["status"], "passed")
        
        # Invalid record
        record = {"nav_value": -10}
        errors = validate_nav_record(record)
        self.assertIn("nav_value_not_positive", errors)
        
        vr = write_validation_result(run_id, "nav_history", None, "schema_validation", "error", "failed", "nav_value_not_positive")
        self.assertEqual(vr["status"], "failed")

    def test_quarantine_for_invalid_records(self):
        """Test that invalid records go to quarantine_rows."""
        from mutual_fund_ingestion.agent.validate import write_quarantine_row
        from mutual_fund_ingestion.agent.db import QuarantineRow
        import uuid
        
        run_id = str(uuid.uuid4())
        
        q = write_quarantine_row(run_id, "missing_scheme_code", {"nav_value": 100}, None, False)
        self.assertEqual(q["reason"], "missing_scheme_code")
        self.assertFalse(q["retryable"])
        
        # Write to DB
        session = self.session_maker()
        try:
            qr = QuarantineRow(
                run_id=uuid.UUID(run_id),
                dataset_type="nav_history",
                reason="missing_scheme_code",
                raw_data_json={"nav_value": 100},
                retryable=False,
            )
            session.add(qr)
            session.commit()
        finally:
            session.close()
        
        session = self.session_maker()
        try:
            quarantine = session.query(QuarantineRow).all()
            self.assertEqual(len(quarantine), 1)
            self.assertIn("missing_scheme_code", quarantine[0].reason)
        finally:
            session.close()

    def test_staging_rows_created(self):
        """Test that staging_rows are created for parsed records."""
        from mutual_fund_ingestion.agent.db import StagingRow, RawArtifact
        import uuid
        
        run_id = str(uuid.uuid4())
        
        session = self.session_maker()
        try:
            # Create raw artifact first
            artifact = RawArtifact(
                run_id=uuid.UUID(run_id),
                source_url="https://test.com/nav.txt",
                artifact_type="file",
                file_type="txt",
            )
            session.add(artifact)
            session.flush()
            
            # Create staging rows
            for i in range(3):
                sr = StagingRow(
                    run_id=uuid.UUID(run_id),
                    raw_artifact_id=artifact.id,
                    dataset_type="nav_history",
                    row_number=i + 1,
                    raw_row_json={"scheme_code": f"ABC{i}", "nav_value": 100 + i},
                    parsed_fields_json={"scheme_code": f"ABC{i}", "nav_value": 100 + i},
                    parser_name="nav_text_v1",
                    parser_confidence=0.85,
                )
                session.add(sr)
            session.commit()
        finally:
            session.close()
        
        session = self.session_maker()
        try:
            staging = session.query(StagingRow).all()
            self.assertEqual(len(staging), 3)
            for s in staging:
                self.assertEqual(s.dataset_type, "nav_history")
                self.assertIsNotNone(s.parsed_fields_json)
                # G005: raw_row_json must preserve original parsed record
                self.assertIsNotNone(s.raw_row_json)
                self.assertIn("scheme_code", s.raw_row_json)
                self.assertIn("nav_value", s.raw_row_json)
        finally:
            session.close()

    def test_quarantine_reason_is_non_empty(self):
        """G006: Every quarantine row has a non-empty reason when validation fails."""
        from mutual_fund_ingestion.agent.validate import validate_and_filter_records
        from mutual_fund_ingestion.agent.models import ParserResult
        import uuid

        run_id = str(uuid.uuid4())

        # Inject invalid NAV record (missing scheme_code, nav_date)
        parser_result = ParserResult(
            dataset_type="nav_history",
            parser_name="nav_text_v1",
            parser_version="1.0",
            confidence=0.9,
            records=[
                {"nav_value": "100.50"},  # invalid: missing scheme_code, nav_date, source_url
            ],
            warnings=[],
            errors=[],
            metadata={},
        )

        valid, quarantined = validate_and_filter_records(parser_result, run_id)

        self.assertEqual(len(valid), 0)
        self.assertEqual(len(quarantined), 1)
        # G006: reason must be non-empty string
        self.assertIsInstance(quarantined[0]["reason"], str)
        self.assertGreater(len(quarantined[0]["reason"]), 0)
        # Raw data preserved in quarantine row
        self.assertIsNotNone(quarantined[0]["raw_data_json"])


class ParserUnitTests(unittest.TestCase):
    """Unit tests for individual parsers."""

    def test_nav_text_parser(self):
        from mutual_fund_ingestion.agent.parser.nav import parse_nav_text
        content = "SCHEME_CODE\tNAV_DATE\tNAV\nABC123\t14-Jun-2025\t31.456"
        result = parse_nav_text(content, {"source_url": "https://test.com"})
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["scheme_code"], "ABC123")
        self.assertEqual(float(result.records[0]["nav_value"]), 31.456)

    def test_amc_html_parser(self):
        from mutual_fund_ingestion.agent.parser.amc import parse_amc_html
        html = '<a href="https://hdfc.com">HDFC Mutual Fund</a>'
        result = parse_amc_html(html, {"source_url": "https://test.com"})
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["name"], "HDFC Mutual Fund")

    def test_scheme_master_csv_parser(self):
        from mutual_fund_ingestion.agent.parser.scheme_master import parse_scheme_master_csv
        content = "Scheme Code,Scheme Name,AMC Name,Category\n123,Test Fund,HDFC Mutual Fund,Equity"
        result = parse_scheme_master_csv(content, {"source_url": "https://test.com"})
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["scheme_code"], "123")
        self.assertEqual(result.records[0]["amc_name"], "HDFC Mutual Fund")

    def test_validation_passes_valid_nav(self):
        from mutual_fund_ingestion.agent.validate import validate_nav_record
        record = {"scheme_code": "ABC", "nav_date": "2024-01-01", "nav_value": 100, "source_url": "https://test.com"}
        errors = validate_nav_record(record)
        self.assertEqual(errors, [])

    def test_validation_fails_invalid_nav(self):
        from mutual_fund_ingestion.agent.validate import validate_nav_record
        record = {"scheme_code": "ABC", "nav_date": "2024-01-01", "nav_value": -10, "source_url": "https://test.com"}
        errors = validate_nav_record(record)
        self.assertIn("nav_value_not_positive", errors)

    def test_quarantine_row_creation(self):
        from mutual_fund_ingestion.agent.validate import write_quarantine_row
        q = write_quarantine_row("run-1", "missing_scheme_code", {"nav_value": 100}, None, False)
        self.assertEqual(q["reason"], "missing_scheme_code")
        self.assertFalse(q["retryable"])

    def test_route_parser_includes_scheme_master(self):
        from mutual_fund_ingestion.agent.parser import route_parser
        self.assertEqual(route_parser("scheme_master", "csv"), "scheme_master_csv")
        self.assertEqual(route_parser("scheme_master", "html"), "scheme_master_html")


class DatabaseSchemaTests(unittest.TestCase):
    """Schema verification tests for DB constraints and indexes."""

    def setUp(self):
        self.db_path = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
        create_tables(self.db_path)
        self.session_maker = get_session_maker(self.db_path)

    def tearDown(self):
        if hasattr(self, "db_path"):
            path = self.db_path.replace("sqlite:///", "")
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_nav_history_has_scheme_code_nav_date_index(self):
        """F002: Verify nav_history has index on (scheme_code, nav_date)."""
        import sqlite3
        from mutual_fund_ingestion.agent.db import NAVHistory
        # Check the model has the index defined
        self.assertTrue(hasattr(NAVHistory, '__table_args__'))
        # Check SQLite creates the indexes
        db_file = self.db_path.replace("sqlite:///", "")
        conn = sqlite3.connect(db_file)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='nav_history'"
        ).fetchall()
        conn.close()
        index_names = [idx[0] for idx in indexes]
        has_composite = any(
            "scheme_code" in name and "nav_date" in name for name in index_names
        )
        self.assertTrue(has_composite, f"No composite index on nav_history. Found: {index_names}")

    def test_amc_normalized_name_is_unique(self):
        """F003: Verify amcs.normalized_name has unique constraint enforced."""
        from sqlalchemy.exc import IntegrityError
        from mutual_fund_ingestion.agent.db import AMC
        from utils.text_utils import normalize_amc_name
        
        session = self.session_maker()
        try:
            amc1 = AMC(name="Example Fund", normalized_name="example_fund", source_url="http://a.com")
            session.add(amc1)
            session.flush()
            
            amc2 = AMC(name="Example Fund 2", normalized_name="example_fund", source_url="http://b.com")
            session.add(amc2)
            with self.assertRaises(IntegrityError):
                session.flush()
        finally:
            session.close()


class ArtifactCollectorTests(unittest.TestCase):
    """Tests for ArtifactCollector behavior."""

    def test_download_rejects_oversized_file_by_content_length(self):
        """L003: Verify download returns file_too_large when content-length exceeds limit."""
        from mutual_fund_ingestion.agent.extract import ArtifactCollector
        import unittest.mock as mock
        from utils.http import HttpSettings
        from pathlib import Path
        import tempfile
        
        collector = ArtifactCollector(
            session=mock.MagicMock(),
            temp_dir=Path(tempfile.mkdtemp()),
            max_file_size_mb=0.001,  # 1KB limit
        )
        fake_response = mock.MagicMock()
        fake_response.headers = {"content-length": "999999999"}
        fake_response.raise_for_status.return_value = None
        mock_session_get = collector.session.get
        cast(Any, collector.session).get.return_value = fake_response
        
        result = collector.download("https://example.com/huge.txt", "test-run")
        self.assertEqual(result["error"], "file_too_large")


    def test_download_returns_download_failed_on_request_exception(self):
        """ArtifactCollector returns download_failed on requests errors."""
        from mutual_fund_ingestion.agent.extract import ArtifactCollector
        import unittest.mock as mock
        from pathlib import Path
        import tempfile
        import requests

        collector = ArtifactCollector(
            session=mock.MagicMock(),
            temp_dir=Path(tempfile.mkdtemp()),
            max_file_size_mb=1.0,
        )
        collector.session.get.side_effect = requests.RequestException("network error")

        result = collector.download("https://example.com/fail.txt", "test-run")
        self.assertEqual(result["error"], "download_failed")
        self.assertIn("network error", result["reason"])

    def test_download_returns_unknown_on_unexpected_exception(self):
        """ArtifactCollector returns unknown on unexpected errors."""
        from mutual_fund_ingestion.agent.extract import ArtifactCollector
        import unittest.mock as mock
        from pathlib import Path
        import tempfile

        collector = ArtifactCollector(
            session=mock.MagicMock(),
            temp_dir=Path(tempfile.mkdtemp()),
            max_file_size_mb=1.0,
        )
        collector.session.get.side_effect = RuntimeError("boom")

        result = collector.download("https://example.com/boom.txt", "test-run")
        self.assertEqual(result["error"], "unknown")
        self.assertIn("boom", result["reason"])


if __name__ == "__main__":
    unittest.main()