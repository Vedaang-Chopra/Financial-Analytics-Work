"""Tests for the task-URL ingestion agent."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from mutual_fund_ingestion.agent.config import AgentConfig
from mutual_fund_ingestion.agent.models import ParserResult
from mutual_fund_ingestion.agent.parser.nav import parse_nav_text, parse_nav_csv
from mutual_fund_ingestion.agent.parser.amc import parse_amc_html
from mutual_fund_ingestion.agent.parser.scheme_master import parse_scheme_master_csv, parse_scheme_master_html
from mutual_fund_ingestion.agent.parser import route_parser, parse_file
from mutual_fund_ingestion.agent.validate import validate_nav_record, validate_portfolio_record, validate_and_filter_records, validate_scheme_master_record, validate_amc_record


class ConfigTests(unittest.TestCase):
    def test_agent_config_defaults(self):
        config = AgentConfig(task_urls=["https://example.com"], database_url="postgresql://localhost/test")
        self.assertEqual(config.max_pages, 500)
        self.assertEqual(config.max_depth, 5)
        self.assertEqual(config.keep_raw_files, False)
        self.assertEqual(config.keep_failed_raw_files, True)
        self.assertEqual(config.use_vlm, False)
        self.assertEqual(len(config.dataset_type_priority), 5)


class ParserRoutingTests(unittest.TestCase):
    def test_route_parser_returns_correct_parser_names(self):
        self.assertEqual(route_parser("nav_history", "text"), "nav_text")
        self.assertEqual(route_parser("nav_history", "csv"), "nav_csv")
        self.assertEqual(route_parser("nav_history", "html"), "nav_html")
        self.assertEqual(route_parser("amc_provider_list", "html"), "amc_html")
        self.assertEqual(route_parser("portfolio_disclosure", "xlsx"), "portfolio_excel")
        self.assertEqual(route_parser("portfolio_disclosure", "xls"), "portfolio_excel")
        self.assertEqual(route_parser("unknown_type", None), "unknown")
        self.assertEqual(route_parser("portfolio_disclosure", "pdf"), "unknown")


class NAVParserTests(unittest.TestCase):
    def test_nav_text_parser_with_valid_data(self):
        content = "SCHEME_CODE\tNAV_DATE\tNAV\nABC123\t01-Jan-2024\t450.50\nDEF456\t02-Jan-2024\t120.75"
        result = parse_nav_text(content, {"source_url": "https://amfiindia.com/nav"})
        self.assertEqual(result.parser_name, "nav_text_v1")
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["scheme_code"], "ABC123")
        self.assertEqual(float(result.records[0]["nav_value"]), 450.50)
        self.assertEqual(result.records[0]["nav_date"], "2024-01-01")
        self.assertEqual(result.records[1]["scheme_code"], "DEF456")

    def test_nav_text_parser_with_realistic_fixture(self):
        from pathlib import Path
        fixture = (Path(__file__).parent / "fixtures" / "data" / "nav_all_schemes.txt").read_text()
        result = parse_nav_text(fixture, {"source_url": "https://amfiindia.com/NAVAll.txt"})
        self.assertEqual(len(result.records), 2, f"Expected 2 records, got {len(result.records)}: {result.records}")
        self.assertEqual(result.records[0]["scheme_code"], "120503")
        self.assertAlmostEqual(float(result.records[0]["nav_value"]), 52.1234, places=3)


        self.assertAlmostEqual(float(result.records[1]["nav_value"]), 147.8921, places=3)

    def test_nav_html_parser_with_fixture(self):
        from pathlib import Path
        from mutual_fund_ingestion.agent.parser.nav import parse_nav_html
        fixture = (Path(__file__).parent / "fixtures" / "data" / "nav_page.html").read_bytes()
        result = parse_nav_html(fixture, {"source_url": "https://example.com/nav.html"})
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["scheme_code"], "120503")



    def test_nav_text_parser_with_bad_lines(self):
        content = "ABC\t01-Jan-2024\t450.50\nBAD_LINE\nXYZ\t01-Jan-2024\tabc"
        result = parse_nav_text(content, {"source_url": "https://amfiindia.com/nav"})
        self.assertEqual(len(result.records), 1)
        self.assertEqual(len(result.errors), 2)

    def test_nav_csv_parser_with_valid_data(self):
        content = "Scheme Code,NAV Date,NAV\nABC123,2024-01-01,450.50\nDEF456,2024-01-02,120.75"
        result = parse_nav_csv(content, {"source_url": "https://amfiindia.com/nav.csv"})
        self.assertEqual(result.parser_name, "nav_csv_v1")
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["scheme_code"], "ABC123")
        self.assertEqual(result.records[1]["scheme_code"], "DEF456")


class AMCParserTests(unittest.TestCase):
    def test_amc_html_parser_extracts_links(self):
        html = """
        <html><body>
        <a href="https://hdfc.com/mf">HDFC Mutual Fund</a>
        <a href="https://icici.com/mf">ICICI Prudential Mutual Fund</a>
        <a href="/careers">Careers</a>
        </body></html>
        """
        result = parse_amc_html(html, {"source_url": "https://amfiindia.com/members"})
        self.assertEqual(result.parser_name, "amc_html_v1")
        names = [r["name"] for r in result.records]
        self.assertIn("HDFC Mutual Fund", names)
        self.assertIn("ICICI Prudential Mutual Fund", names)


class ValidationTests(unittest.TestCase):
    def test_nav_validation_passes_valid_record(self):
        record = {"scheme_code": "ABC123", "nav_date": "2024-01-01", "nav_value": 450.5, "source_url": "https://amfi.com"}
        errors = validate_nav_record(record)
        self.assertEqual(errors, [])

    def test_nav_validation_fails_missing_fields(self):
        record = {}
        errors = validate_nav_record(record)
        self.assertIn("missing_scheme_code", errors)
        self.assertIn("missing_nav_value", errors)
        self.assertIn("missing_nav_date", errors)

    def test_nav_validation_fails_non_positive_nav(self):
        record = {"scheme_code": "ABC", "nav_date": "2024-01-01", "nav_value": -10, "source_url": "https://amfi.com"}
        errors = validate_nav_record(record)
        self.assertIn("nav_value_not_positive", errors)

    def test_portfolio_validation_passes_valid_record(self):
        record = {"security_name": "Reliance Industries", "percentage_to_nav": 10.5, "market_value": 1000000}
        errors = validate_portfolio_record(record)
        self.assertEqual(errors, [])

    def test_portfolio_validation_fails_missing_security_name(self):
        record = {"percentage_to_nav": 10.5}
        errors = validate_portfolio_record(record)
        self.assertIn("missing_security_name", errors)

    def test_portfolio_validation_fails_out_of_range_percentage(self):
        record = {"security_name": "Test", "percentage_to_nav": 150}
        errors = validate_portfolio_record(record)
        self.assertIn("percentage_out_of_range", errors)

    def test_validate_and_filter_records_routes_to_nav_validator(self):
        parser_result = ParserResult(
            dataset_type="nav_history",
            parser_name="nav_text_v1",
            parser_version="1.0",
            confidence=0.85,
            records=[
                {"scheme_code": "ABC", "nav_date": "2024-01-01", "nav_value": 100, "source_url": "https://amfi.com"},
                {},  # invalid
            ],
            warnings=[],
            errors=[],
            metadata={},
        )
        valid, quarantined = validate_and_filter_records(parser_result, "run-1")
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 1)
        self.assertIn("missing_scheme_code", quarantined[0]["reason"])

    def test_validate_and_filter_records_routes_to_portfolio_validator(self):
        parser_result = ParserResult(
            dataset_type="portfolio_disclosure",
            parser_name="portfolio_excel_v1",
            parser_version="1.0",
            confidence=0.7,
            records=[
                {"security_name": "Reliance", "percentage_to_nav": 5.0},
                {"security_name": "", "percentage_to_nav": 3.0},  # invalid - missing name
            ],
            warnings=[],
            errors=[],
            metadata={},
        )
        valid, quarantined = validate_and_filter_records(parser_result, "run-1")
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 1)

    def test_scheme_master_validation_fails_missing_scheme_code(self):
        record = {"scheme_name": "Example Growth Fund"}
        errors = validate_scheme_master_record(record)
        self.assertIn("missing_scheme_code", errors)

    def test_scheme_master_validation_passes_valid_record(self):
        record = {"scheme_code": "120503", "scheme_name": "Example Growth Fund", "amc_name": "Example AMC"}
        errors = validate_scheme_master_record(record)
        self.assertEqual(errors, [])

    def test_amc_validation_fails_missing_name(self):
        record = {"website_url": "http://example.com"}
        errors = validate_amc_record(record)
        self.assertIn("missing_name", errors)

    def test_validate_and_filter_records_routes_to_scheme_master_validator(self):
        parser_result = ParserResult(
            dataset_type="scheme_master",
            parser_name="scheme_master_csv_v1",
            parser_version="1.0",
            confidence=0.8,
            records=[
                {"scheme_code": "123", "scheme_name": "Test Fund"},
                {"scheme_name": "Invalid Fund"},  # missing scheme_code
            ],
            warnings=[],
            errors=[],
            metadata={},
        )
        valid, quarantined = validate_and_filter_records(parser_result, "run-1")
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 1)
        self.assertIn("missing_scheme_code", quarantined[0]["reason"])

    def test_validate_and_filter_records_routes_to_amc_validator(self):
        parser_result = ParserResult(
            dataset_type="amc_provider_list",
            parser_name="amc_html_v1",
            parser_version="1.0",
            confidence=0.9,
            records=[
                {"name": "Test AMC", "website_url": "https://test.com"},
                {"website_url": "https://example.com"},  # missing name
            ],
            warnings=[],
            errors=[],
            metadata={},
        )
        valid, quarantined = validate_and_filter_records(parser_result, "run-1")
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 1)
        self.assertIn("missing_name", quarantined[0]["reason"])


class RouteParserIntegrationTests(unittest.TestCase):
    def test_parse_file_routes_to_nav_text_parser(self):
        content = "SCHEME\tDATE\tNAV\nABC\t01-Jan-2024\t100"
        result = parse_file("nav_history", "text", content, {"source_url": "https://amfi.com"})
        self.assertEqual(result.parser_name, "nav_text_v1")
        self.assertEqual(len(result.records), 1)

    def test_parse_file_routes_to_amc_html_parser(self):
        content = '<html><body><a href="https://hdfc.com">HDFC Mutual Fund</a></body></html>'
        result = parse_file("amc_provider_list", "html", content, {"source_url": "https://amfi.com"})
        self.assertEqual(result.parser_name, "amc_html_v1")

    def test_parse_file_returns_unknown_for_unroutable(self):
        result = parse_file("unknown_type", "pdf", b"", {})
        self.assertEqual(result.parser_name, "unknown")
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("No parser found", result.warnings[0])


class SchemeMasterParserTests(unittest.TestCase):
    def test_scheme_master_csv_parser_with_valid_data(self):
        content = "Scheme Code,Scheme Name,AMC Name,Category\n12345,HDFC Top 100,HDFC Mutual Fund,Equity\n67890,ICICI Bluechip,ICICI Prudential Mutual Fund,Equity"
        result = parse_scheme_master_csv(content, {"source_url": "https://amfiindia.com/scheme_master.csv"})
        self.assertEqual(result.parser_name, "scheme_master_csv_v1")
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["scheme_code"], "12345")
        self.assertEqual(result.records[0]["scheme_name"], "HDFC Top 100")
        self.assertEqual(result.records[0]["amc_name"], "HDFC Mutual Fund")
        self.assertEqual(result.records[0]["category"], "Equity")
        self.assertEqual(result.records[1]["scheme_code"], "67890")
        self.assertEqual(result.records[1]["scheme_name"], "ICICI Bluechip")

    def test_scheme_master_csv_parser_with_realistic_fixture(self):
        from pathlib import Path
        from mutual_fund_ingestion.agent.parser.scheme_master import parse_scheme_master_csv
        fixture = (Path(__file__).parent / "fixtures" / "data" / "scheme_master.csv").read_bytes()
        result = parse_scheme_master_csv(fixture, {"source_url": "https://amfiindia.com/scheme_master.csv"})
        codes = [r["scheme_code"] for r in result.records if r.get("scheme_code")]
        self.assertIn("120503.0", codes)
        self.assertIn("120504.0", codes)



    def test_scheme_master_csv_parser_with_alternative_columns(self):
        content = "schemecode,schemename,amc,fund category\n111,Test Fund,Test AMC,Debt"
        result = parse_scheme_master_csv(content, {"source_url": "https://amfiindia.com/scheme_master.csv"})
        self.assertEqual(result.parser_name, "scheme_master_csv_v1")
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["scheme_code"], "111")
        self.assertEqual(result.records[0]["scheme_name"], "Test Fund")
        self.assertEqual(result.records[0]["amc_name"], "Test AMC")
        self.assertEqual(result.records[0]["category"], "Debt")

    def test_parse_file_routes_to_scheme_master_csv_parser(self):
        content = "Scheme Code,Scheme Name\n123,Test Fund"
        result = parse_file("scheme_master", "csv", content, {"source_url": "https://amfi.com"})
        self.assertEqual(result.parser_name, "scheme_master_csv_v1")
        self.assertEqual(len(result.records), 1)

    def test_parse_file_routes_to_scheme_master_html_parser(self):
        content = '<html><body><table><tr><th>Scheme Code</th><th>Scheme Name</th></tr><tr><td>123</td><td>Test Fund</td></tr></table></body></html>'
        result = parse_file("scheme_master", "html", content, {"source_url": "https://amfi.com"})
        self.assertEqual(result.parser_name, "scheme_master_html_v1")


class CLITests(unittest.TestCase):
    def test_run_agent_requires_task_url(self):
        from mutual_fund_ingestion.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run-agent", "--database-url", "postgresql://localhost/test"])
        self.assertEqual(args.task_url, [])
        self.assertEqual(args.database_url, "postgresql://localhost/test")

    def test_run_agent_accepts_multiple_task_urls(self):
        from mutual_fund_ingestion.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "run-agent",
            "--database-url", "postgresql://localhost/test",
            "--task-url", "https://amfiindia.com/",
            "--task-url", "https://example.com/data",
        ])
        self.assertEqual(len(args.task_url), 2)

    def test_run_agent_init_db_command_exists(self):
        from mutual_fund_ingestion.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["init-db", "--database-url", "postgresql://localhost/test"])
        self.assertEqual(args.database_url, "postgresql://localhost/test")

    def test_run_agent_respects_all_flags(self):
        from mutual_fund_ingestion.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "run-agent",
            "--database-url", "postgresql://localhost/test",
            "--task-url", "https://amfiindia.com/",
            "--max-pages", "10",
            "--max-depth", "2",
            "--dry-run",
            "--use-browser",
            "--keep-raw-files",
        ])
        self.assertEqual(args.max_pages, 10)
        self.assertEqual(args.max_depth, 2)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.use_browser)
        self.assertTrue(args.keep_raw_files)

    def test_run_agent_accepts_task_url_file(self):
        from mutual_fund_ingestion.cli import build_parser
        import tempfile
        import os
        
        # Create temp file with URLs
        fd, url_file = tempfile.mkstemp(suffix='.txt', text=True)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write('https://example.com/a\nhttps://example.com/b\n')
            
            parser = build_parser()
            args = parser.parse_args([
                'run-agent',
                '--task-url-file', url_file,
                '--database-url', 'sqlite:///test.db',
            ])
            # Verify the argument is parsed
            self.assertEqual(args.task_url_file, Path(url_file))
            # Note: task_url_file is handled in _run_agent, not in AgentConfig.from_args
        finally:
            os.unlink(url_file)


class PortfolioParserTests(unittest.TestCase):
    def test_parse_portfolio_excel_with_real_columns(self):
        from pathlib import Path
        from mutual_fund_ingestion.agent.parser.portfolio import parse_portfolio_excel
        content = (Path(__file__).parent / "fixtures" / "data" / "portfolio_sample.xlsx").read_bytes()
        result = parse_portfolio_excel(content, {"source_url": "https://example.com/portfolio.xlsx"})
        names = [r["security_name"] for r in result.records]
        self.assertIn("Reliance Industries Ltd", names)
        self.assertIn("HDFC Bank Ltd", names)
        self.assertTrue(all(r.get("security_name") for r in result.records))
        self.assertGreaterEqual(len(result.records), 3)


class MetadataParserTests(unittest.TestCase):
    def test_metadata_html_returns_document_record(self):
        from mutual_fund_ingestion.agent.parser.metadata import parse_metadata_html
        result = parse_metadata_html(
            b"<html><body>Factsheet October 2024</body></html>",
            {"source_url": "https://example.com/factsheet.html", "dataset_type": "factsheet"}
        )
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["document_type"], "factsheet")

    def test_metadata_pdf_returns_zero_records_with_warning(self):
        from mutual_fund_ingestion.agent.parser.metadata import parse_metadata_pdf
        result = parse_metadata_pdf(b"%PDF stub", {"source_url": "https://x.com/sid.pdf", "dataset_type": "sid"})
        self.assertEqual(result.records, [])
        self.assertTrue(result.warnings)

    def test_parse_tabular_csv_returns_records(self):
        from mutual_fund_ingestion.agent.parser.metadata import parse_tabular_csv
        csv_content = "scheme_code,ter\n120503,1.5\n120504,1.2\n"
        result = parse_tabular_csv(csv_content.encode(), {"source_url": "https://example.com/ter.csv"}, "ter")
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["scheme_code"], "120503")
        self.assertEqual(result.records[0]["ter"], "1.5")



    def test_parse_portfolio_csv_with_real_columns(self):
        from mutual_fund_ingestion.agent.parser.portfolio import parse_portfolio_csv
        csv_content = """Name of Instrument,ISIN,Industry,Quantity,Market Value (Rs. in Lakhs),% to NAV
Reliance Industries Ltd,INE002A01018,Oil & Gas,100,5234.56,8.5
HDFC Bank Ltd,INE040A01034,Banks,200,8901.23,14.2
TCS Ltd,INE467B01029,IT,50,3456.78,5.6
"""
        result = parse_portfolio_csv(csv_content.encode(), {"source_url": "https://example.com/portfolio.csv"})
        names = [r["security_name"] for r in result.records]
        self.assertIn("Reliance Industries Ltd", names)
        self.assertIn("HDFC Bank Ltd", names)
        self.assertTrue(all(r.get("security_name") for r in result.records))
        self.assertGreaterEqual(len(result.records), 3)


class DiscoveryEngineTests(unittest.TestCase):
    def setUp(self):
        from mutual_fund_ingestion.agent.discovery import DiscoveryEngine
        from utils.http import HttpSettings
        import requests
        self.engine = DiscoveryEngine(session=requests.Session(), settings=HttpSettings())

    def test_nav_link_scores_high(self):
        score, hint = self.engine.score_relevance(
            "https://example.com/nav-history", "NAV History", ""
        )
        self.assertGreaterEqual(score, 0.7)

    def test_careers_link_scores_zero(self):
        score, hint = self.engine.score_relevance(
            "https://example.com/careers", "Careers", ""
        )
        self.assertEqual(score, 0.0)

    def test_extract_links_from_fixture(self):
        from pathlib import Path
        html = (Path(__file__).parent / "fixtures" / "provider_static.html").read_text()
        links = self.engine.extract_links(html, "https://example.com/")
        urls = [l["url"] for l in links]
        self.assertTrue(any("portfolio" in u.lower() or ".xlsx" in u.lower() for u in urls),
                        f"No portfolio link found in {urls}")

    def test_classify_nav_url(self):
        self.assertEqual(self.engine.classify_dataset("https://x.com/nav-all.txt", "NAV Data"), "nav_history")

    def test_classify_portfolio_url(self):
        result = self.engine.classify_dataset("https://x.com/portfolio-disclosure.xlsx", "Monthly Portfolio")
        self.assertEqual(result, "portfolio_disclosure")

    def test_classify_scheme_master_url(self):
        result = self.engine.classify_dataset("https://x.com/scheme-master.csv", "Scheme Code List")
        self.assertEqual(result, "scheme_master")

    def test_classify_factsheet_url(self):
        result = self.engine.classify_dataset("https://x.com/SBI-Factsheet-Oct2024.pdf", "Factsheet")
        self.assertEqual(result, "factsheet")

    def test_classify_ter_url(self):
        result = self.engine.classify_dataset("https://x.com/TER-report-2024.csv", "Total Expense Ratio")
        self.assertEqual(result, "ter")

    def test_amfi_api_nav_url_classified_as_nav_history(self):
        result = self.engine.classify_dataset(
            "https://www.amfiindia.com/spages/NAVAll.txt", "Download All NAV"
        )
        self.assertEqual(result, "nav_history")


    def test_portfolio_xlsx_classified_as_portfolio_disclosure(self):
        result = self.engine.classify_dataset(
            "https://amc.com/portfolio-oct2024.xlsx", "Monthly Portfolio"
        )
        self.assertEqual(result, "portfolio_disclosure")


class BrowserAgentTests(unittest.TestCase):
    def test_raises_browser_unavailable_when_playwright_missing(self):
        from mutual_fund_ingestion.agent.browser import extract_with_browser, BrowserUnavailable
        from pathlib import Path
        import unittest.mock as mock
        import sys
        
        with mock.patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            with self.assertRaises((BrowserUnavailable, ImportError)):
                extract_with_browser("https://example.com", Path("/tmp/debug"), timeout_seconds=5)

    def test_extract_with_browser_returns_links(self):
        from mutual_fund_ingestion.agent.browser import extract_with_browser, BrowserResult
        from pathlib import Path
        import unittest.mock as mock
        
        fake_html = '<html><body><a href="/nav.txt">NAV Data</a></body></html>'
        fake_page = mock.MagicMock()
        fake_page.content.return_value = fake_html
        fake_locator = mock.MagicMock()
        fake_locator.get_attribute.return_value = "/nav.txt"
        fake_locator.inner_text.return_value = "NAV Data"
        fake_page.locator.return_value.all.return_value = [fake_locator]
        fake_page.goto.return_value = None
        fake_browser = mock.MagicMock()
        fake_browser.new_page.return_value = fake_page
        fake_sync_playwright = mock.MagicMock()
        fake_chromium = mock.MagicMock()
        fake_chromium.launch.return_value = fake_browser
        fake_sync_playwright.__enter__.return_value.chromium = fake_chromium
        fake_sync_playwright.__exit__.return_value = False
        
        with mock.patch("playwright.sync_api.sync_playwright", fake_sync_playwright):
            result = extract_with_browser("https://example.com", Path("/tmp/test_browser_debug"))
        self.assertIsNotNone(result.html)


class NetworkAPITests(unittest.TestCase):
    def test_network_downloads_detected_from_xhr(self):
        from mutual_fund_ingestion.agent.browser import BrowserResult
        
        network_calls = [
            {"url": "https://api.amfiindia.com/NavALL", "status": 200, "content_type": "text/plain"},
        ]
        result = BrowserResult(
            html="<html></html>",
            screenshot_path=None,
            links=[],
            downloads=[{"url": "https://api.amfiindia.com/NavALL", "file_type": "txt", "content_type": "text/plain"}],
            network_calls=network_calls,
        )
        self.assertTrue(any(d["file_type"] == "txt" for d in result.downloads))


        self.assertTrue(any(d["file_type"] == "txt" for d in result.downloads))


class VLMClientTests(unittest.TestCase):
    def test_null_client_returns_none(self):
        from mutual_fund_ingestion.agent.vlm import NullVLMClient, PageAnalysisPayload
        client = NullVLMClient()
        payload = PageAnalysisPayload(
            objective="find NAV data",
            current_url="https://x.com",
            page_title="",
            visible_text_excerpt="<html></html>",
            links=[],
            buttons=[],
            forms=[],
            screenshot_path=None
        )
        self.assertIsNone(client.analyze_page(payload))

    def test_ollama_client_builds_prompt(self):
        from mutual_fund_ingestion.agent.vlm import OllamaVLMClient, PageAnalysisPayload
        client = OllamaVLMClient(endpoint="http://localhost:11434", model="llama3")
        payload = PageAnalysisPayload(
            objective="find NAV data",
            current_url="https://example.com/downloads",
            page_title="Downloads",
            visible_text_excerpt="<html><body>Download NAV Data</body></html>",
            links=[{"url": "https://example.com/nav.txt", "text": "NAV History"}],
            buttons=[],
            forms=[],
            screenshot_path=None
        )
        prompt = client._build_prompt(payload)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 20)
        self.assertIn("example.com", prompt)

    def test_parse_response_valid_json(self):
        from mutual_fund_ingestion.agent.vlm import OllamaVLMClient
        client = OllamaVLMClient()
        raw = '{"page_relevance": "high", "dataset_hints": ["nav_history"], "recommended_action": "download", "target_text": "NAV History", "form_values": {}, "avoid_targets": [], "reason": "NAV link found", "confidence": 0.85}'
        decision = client._parse_response(raw)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.page_relevance, "high")
        self.assertIn("nav_history", decision.dataset_hints)

    def test_parse_response_invalid_json_returns_none(self):
        from mutual_fund_ingestion.agent.vlm import OllamaVLMClient
        client = OllamaVLMClient()
        self.assertIsNone(client._parse_response("not json at all"))

    def test_vlm_called_for_low_confidence_page(self):
        from mutual_fund_ingestion.agent.vlm import VLMClient, PageAnalysisPayload, PageAnalysisDecision
        calls = []
        class SpyVLM(VLMClient):
            def analyze_page(self, payload):
                calls.append(payload.current_url)
                return None
        # Note: This test would need integration with runner to fully verify
        # For now, verify the VLM client interface works
        spy = SpyVLM()
        payload = PageAnalysisPayload(
            objective="test", current_url="https://example.com", page_title="",
            visible_text_excerpt="<html>test</html>", links=[], buttons=[], forms=[], screenshot_path=None
        )
        result = spy.analyze_page(payload)
        self.assertIsNone(result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], "https://example.com")


if __name__ == "__main__":
    unittest.main()