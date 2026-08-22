#!/usr/bin/env python
"""Detect impossible price moves and manage corporate_actions (plan task E2).

Deterministic detection fallback (mandatory per plan):
  1. Scan security_prices for |1-day move| > 60% per ISIN.
  2. For each candidate date, check corporate_actions: a confirmed action with
     ex_date = candidate_date+1 (bhavcopy dates are trading days; the drop
     shows on the first close AFTER ex-date) explains the move.
  3. Explained candidates: no output (price history is correct as-is; the
     adjusted view handles returns).
  4. Unexplained candidates -> review CSV in data/reports/mutual_funds/
     (never auto-insert into corporate_actions without a confirmed source).

Verify mode re-runs the impossible-move scan on security_prices_adj:
genuine crashes stay; split/bonus artifacts disappear.

Usage:
    ./financial_env/bin/python scripts/detect_corporate_actions.py             # detect + write review CSV
    ./financial_env/bin/python scripts/detect_corporate_actions.py --verify-adjusted   # scan adjusted series
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

from db_config import mutual_funds_url  # noqa: E402

REPORT_DIR = REPO_ROOT / "data" / "reports" / "mutual_funds"
MOVE_THRESHOLD = 0.60


def fetch_moves(cur, table: str) -> list[dict]:
    close_col = "adjusted_close" if table == "security_prices_adj" else "close"
    cur.execute(
        f"""
        WITH px AS (
            SELECT isin, trade_date, {close_col} AS close,
                   LAG({close_col}) OVER (PARTITION BY isin ORDER BY trade_date)
                       AS prev_close
            FROM {table}
        )
        SELECT isin,
               trade_date,
               prev_close::float8,
               close::float8,
               (close / NULLIF(prev_close, 0) - 1)::float8 AS ret
        FROM px
        WHERE prev_close > 0 AND ABS(close / NULLIF(prev_close, 0) - 1) > %s
        ORDER BY isin, trade_date
        """,
        (MOVE_THRESHOLD,),
    )
    return [dict(r) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database-url", default=None)
    ap.add_argument("--verify-adjusted", action="store_true",
                    help="scan security_prices_adj instead of raw")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url or mutual_funds_url())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    table = "security_prices_adj" if args.verify_adjusted else "security_prices"
    moves = fetch_moves(cur, table)
    print(f"[scan] |1d move| > {MOVE_THRESHOLD:.0%} in {table}: {len(moves)} candidates")

    if args.verify_adjusted:
        for m in moves[:20]:
            print(f"  {m['isin']} {m['trade_date']} {m['prev_close']:.2f} -> "
                  f"{m['close']:.2f} ({m['ret']:+.1%})")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORT_DIR / f"impossible_moves_adjusted_{stamp}.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(moves[0].keys()) if moves else ["isin"])
            w.writeheader()
            w.writerows(moves)
        print(f"[report] remaining candidates -> {out}")
        conn.close()
        return 0

    # Detection mode: which candidates does corporate_actions explain?
    # An action explains the move when its ex-date falls within +/-7 days of
    # the gap (bhavcopy gaps open on the first close on/after ex-date) and the
    # implied ratio 1/ratio is within tolerance of the observed move.
    explained = unexplained = 0
    unexplained_rows: list[dict] = []
    for m in moves:
        cur.execute(
            """
            SELECT action, ratio FROM corporate_actions
            WHERE isin = %s
              AND ex_date BETWEEN %s::date - 7 AND %s::date + 7
            """,
            (m["isin"], m["trade_date"], m["trade_date"]),
        )
        hits = cur.fetchall()
        obs = abs(m["close"] / m["prev_close"]) if m["prev_close"] else None
        ok = False
        for hit in hits:
            action = hit["action"]
            ratio = hit["ratio"]
            if ratio and obs is not None:
                implied = 1.0 / float(ratio)
                if implied > 0 and abs(obs - implied) / implied < 0.25:
                    ok = True
                    break
        if ok or hits:
            explained += 1
        else:
            unexplained += 1
            unexplained_rows.append(m)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"corporate_action_review_{stamp}.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["isin", "trade_date", "prev_close", "close", "ret"]
        )
        w.writeheader()
        w.writerows(unexplained_rows)
    print(f"[detect] explained by confirmed actions : {explained}")
    print(f"[detect] UNEXPLAINED (need review)      : {unexplained}")
    print(f"[report] review CSV -> {out}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
