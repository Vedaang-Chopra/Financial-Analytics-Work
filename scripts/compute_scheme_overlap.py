#!/usr/bin/env python
"""Compute pairwise scheme-overlap coefficients per quarter (Task D2).

Applies mutual_fund_ingestion/analysis/scheme_overlap.sql against the
canonical PostgreSQL database. The SQL:

  * picks the LATEST snapshot per (scheme_id, quarter),
  * builds each scheme's set of distinct non-null ISINs for that quarter,
    (NULL / blank ISIN holdings are excluded consistently — see the SQL
    header comment for rationale),
  * computes overlap(A, B) = |A ∩ B| / min(|A|, |B|) for every unordered
    scheme pair sharing a quarter, TRUNCATE-and-recompute into
    ``scheme_overlap``.

Pair-count sanity check: pairs per quarter = C(n_schemes, 2). At ~389
schemes the worst case is ~75K pairs in one quarter; this script reports
the actual expected pair count before running and warns if it exceeds
--max-pairs (default 200_000), in which case it aborts unless --force is
given.

Usage:
    ./financial_env/bin/python scripts/compute_scheme_overlap.py            # run
    ./financial_env/bin/python scripts/compute_scheme_overlap.py --dry-run  # pair-count math only
"""
from __future__ import annotations

import argparse
import sys
import time
from itertools import combinations
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = REPO_ROOT / "mutual_fund_ingestion" / "analysis" / "scheme_overlap.sql"

from db_config import mutual_funds_url  # noqa: E402

DEFAULT_DSN = mutual_funds_url()


def overlap_coefficient(set_a: set, set_b: set) -> tuple[float, int, int]:
    """Pure overlap-coefficient math: |A∩B| / min(|A|,|B|).

    Returns (coefficient, n_common, n_min). Empty inputs yield (0.0, 0, 0)
    — a pair with no identified securities on either side is not similar.
    """
    if not set_a or not set_b:
        return 0.0, 0, 0
    n_common = len(set_a & set_b)
    n_min = min(len(set_a), len(set_b))
    return n_common / n_min, n_common, n_min


def expected_pair_count(per_quarter_scheme_counts: dict) -> int:
    """C(n, 2) summed over quarters."""
    return sum(n * (n - 1) // 2 for n in per_quarter_scheme_counts.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute pairwise scheme-overlap coefficients per quarter (Task D2)."
    )
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--dry-run", action="store_true", help="report pair-count math only")
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=200_000,
        help="abort if expected total pairs exceed this (default 200000)",
    )
    parser.add_argument("--force", action="store_true", help="run even above --max-pairs")
    args = parser.parse_args(argv)

    conn = psycopg2.connect(args.dsn)
    try:
        with conn.cursor() as cur:
            # Pair-count sanity check before running anything destructive.
            cur.execute(
                """
                WITH snap_q AS (
                    SELECT s.scheme_id,
                           date_trunc('quarter', s.reporting_date)::date AS qtr,
                           row_number() OVER (
                               PARTITION BY s.scheme_id,
                                            date_trunc('quarter', s.reporting_date)
                               ORDER BY s.reporting_date DESC, s.created_at DESC
                           ) AS rn
                    FROM portfolio_snapshots s
                    WHERE s.scheme_id IS NOT NULL
                )
                SELECT qtr, count(*) AS n_schemes
                FROM snap_q WHERE rn = 1 GROUP BY qtr ORDER BY qtr
                """
            )
            per_qtr = {qtr: n for qtr, n in cur.fetchall()}
            total_pairs = expected_pair_count({q: n for q, n in per_qtr.items()})
            worst_qtr, worst_n = max(per_qtr.items(), key=lambda kv: kv[1])
            print(f"quarters with >=1 scheme : {len(per_qtr)}")
            print(f"largest quarter          : {worst_qtr} ({worst_n} schemes -> {worst_n * (worst_n - 1) // 2} pairs)")
            print(f"expected total pairs     : {total_pairs}")
            if args.dry_run:
                print("dry-run: nothing computed")
                return 0
            if total_pairs > args.max_pairs and not args.force:
                print(
                    f"ABORT: {total_pairs} pairs > --max-pairs {args.max_pairs}. "
                    "Re-run with --force to proceed anyway."
                )
                return 2

            sql = SQL_PATH.read_text()
            t0 = time.perf_counter()
            cur.execute(sql)
            elapsed = time.perf_counter() - t0
            print(f"compute runtime          : {elapsed:.2f}s")
            conn.commit()

            cur.execute("SELECT count(*) FROM scheme_overlap")
            rows = int(cur.fetchone()[0])
            print(f"scheme_overlap rows      : {rows}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
