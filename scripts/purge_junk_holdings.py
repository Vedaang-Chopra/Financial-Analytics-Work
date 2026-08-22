#!/usr/bin/env python
"""One-off purge of junk (section-header / footnote) rows from ``portfolio_holdings`` (Task A6).

Problem:
  Section-header strings and disclosure footnotes were parsed as holdings rows
  ('Total', 'Net Current Assets', 'TREPS ...', 'Scheme Name:', '** non traded
  in accordance with sebi regulations.', numbered notes, etc.). The parser's
  JUNK_ROW_PATTERNS in mutual_fund_ingestion/agent/parser/portfolio.py has been
  extended with the observed leaks; this script removes already-ingested leaks.

What this script does (deletion-policy compliant):
  1. Computes the matching junk row set from the SAME patterns as the parser
     (imported from mutual_fund_ingestion.agent.parser.portfolio) plus the
     task-mandated exact verify names. Matching is exact on
     lower(btrim(security_name)) for literal names; regex prefixes are used
     only for unambiguous families (treps*, benchmark riskometer:, footnotes).
  2. BACKUP FIRST: exports every row it intends to delete to
     data/backups/holdings_junk_purge_<stamp>.csv before any DELETE runs.
  3. DELETEs the matched rows inside one short transaction (--apply).

Usage:
    ./financial_env/bin/python scripts/purge_junk_holdings.py            # dry-run report
    ./financial_env/bin/python scripts/purge_junk_holdings.py --apply    # backup + delete
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import psycopg2  # noqa: E402

from mutual_fund_ingestion.agent.parser.portfolio import (  # noqa: E402
    JUNK_ROW_PATTERNS,
    _is_section_header,
)

DATABASE_URL = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"
BACKUP_DIR = REPO_ROOT / "data" / "backups"

# Task-mandated minimum exact-match set (lowercased trimmed security_name).
VERIFY_EXACT_NAMES = [
    "total",
    "net current assets",
    "total net assets",
    "treps",
    "commercial papers",
    "government securities",
    "certificate of deposits",
]

# Regexes compiled from the parser patterns — applied with re.match on the
# lowercased trimmed name, mirroring SECTION_HEADER_REGEX semantics.
JUNK_REGEX = re.compile("|".join(JUNK_ROW_PATTERNS), re.IGNORECASE)


def is_junk(name: str | None) -> bool:
    if not name or not isinstance(name, str):
        return False
    normalized = " ".join(name.split()).strip().lower()
    return normalized in VERIFY_EXACT_NAMES or bool(JUNK_REGEX.match(normalized))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Actually backup + DELETE. Without this flag: dry-run only.")
    args = ap.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, snapshot_id, security_name, isin FROM portfolio_holdings")
    rows = cur.fetchall()
    junk_rows = [r for r in rows if is_junk(r[2])]
    print(f"portfolio_holdings total: {len(rows)}")
    print(f"junk rows matched:        {len(junk_rows)}")

    # Breakdown by lowercased trimmed name for the report.
    from collections import Counter
    breakdown = Counter(" ".join(r[2].split()).strip().lower() for r in junk_rows)
    print("\nTop junk names:")
    for name, cnt in breakdown.most_common(30):
        print(f"  {cnt:>5}  {name}")

    if not args.apply:
        print("\nDRY-RUN: nothing deleted. Re-run with --apply to backup + purge.")
        conn.close()
        return 0

    # --- Step 1: BACKUP FIRST -------------------------------------------
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"holdings_junk_purge_{stamp}.csv"
    cur.execute(
        """
        SELECT id, snapshot_id, instrument_id, security_name, isin, sector,
               asset_class, quantity, market_value, market_value_currency,
               percentage_to_nav, coupon, maturity_date, rating, metadata_json,
               created_at
        FROM portfolio_holdings WHERE id = ANY(%s::uuid[])
        """,
        ([r[0] for r in junk_rows],),
    )
    purged = cur.fetchall()
    colnames = [d[0] for d in cur.description]
    with open(backup_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(colnames)
        writer.writerows(purged)
    print(f"\nBackup written ({len(purged)} rows): {backup_path}")

    # --- Step 2: DELETE (single short transaction) -----------------------
    cur.execute("DELETE FROM portfolio_holdings WHERE id = ANY(%s::uuid[])",
                ([r[0] for r in junk_rows],))
    deleted = cur.rowcount
    conn.commit()
    print(f"Deleted: {deleted} rows")

    # --- Step 3: post-delete verification -------------------------------
    cur.execute(
        """
        SELECT count(*) FROM portfolio_holdings
        WHERE lower(btrim(security_name)) = ANY(ARRAY[
            'total','net current assets','total net assets','treps',
            'commercial papers','government securities','certificate of deposits'])
        """
    )
    print(f"Verify-list residual count (must be 0): {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM portfolio_holdings")
    print(f"Remaining portfolio_holdings rows:      {cur.fetchone()[0]}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
