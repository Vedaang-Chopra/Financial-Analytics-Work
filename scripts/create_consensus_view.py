#!/usr/bin/env python
"""Apply or refresh the consensus_panel materialized view.

Usage:
    # Create/recreate the view (idempotent: DROP IF EXISTS + CREATE + indexes)
    python scripts/create_consensus_view.py

    # Refresh existing view without rebuilding DDL (fast, uses stored query)
    python scripts/create_consensus_view.py --refresh

    # Refresh non-blocking for readers (requires the unique index created below)
    python scripts/create_consensus_view.py --refresh --concurrently

Environment:
    MF_DATABASE_URL  optional override; defaults to
                     postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = REPO_ROOT / "mutual_fund_ingestion" / "analysis" / "consensus_panel.sql"

DEFAULT_DSN = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"


def apply(conn) -> None:
    """Drop + recreate consensus_panel and its lookup indexes (idempotent)."""
    sql = SQL_PATH.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def refresh(conn, concurrently: bool) -> None:
    with conn.cursor() as cur:
        if concurrently:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY consensus_panel")
        else:
            cur.execute("REFRESH MATERIALIZED VIEW consensus_panel")
    conn.commit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "Apply or refresh consensus_panel").splitlines()[0]
    )
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="REFRESH the existing view instead of DROP+CREATE",
    )
    ap.add_argument(
        "--concurrently",
        action="store_true",
        help="with --refresh: REFRESH ... CONCURRENTLY (needs unique index)",
    )
    args = ap.parse_args(argv)

    dsn = os.environ.get("MF_DATABASE_URL", DEFAULT_DSN)
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            if args.refresh:
                refresh(conn, args.concurrently)
                cur.execute("SELECT count(*) FROM consensus_panel")
                print(f"refreshed consensus_panel: {cur.fetchone()[0]} rows")
            else:
                apply(conn)
                cur.execute("SELECT count(*) FROM consensus_panel")
                print(f"applied consensus_panel.sql: {cur.fetchone()[0]} rows")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
