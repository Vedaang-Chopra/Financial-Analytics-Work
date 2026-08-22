"""Post-crawl fix-up pass for T3.

1. Fully re-ingest problem slugs (degraded/shell pages missing statement
   types, growth tables, or exchange codes; chart-fetch failures missing
   weekly price/volume series) through the normal polite pipeline.
2. Backfill missing 'daily' price series from Yahoo, trying <NSE>.NS then
   <BSE>.BO (handles '&' symbols like M&M / GVT&D that yfinance mangles).

Usage:
  python scripts/fixup_t3.py --reingest SLUG1,SLUG2 --delay 3
  python scripts/fixup_t3.py --backfill-daily
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import psycopg2.extras
from sqlalchemy import text

from screener_ingestion import db, yahoo
from screener_ingestion.cli import ingest_one

from db_config import screener_url

DB = screener_url()


def find_problem_slugs() -> dict[str, list[str]]:
    """Return {'reingest': [...], 'daily': [...]} based on DB state."""
    reasons: dict[str, list[str]] = {}
    eng = db.get_engine(DB)
    with eng.connect() as conn:
        rows = conn.execute(text("""
            SELECT s.slug,
                   COUNT(DISTINCT fp.statement_type) FILTER (WHERE fp.statement_type IN
                     ('quarters','profit-loss','balance-sheet','cash-flow','ratios',
                      'shareholding_quarterly','shareholding_annual')) AS n_types,
                   (SELECT COUNT(*) FROM growth_summary g WHERE g.stock_id=s.id) AS n_growth,
                   (s.bse_code IS NULL OR s.nse_code IS NULL) AS codes_missing,
                   COALESCE(SUM((pp.series IN ('price','volume'))::int), 0) AS n_weekly,
                   COALESCE(SUM((pp.series='daily')::int), 0) AS n_daily
              FROM stocks s
              LEFT JOIN financial_periods fp ON fp.stock_id = s.id
              LEFT JOIN price_points pp ON pp.stock_id = s.id
             GROUP BY s.id, s.slug, s.bse_code, s.nse_code
        """)).mappings().all()
    reingest, daily_only = [], []
    for r in rows:
        slug = r["slug"]
        probs = []
        if r["n_types"] < 7:
            probs.append(f"types={r['n_types']}")
        if r["n_growth"] == 0:
            probs.append("growth=0")
        if r["codes_missing"]:
            probs.append("codes_missing")
        if r["n_weekly"] == 0:
            probs.append("weekly=0")
        if r["n_daily"] == 0:
            probs.append("daily=0")
        if not probs:
            continue
        reasons[slug] = probs
        if set(probs) == {"daily=0"}:
            daily_only.append(slug)
        else:
            reingest.append(slug)
    print("problem slugs:")
    for s, p in sorted(reasons.items()):
        print(f"  {s:<14} {','.join(p)}")
    return {"reingest": reingest, "daily": reingest + daily_only}


def cmd_reingest(slugs: list[str], delay: float) -> None:
    ok, fail = [], []
    for i, slug in enumerate(slugs):
        try:
            summary = ingest_one(slug, DB)
            ok.append(slug)
            print(f"  [{i+1}/{len(slugs)}] OK   {slug:<14} items={summary['line_items']} "
                  f"prices={summary['price_points']} daily={summary['daily_points']}")
        except Exception as exc:
            fail.append(slug)
            print(f"  [{i+1}/{len(slugs)}] FAIL {slug:<14} {str(exc)[:100]}")
        time.sleep(delay)
    print(f"reingest done: {len(ok)} ok, {len(fail)} failed {fail}")


def cmd_backfill_daily(slugs: list[str], delay: float) -> None:
    """Insert missing daily series via yahoo; try NSE.NS then BSE.BO."""
    eng = db.get_engine(DB)
    with eng.connect() as conn:
        codes = {
            r[0]: (r[1], r[2])
            for r in conn.execute(text("SELECT slug, nse_code, bse_code FROM stocks"))
        }
    still_missing = []
    for i, slug in enumerate(slugs):
        nse, bse = codes.get(slug, (None, None))
        candidates = []
        if nse and "&" not in str(nse):
            candidates.append(f"{nse}.NS")
        if bse:
            candidates.append(f"{bse}.BO")
        got = False
        for sym in candidates:
            try:
                result = yahoo.fetch_daily(sym)
                rows, meta = yahoo.parse_daily(result)
                if not rows:
                    raise yahoo.YahooError("no rows")
                _upsert_price_points(rows, slug)
                print(f"  [{i+1}/{len(slugs)}] OK   {slug:<14} {sym}: {meta['count']} daily rows "
                      f"{meta['first_date']}..{meta['last_date']}")
                got = True
                break
            except Exception as exc:
                print(f"  [{i+1}/{len(slugs)}] miss {slug:<14} {sym}: {str(exc)[:80]}")
        if not got:
            still_missing.append(slug)
        time.sleep(delay)
    print(f"daily backfill done; still missing: {still_missing}")


def _upsert_price_points(rows: list[dict], slug: str) -> int:
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM stocks WHERE slug=%s", (slug,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return 0
    stock_id = row[0]
    n = 0
    for pt in rows:
        cur.execute("""
            INSERT INTO price_points (stock_id, point_date, series, close, volume,
                                      open, high, low, adj_close, fetched_at)
            VALUES (%s,%s,'daily',%s,%s,%s,%s,%s,%s, now())
            ON CONFLICT (stock_id, point_date, series) DO UPDATE SET
                close=EXCLUDED.close, volume=EXCLUDED.volume, open=EXCLUDED.open,
                high=EXCLUDED.high, low=EXCLUDED.low, adj_close=EXCLUDED.adj_close,
                fetched_at=now()
        """, (stock_id, pt["point_date"], pt["close"], pt["volume"],
              pt["open"], pt["high"], pt["low"], pt["adj_close"]))
        n += 1
    conn.commit()
    conn.close()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reingest", default=None,
                    help="Comma-separated slugs; omit to auto-detect")
    ap.add_argument("--backfill-daily", action="store_true")
    ap.add_argument("--detect-only", action="store_true")
    ap.add_argument("--delay", type=float, default=3.0)
    args = ap.parse_args()

    problems = find_problem_slugs()
    if args.detect_only:
        return 0

    if args.backfill_daily:
        cmd_backfill_daily(problems["daily"], args.delay)
    elif args.reingest is not None:
        slugs = [s.strip().upper() for s in args.reingest.split(",") if s.strip()]
        cmd_reingest(slugs, args.delay)
    else:
        cmd_reingest(problems["reingest"], args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
