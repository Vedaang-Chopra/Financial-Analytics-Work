"""Backfill daily OHLC history (Yahoo) for stocks already in the DB.

Lightweight: does NOT re-scrape screener. Only hits Yahoo once per stock,
2s apart, and upserts series='daily' rows into price_points.

Usage:
  python scripts/backfill_daily.py                # all stocks missing daily data
  python scripts/backfill_daily.py --limit 10     # first 10 only
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_config import screener_url  # noqa: E402

DB = screener_url()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()

    from screener_ingestion import db, yahoo

    engine = create_engine(DB)
    todo = pd.read_sql(text("""
        SELECT s.slug, s.nse_code
        FROM stocks s
        WHERE NOT EXISTS (
            SELECT 1 FROM price_points pp
            WHERE pp.stock_id = s.id AND pp.series = 'daily'
        )
        ORDER BY s.id
    """), engine)
    if args.limit:
        todo = todo.head(args.limit)
    print(f"stocks needing daily backfill: {len(todo)}")

    ok = fail = 0
    for i, row in enumerate(todo.itertuples()):
        slug, nse = row.slug, row.nse_code
        try:
            ysym = yahoo.yahoo_symbol(slug, nse)
            rows, meta = yahoo.parse_daily(yahoo.fetch_daily(ysym))
            if not rows:
                raise yahoo.YahooError("0 rows returned")
            run_uuid = db.save_payload(
                DB, {"slug": slug}, price_history=rows,
            )
            ok += 1
            print(f"[{i + 1}/{len(todo)}] OK   {slug:<14} {meta['count']:>5} daily rows "
                  f"{meta['first_date']} -> {meta['last_date']}")
        except Exception as exc:
            fail += 1
            print(f"[{i + 1}/{len(todo)}] FAIL {slug:<14} {str(exc)[:90]}")
        time.sleep(args.delay)

    print(f"\nDone: {ok} backfilled, {fail} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
