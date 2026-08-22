"""Tests for scripts/compute_scheme_overlap.py (Task D2).

Pure-function tests for the overlap-coefficient math and the pair-count
sanity check, plus a tiny-fixture test of the set-building semantics
(latest snapshot per scheme-quarter, NULL/blank-ISIN exclusion) that the
SQL implements. No live PostgreSQL needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from compute_scheme_overlap import (  # noqa: E402
    expected_pair_count,
    overlap_coefficient,
)


class TestOverlapCoefficient:
    def test_identical_sets(self):
        coef, n_common, n_min = overlap_coefficient({"a", "b", "c"}, {"a", "b", "c"})
        assert coef == 1.0
        assert n_common == 3
        assert n_min == 3

    def test_identical_sets_different_sizes_is_still_one(self):
        # subset case: min(|A|,|B|) denominator => coefficient 1.0
        coef, n_common, n_min = overlap_coefficient({"a", "b"}, {"a", "b", "c", "d"})
        assert coef == 1.0
        assert n_common == 2
        assert n_min == 2

    def test_disjoint_sets(self):
        coef, n_common, n_min = overlap_coefficient({"a", "b"}, {"c", "d"})
        assert coef == 0.0
        assert n_common == 0
        assert n_min == 2

    def test_partial_overlap(self):
        # A={a,b,c,d}, B={b,c,x}: |A∩B|=2, min=3 => 2/3
        coef, n_common, n_min = overlap_coefficient(
            {"a", "b", "c", "d"}, {"b", "c", "x"}
        )
        assert coef == pytest.approx(2 / 3)
        assert n_common == 2
        assert n_min == 3

    def test_symmetry(self):
        a, b = {"a", "b", "c"}, {"b", "c", "d", "e"}
        assert overlap_coefficient(a, b) == overlap_coefficient(b, a)

    def test_empty_sets_yield_zero(self):
        assert overlap_coefficient(set(), {"a"}) == (0.0, 0, 0)
        assert overlap_coefficient({"a"}, set()) == (0.0, 0, 0)
        assert overlap_coefficient(set(), set()) == (0.0, 0, 0)

    def test_single_element_match(self):
        assert overlap_coefficient({"INE123"}, {"INE123"}) == (1.0, 1, 1)


class TestExpectedPairCount:
    def test_single_quarter(self):
        # C(4, 2) = 6
        assert expected_pair_count({"2026-04-01": 4}) == 6

    def test_multiple_quarters_summed(self):
        assert expected_pair_count({"q1": 3, "q2": 2}) == 3 + 1

    def test_empty(self):
        assert expected_pair_count({}) == 0

    def test_single_scheme_has_no_pairs(self):
        assert expected_pair_count({"q1": 1}) == 0


class TestSetBuildingSemantics:
    """Mirror of the SQL's set-building rules on a tiny fixture.

    Rules under test (must match mutual_fund_ingestion/analysis/scheme_overlap.sql):
      1. latest reporting_date snapshot wins per (scheme, qtr)
      2. NULL / blank ISIN holdings are excluded
      3. ISINs are deduplicated within a snapshot
    """

    @staticmethod
    def build_sets(snapshots, holdings):
        """snapshots: list of dicts (id, scheme_id, reporting_date).
        holdings: list of dicts (snapshot_id, isin).
        Returns {qtr: {scheme_id: set_of_isins}}."""
        chosen = {}  # (scheme_id, qtr) -> snapshot_id
        for s in sorted(snapshots, key=lambda s: (s["reporting_date"],)):
            key = (s["scheme_id"], s["reporting_date"][:4] + "-q" + str(
                (int(s["reporting_date"][5:7]) - 1) // 3 + 1))
            chosen[key] = s["id"]  # later (latest) reporting_date overwrites
        sets: dict = {}
        for h in holdings:
            isin = h["isin"]
            if isin is None or not isin.strip():
                continue  # NULL/blank ISIN excluded consistently
            for (scheme_id, qtr), snap_id in chosen.items():
                if snap_id == h["snapshot_id"]:
                    sets.setdefault(qtr, {}).setdefault(scheme_id, set()).add(isin.strip())
        return sets

    def test_tiny_fixture_end_to_end(self):
        snapshots = [
            {"id": "s1", "scheme_id": "A", "reporting_date": "2026-04-30"},
            {"id": "s2", "scheme_id": "A", "reporting_date": "2026-06-30"},  # latest for A
            {"id": "s3", "scheme_id": "B", "reporting_date": "2026-06-30"},
        ]
        holdings = [
            # scheme A latest snapshot (s2): 2 real ISINs + 1 NULL + 1 blank + 1 dup
            {"snapshot_id": "s2", "isin": "INE001"},
            {"snapshot_id": "s2", "isin": "INE002"},
            {"snapshot_id": "s2", "isin": None},
            {"snapshot_id": "s2", "isin": "   "},
            {"snapshot_id": "s2", "isin": "INE001"},  # duplicate
            # scheme A older snapshot (s1) must be ignored (stale ISIN)
            {"snapshot_id": "s1", "isin": "INE-STALE"},
            # scheme B (s3): 1 shared ISIN + 1 unique
            {"snapshot_id": "s3", "isin": "INE001"},
            {"snapshot_id": "s3", "isin": "INE009"},
        ]
        sets = self.build_sets(snapshots, holdings)
        a = sets["2026-q2"]["A"]
        b = sets["2026-q2"]["B"]

        assert a == {"INE001", "INE002"}  # stale snapshot, NULL/blank, dup excluded
        assert b == {"INE001", "INE009"}

        coef, n_common, n_min = overlap_coefficient(a, b)
        assert (coef, n_common, n_min) == (pytest.approx(1 / 2), 1, 2)
