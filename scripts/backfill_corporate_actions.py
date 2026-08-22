#!/usr/bin/env python
"""Backfill corporate_actions from the NSE corporate-actions feed (plan E2).

Polite sequential fetch of
    https://www.nseindia.com/api/corporates-corporateActions
        ?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY
in <=90-day windows (verified working 2026-08-22, historical coverage OK).

Parses split/bonus/rights subjects into ratio = new/old shares and inserts
confirmed rows into corporate_actions (ON CONFLICT DO NOTHING — idempotent).

Subject parsing examples:
  "Split 10:5" / "Split of Rs.10/- to Rs.2/-" -> split ratios
  "Bonus 1:1" / "Bonus 4:1"                   -> bonus ratios
  "Rights 1:9"                                -> rights ratio

Usage:
    ./financial_env/bin/python scripts/backfill_corporate_actions.py \
        --start 2016-01-01 --end 2026-08-22 [--window-days 90]
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import psycopg2  # noqa: E402
import requests  # noqa: E402

from db_config import mutual_funds_url  # noqa: E402

API_URL = "https://www.nseindia.com/api/corporates-corporateActions"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
}
SLEEP_SECONDS = 1.2

# ratio patterns: prefer explicit share ratios ("Bonus 1:1", "Split 10:5")
RATIO_RE = re.compile(r"(?:split|bonus|rights|fsp)[^:]*?(\d+)\s*:\s*(\d+)", re.IGNORECASE)
# face-value split form: "Rs.10/- to Rs.2/-"
FV_RE = re.compile(r"[rR]s\.?\s*([\d.]+)\s*/?-?\s*(?:to|-)\s*[rR]s\.?\s*([\d.]+)")


def parse_subject(subject: str) -> tuple[str, float] | None:
    """Return (action, ratio=new/old) or None when not a price-distorting action."""
    s = subject or ""
    low = s.lower()
    if "split" in low:
        m = RATIO_RE.search(s)
        if m:
            return "split", float(m.group(1)) / float(m.group(2))
        m = FV_RE.search(s)
        if m and float(m.group(2)) > 0:
            return "split", float(m.group(1)) / float(m.group(2))
        return None
    if "bonus" in low:
        m = RATIO_RE.search(s)
        if m:
            old = float(m.group(2))
            new = float(m.group(1))
            if old > 0:
                # Bonus a:b -> holder of b gets a extra; total shares become a+b.
                return "bonus", (new + old) / old
        return None
    if "rights" in low:
        m = RATIO_RE.search(s)
        if m:
            old = float(m.group(2))
            new = float(m.group(1))
            if old > 0:
                return "rights", (new + old) / old
        return None
    return None


def parse_exdate(d: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(d.strip(), fmt).date()
        except ValueError:
            continue
    return None


def windows(start: date, end: date, days: int):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--window-days", type=int, default=90)
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args()

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    conn = psycopg2.connect(args.database_url or mutual_funds_url())
    cur = conn.cursor()

    session = requests.Session()
    session.headers.update(HEADERS)
    session.get("https://www.nseindia.com", timeout=15)

    inserted = skipped_no_ratio = skipped_no_isin = failed_windows = 0
    n_windows = len(list(windows(start, end, args.window_days)))
    for wi, (w_start, w_end) in enumerate(windows(start, end, args.window_days), 1):
        params = {
            "index": "equities",
            "from_date": w_start.strftime("%d-%m-%Y"),
            "to_date": w_end.strftime("%d-%m-%Y"),
        }
        rows = []
        for attempt in range(3):
            try:
                resp = session.get(API_URL, params=params, timeout=30)
                resp.raise_for_status()
                rows = resp.json() or []
                break
            except Exception as exc:  # noqa: BLE001
                wait = 2**attempt * 5
                logging.warning("window %s..%s attempt %d failed: %s; retry in %ss",
                                w_start, w_end, attempt + 1, exc, wait)
                time.sleep(wait)
                # re-warm cookies
                try:
                    session.get("https://www.nseindia.com", timeout=15)
                except Exception:  # noqa: BLE001
                    pass
        else:
            failed_windows += 1
            continue

        for row in rows:
            isin = (row.get("isin") or "").strip()
            ex_raw = row.get("exDate") or ""
            if not isin or not ex_raw:
                skipped_no_isin += 1
                continue
            parsed = parse_subject(row.get("subject") or "")
            if parsed is None:
                skipped_no_ratio += 1
                continue
            action, ratio = parsed
            ex = parse_exdate(ex_raw)
            if ex is None:
                continue
            cur.execute(
                """
                INSERT INTO corporate_actions (isin, ex_date, action, ratio, source_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (isin, ex_date, action) DO NOTHING
                """,
                (isin, ex, action, ratio,
                 f"{API_URL} [{w_start}:{w_end}] subject={row.get('subject')}"),
            )
            inserted += cur.rowcount

        if wi % 10 == 0:
            print(f"window {wi}/{n_windows}: inserted so far={inserted}")
        conn.commit()
        time.sleep(SLEEP_SECONDS)

    conn.commit()
    cur.execute("SELECT count(*) FROM corporate_actions")
    total = cur.fetchone()[0]
    print(f"\n=== report ===")
    print(f"windows failed          : {failed_windows}")
    print(f"rows inserted           : {inserted}")
    print(f"skipped (no ratio)      : {skipped_no_ratio}")
    print(f"skipped (no ISIN/exdate): {skipped_no_isin}")
    print(f"corporate_actions total : {total}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
