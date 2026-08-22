"""Unit tests for A1 validators: ISIN format check + snapshot pct-sum gate."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mutual_fund_ingestion.agent.models import ParserResult
from mutual_fund_ingestion.agent.validate import (
    ISIN_PATTERN,
    PCT_SUM_LOWER_BOUND,
    PCT_SUM_UPPER_BOUND,
    check_snapshot_pct_sums,
    validate_and_filter_records,
    validate_portfolio_record,
)


def _parser_result(dataset_type: str, records: list[dict]) -> ParserResult:
    return ParserResult(
        dataset_type=dataset_type,
        parser_name="test_parser",
        parser_version="1",
        confidence=0.9,
        records=records,
        warnings=[],
        errors=[],
        metadata={},
    )


class IsinFormatTests(unittest.TestCase):
    def test_valid_isin_passes(self):
        record = {"security_name": "Reliance Industries", "isin": "INE002A01018",
                  "percentage_to_nav": 5.0}
        self.assertEqual(validate_portfolio_record(record), [])

    def test_lowercase_isin_normalised_and_passes(self):
        record = {"security_name": "X", "isin": "ine002a01018"}
        self.assertEqual(validate_portfolio_record(record), [])

    def test_invalid_isin_rejected(self):
        for bad in ["INE002A0101", "INE002A0101823", "12E002A0101", "INE002A0101X",
                    "XX-002A01018", "not-an-isin"]:
            with self.subTest(isin=bad):
                record = {"security_name": "X", "isin": bad}
                errors = validate_portfolio_record(record)
                self.assertIn("invalid_isin", errors)

    def test_missing_or_empty_isin_is_not_rejected(self):
        # Absence of ISIN is tolerated; only malformed non-empty values fail.
        self.assertEqual(validate_portfolio_record({"security_name": "X"}), [])
        self.assertEqual(validate_portfolio_record({"security_name": "X", "isin": ""}), [])
        self.assertEqual(validate_portfolio_record({"security_name": "X", "isin": None}), [])

    def test_isin_pattern_shape(self):
        self.assertTrue(ISIN_PATTERN.match("US5949181045"))
        self.assertFalse(ISIN_PATTERN.match("US594918104A"))

    def test_filter_routes_invalid_isin_to_quarantine(self):
        records = [
            {"security_name": "Good Co", "isin": "INE002A01018"},
            {"security_name": "Bad Co", "isin": "BOGUS_ISIN_99"},
        ]
        valid, quarantined = validate_and_filter_records(
            _parser_result("portfolio_disclosure", records), "run-1"
        )
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["isin"], "INE002A01018")
        self.assertEqual(len(quarantined), 1)
        self.assertIn("invalid_isin", quarantined[0]["reason"])


class SnapshotPctSumTests(unittest.TestCase):
    def test_sum_within_bounds_no_warning(self):
        records = [
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "X", "percentage_to_nav": 60.0},
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "Y", "percentage_to_nav": 40.0},
        ]
        warnings = check_snapshot_pct_sums(records)
        self.assertEqual(warnings, [])

    def test_sum_outside_bounds_flagged(self):
        records = [
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "X", "percentage_to_nav": 50.0},
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "Y", "percentage_to_nav": 20.0},  # sum 70 < 85
        ]
        warnings = check_snapshot_pct_sums(records)
        self.assertEqual(len(warnings), 1)
        w = warnings[0]
        self.assertEqual(w["severity"], "warn")
        self.assertEqual(w["check_name"], "snapshot_pct_sum")
        self.assertAlmostEqual(w["pct_sum"], 70.0)
        self.assertIn("70.0", w["message"])

    def test_groups_are_independent(self):
        records = [
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "X", "percentage_to_nav": 100.0},
            {"scheme_name": "Fund B", "reporting_date": "2026-06-30",
             "security_name": "Y", "percentage_to_nav": 30.0},   # flagged
            {"scheme_name": "Fund B", "reporting_date": "2026-07-31",
             "security_name": "Z", "percentage_to_nav": 95.0},   # ok
        ]
        warnings = check_snapshot_pct_sums(records)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["scheme"], "Fund B")
        self.assertEqual(warnings[0]["reporting_date"], "2026-06-30")

    def test_gate_does_not_drop_rows(self):
        records = [
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "X", "percentage_to_nav": 10.0},
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "Y", "percentage_to_nav": 10.0},  # sum 20 -> warn
        ]
        valid, quarantined, warnings = validate_and_filter_records(
            _parser_result("portfolio_disclosure", records), "run-1", return_warnings=True
        )
        # WARN-level only: rows stay valid, nothing quarantined
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(quarantined), 0)
        self.assertEqual(len(warnings), 1)

    def test_non_numeric_and_missing_pct_tolerated(self):
        records = [
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "X", "percentage_to_nav": None},
            {"scheme_name": "Fund A", "reporting_date": "2026-06-30",
             "security_name": "Y", "percentage_to_nav": "n/a"},
        ]
        self.assertEqual(check_snapshot_pct_sums(records), [])

    def test_default_bounds(self):
        self.assertEqual(PCT_SUM_LOWER_BOUND, 85.0)
        self.assertEqual(PCT_SUM_UPPER_BOUND, 115.0)

    def test_gate_applies_only_to_portfolio_dataset(self):
        records = [
            {"scheme_code": "1", "nav_value": 10.0, "nav_date": "2026-06-30",
             "source_url": "http://x"},
        ]
        _, _, warnings = validate_and_filter_records(
            _parser_result("nav_history", records), "run-1", return_warnings=True
        )
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
