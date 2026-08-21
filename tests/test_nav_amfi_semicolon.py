"""Add regression tests for the AMFI semicolon parser fix.

Covers the exact bug: rows with empty Plan/Option fields (';;') were dropped
when re.split(r"[\\t,|;]+") collapsed consecutive separators.
"""
import unittest

from mutual_fund_ingestion.agent.parser import parse_file


AMFI_SAMPLE = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;"
    "Scheme Name;Plan;Option;Net Asset Value;Date\r\n"
    " \r\n"
    "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)\r\n"
    "Aditya Birla Sun Life Mutual Fund\r\n"
    "119551;INF209KA12Z1;INF209KA13Z9;Aditya Birla Sun Life Banking & PSU Debt Fund;"
    "Direct Plan;IDCW-Re-investment;106.8821;21-Aug-2026\r\n"
    # Empty Plan AND Option — this is the row class the old parser dropped
    "130897;INF109KA1B57;-;ICICI Prudential Banking & PSU Debt Fund;;;15.8889;24-Apr-2020\r\n"
    # Embedded tab in Option + comma-free name
    "119163;-;INF959L01GK1;Navi Liquid Fund;Direct Plan;Daily IDCW - ReInvestment\t;10.0129;21-Aug-2026\r\n"
    # NAV of 0.0000 (suspended/segregated scheme) must still PARSE (validation may reject)
    "148304;INF123456789;-;Franklin India Credit Risk Fund (Segregated);Direct Plan;Growth;0.0000;21-Aug-2026\r\n"
)


class TestAmfiSemicolonParser(unittest.TestCase):
    def test_parses_all_rows_including_empty_plan(self):
        result = parse_file("nav_history", "text", AMFI_SAMPLE.encode(), {"source_url": "test"})
        self.assertEqual(len(result.records), 4, result.errors)
        self.assertEqual(result.errors, [])
        codes = [r["scheme_code"] for r in result.records]
        self.assertEqual(codes, ["119551", "130897", "119163", "148304"])

    def test_empty_plan_and_option_are_none_not_shifted(self):
        result = parse_file("nav_history", "text", AMFI_SAMPLE.encode(), {})
        row = next(r for r in result.records if r["scheme_code"] == "130897")
        self.assertIsNone(row["plan"])
        self.assertIsNone(row["option"])
        self.assertEqual(row["nav_value"], 15.8889)
        self.assertEqual(row["nav_date"], "2020-04-24")

    def test_embedded_tab_does_not_corrupt_option(self):
        result = parse_file("nav_history", "text", AMFI_SAMPLE.encode(), {})
        row = next(r for r in result.records if r["scheme_code"] == "119163")
        self.assertEqual(row["nav_value"], 10.0129)
        self.assertTrue(row["option"].startswith("Daily IDCW"))

    def test_zero_nav_still_parsed(self):
        """Zero NAV is real AMFI data (segregated portfolios); parsing keeps it."""
        result = parse_file("nav_history", "text", AMFI_SAMPLE.encode(), {})
        row = next(r for r in result.records if r["scheme_code"] == "148304")
        self.assertEqual(row["nav_value"], 0.0)

    def test_section_headers_skipped(self):
        result = parse_file("nav_history", "text", AMFI_SAMPLE.encode(), {})
        names = [r["scheme_name"] for r in result.records]
        # every parsed row carries a real scheme name (no section headers/AMC rows)
        self.assertTrue(all(n and "Open Ended" not in n and "Mutual Fund" != n for n in names))
        self.assertEqual(len(names), 4)

    def test_isin_dash_normalized_to_none(self):
        result = parse_file("nav_history", "text", AMFI_SAMPLE.encode(), {})
        # 119163 has '-' in the payout ISIN column
        row = next(r for r in result.records if r["scheme_code"] == "119163")
        self.assertIsNone(row["isin_div_payout"])
        self.assertIsNotNone(row["isin_div_reinvestment"])

    def test_full_live_snapshot_row_count(self):
        """If the live snapshot fixture is present, all rows must parse."""
        import os
        path = "/tmp/navall.txt"
        if not os.path.exists(path):
            self.skipTest("live snapshot not available")
        with open(path, "rb") as f:
            content = f.read()
        result = parse_file("nav_history", "text", content, {"source_url": "amfi"})
        raw_rows = sum(
            1 for l in content.decode("utf-8", errors="replace").strip().split("\n")
            if len(l.split(";")) == 8 and l.split(";")[0].strip().isdigit()
        )
        self.assertEqual(len(result.records), raw_rows)
        self.assertEqual(len(result.errors), 0)


if __name__ == "__main__":
    unittest.main()
