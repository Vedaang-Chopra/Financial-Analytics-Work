"""Tests for mutual_fund_ingestion/agent/fund_rollup.py (plan task E1).

Pure-logic coverage: token stripping, base-name grouping, overlap policy.
No DB required — DB-side behavior is covered by scripts/backfill_fund_rollup.py
verify output and integration checks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mutual_fund_ingestion.agent.fund_rollup import (  # noqa: E402
    MIN_HOLDING_OVERLAP,
    base_display_name,
    group_schemes_by_base,
    holding_overlap,
    normalize_base_name,
    resolve_group_merge,
)


class TestBaseNameNormalization:
    def test_direct_regular_variants_share_base(self):
        assert (
            normalize_base_name("Parag Parikh Flexi Cap Fund-Direct Plan-Growth")
            == normalize_base_name("Parag Parikh Flexi Cap Fund-Regular Plan-IDCW")
        )

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("HDFC Flexi Cap Fund (Direct-Growth)", "hdfc flexi cap fund"),
            ("UTI Nifty 50 Index Fund - Direct Plan - Growth", "uti nifty 50 index fund"),
            ("SBI Small Cap Fund Regular IDCW", "sbi small cap fund"),
            ("Nippon India Growth Fund", "nippon india fund"),  # 'growth' stripped (fund-name tail); key stays consistent across that fund's plan variants
        ],
    )
    def test_known_names(self, name, expected):
        assert normalize_base_name(name) == expected

    def test_parenthetical_descriptor_does_not_split_fund(self):
        verbose = (
            "Parag Parikh Flexi Cap Fund (An open-ended dynamic equity scheme "
            "investing across large cap, mid-cap, small-cap stocks)"
        )
        assert (
            normalize_base_name(verbose)
            == normalize_base_name("Parag Parikh Flexi Cap Fund")
        )

    def test_display_name_cleans_punctuation(self):
        assert base_display_name("HDFC Flexi Cap Fund (Direct-Growth)") == "HDFC Flexi Cap Fund"
        assert (
            base_display_name("Parag Parikh Flexi Cap Fund-Direct Plan-Growth")
            == "Parag Parikh Flexi Cap Fund"
        )


class TestGrouping:
    def test_same_amc_variants_group(self):
        schemes = [
            {"id": "a", "scheme_name": "Fund X Direct Growth", "amc_id": "amc1"},
            {"id": "b", "scheme_name": "Fund X Regular IDCW", "amc_id": "amc1"},
        ]
        groups = group_schemes_by_base(schemes)
        assert len(groups) == 1
        assert {m["id"] for m in next(iter(groups.values()))} == {"a", "b"}

    def test_different_amcs_never_group(self):
        schemes = [
            {"id": "a", "scheme_name": "Flexi Cap Fund Direct", "amc_id": "amc1"},
            {"id": "b", "scheme_name": "Flexi Cap Fund Direct", "amc_id": "amc2"},
        ]
        groups = group_schemes_by_base(schemes)
        assert len(groups) == 2

    def test_null_amc_isolated_from_named_amc(self):
        schemes = [
            {"id": "a", "scheme_name": "Flexi Cap Fund Direct", "amc_id": None},
            {"id": "b", "scheme_name": "Flexi Cap Fund Direct", "amc_id": "amc1"},
        ]
        groups = group_schemes_by_base(schemes)
        assert len(groups) == 2


class TestOverlapPolicy:
    def test_identical_portfolios_overlap_one(self):
        h = {"INE009A01021", "INE002A01018"}
        assert holding_overlap(h, set(h)) == 1.0

    def test_unknown_when_either_side_missing(self):
        assert holding_overlap(None, {"X"}) is None

    def test_two_empty_known_portfolios_no_contradiction(self):
        assert holding_overlap(set(), set()) == 1.0

    def test_merge_passes_on_high_overlap(self):
        assert resolve_group_merge([0.95, None]) is True

    def test_merge_blocked_on_low_overlap(self):
        assert resolve_group_merge([0.5, 0.99]) is False

    def test_all_unknown_merges(self):
        assert resolve_group_merge([None, None]) is True

    def test_threshold_value(self):
        assert MIN_HOLDING_OVERLAP == 0.90
