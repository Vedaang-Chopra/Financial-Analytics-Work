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
from mutual_fund_ingestion.agent.parser import route_parser, parse_file
from mutual_fund_ingestion.agent.validate import validate_nav_record, validate_portfolio_record, validate_and_filter_records


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
        self.assertEqual(float(result.records[1]["nav_value"]), 120.75)

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


if __name__ == "__main__":
    unittest.main()