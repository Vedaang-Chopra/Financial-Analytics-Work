#!/usr/bin/env python
"""Backfill security_prices from NSE bhavcopy files (~10 years).

Polite sequential crawling: sleep >= 1s between requests (default 2s),
real browser User-Agent, timeouts, retry-with-backoff on transient errors.

Resume capability: dates already present in security_prices are skipped,
so the script can be re-run after interruption without refetching.

Usage:
    python scripts/backfill_bhavcopy.py --start 2018-01-01   # priority range
    python scripts/backfill_bhavcopy.py --start 2016-01-01   # full history

If NSE blocks/rate-limits persistently (repeated ConnectionError), the run
aborts with a clear report; re-run prioritising 2018->now first.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

from market_data.bhavcopy import BhavcopyClient, trading_days, upsert_prices  # noqa: E402

DEFAULT_DB = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill_bhavcopy")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def existing_dates(engine) -> set[date]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT trade_date FROM security_prices")
        ).fetchall()
    return {r[0] for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD")
    ap.add_argument("--db", default=os.environ.get("DATABASE_URL", DEFAULT_DB))
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between HTTP requests (>=1)")
    ap.add_argument("--max-consecutive-blocks", type=int, default=5,
                    help="abort after this many consecutive blocked fetches")
    args = ap.parse_args()

    start, end = parse_date(args.start), parse_date(args.end)
    engine = create_engine(args.db)

    done = existing_dates(engine)
    todo = [d for d in trading_days(start, end) if d not in done]
    log.info(
        "Backfill %s -> %s: %d weekdays, %d already present, %d to fetch",
        start, end, sum(1 for _ in trading_days(start, end)), len(done), len(todo),
    )

    client = BhavcopyClient(sleep_seconds=args.sleep)
    stats = {"ok": 0, "miss": 0, "rows": 0, "blocked": 0}
    consecutive_blocks = 0

    for i, d in enumerate(todo, 1):
        try:
            rows, source_url = client.fetch_date(d)
        except ConnectionError as exc:
            consecutive_blocks += 1
            log.error("[%d/%d] %s BLOCKED (%d consecutive): %s",
                      i, len(todo), d, consecutive_blocks, exc)
            if consecutive_blocks >= args.max_consecutive_blocks:
                log.error(
                    "Aborting: %d consecutive blocked fetches. "
                    "Re-run later (script resumes automatically).",
                    consecutive_blocks,
                )
                break
            continue
        consecutive_blocks = 0

        if not rows:
            stats["miss"] += 1  # holiday / file not published
            continue
        inserted, skipped = upsert_prices(engine, rows, d, source_url)
        stats["ok"] += 1
        stats["rows"] += inserted
        if i % 25 == 0 or i == len(todo):
            log.info("[%d/%d] %s: +%d rows | ok=%d miss=%d total_rows=%d",
                     i, len(todo), d, inserted, stats["ok"], stats["miss"],
                     stats["rows"])

    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM security_prices")).scalar()
        distinct = conn.execute(
            text("SELECT count(DISTINCT isin) FROM security_prices")
        ).scalar()
    log.info(
        "DONE start=%s end=%s ok=%d miss(holiday/404)=%d rows_inserted=%d "
        "| table now: %d rows, %d distinct ISINs",
        start, end, stats["ok"], stats["miss"], stats["rows"], total, distinct,
    )
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
