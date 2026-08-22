#!/usr/bin/env python
"""Backfill ~10 years of NSE benchmark index closes into PostgreSQL.

Indices: NIFTY 50, NIFTY 500, NIFTY SMALLCAP 250, NIFTY MIDCAP 150.

Source (verified working 2026-08-22):
    https://archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv
  - one CSV per trading day covers ALL indices -> one request per day
    serves every index (~2,600 weekday requests for a 10y window)
  - weekends return 404 and are skipped client-side; other 404s are
    non-trading days / spotty archive files and are skipped too

Politeness: strictly sequential requests, >=1.1s sleep between them,
real browser User-Agent, 30s timeouts.

Resume: existing (index_symbol, trade_date) rows are loaded up front and
skipped, so re-runs only fetch missing days. Upserts use ON CONFLICT
DO NOTHING as a second safety net.

Usage:
    ./financial_env/bin/python scripts/backfill_index_prices.py \
        [--start 2016-08-22] [--end 2026-08-22]
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, ".")

import requests
from sqlalchemy import create_engine, text

from mutual_fund_ingestion.market_data.index_prices import (
    DEFAULT_HEADERS,
    INDEX_LABELS,
    daily_close_all_url,
    polite_sleep,
    parse_index_close_csv,
    select_closes,
    weekday_range,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
LOGGER = logging.getLogger("index_backfill")

from db_config import mutual_funds_url  # noqa: E402

DATABASE_URL = mutual_funds_url()
SOURCE_URL_TEMPLATE = daily_close_all_url(date(2000, 1, 1))  # re-formatted per day
SLEEP_SECONDS = 1.1


def load_existing(engine, symbols: list[str]) -> set[tuple[str, date]]:
    """All (symbol, date) pairs already in index_prices (resume support)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT index_symbol, trade_date FROM index_prices WHERE index_symbol = ANY(:syms)"),
            {"syms": symbols},
        )
        return {(r[0], r[1]) for r in rows}


def insert_closes(engine, symbol_dates_closes, source_url: str) -> int:
    """Upsert rows with ON CONFLICT DO NOTHING. Returns inserted count."""
    if not symbol_dates_closes:
        return 0
    payload = [
        {"sym": s, "d": d, "close": c, "url": source_url}
        for s, d, c in symbol_dates_closes
    ]
    stmt = text(
        """
        INSERT INTO index_prices (index_symbol, trade_date, close, source_url)
        VALUES (:sym, :d, :close, :url)
        ON CONFLICT (index_symbol, trade_date) DO NOTHING
        """
    )
    inserted = 0
    with engine.begin() as conn:
        result = conn.execute(stmt, payload)
        inserted = result.rowcount or 0
    return inserted


def backfill(start: date, end: date) -> None:
    engine = create_engine(DATABASE_URL)
    symbols = list(INDEX_LABELS)
    existing = load_existing(engine, symbols)
    LOGGER.info("resume: %d existing (symbol,date) pairs already stored", len(existing))

    session = requests.Session()
    days_total = sum(1 for _ in weekday_range(start, end))
    days_done = days_missing = days_404 = 0
    rows_inserted = 0
    t0 = time.time()

    for d in weekday_range(start, end):
        # A single request covers all indices; skip the day entirely when
        # every wanted (symbol, date) pair is already present.
        missing = [(s, d) for s in symbols if (s, d) not in existing]
        if not missing:
            days_done += 1
            continue
        url = daily_close_all_url(d)
        try:
            resp = session.get(url, timeout=30, headers=DEFAULT_HEADERS)
        except requests.RequestException as exc:
            LOGGER.warning("%s network error (%s) — skipping day", d, exc)
            polite_sleep(SLEEP_SECONDS)
            days_missing += 1
            continue
        if resp.status_code == 404:
            # The NSE archive intermittently soft-404s long-lived sessions
            # (verified 2026-08-22: a day that 404'd mid-run returns 200 on
            # a fresh session). Retry once with a fresh session before
            # treating it as a genuine non-trading day.
            polite_sleep(SLEEP_SECONDS)
            session = requests.Session()
            try:
                resp = session.get(url, timeout=30, headers=DEFAULT_HEADERS)
            except requests.RequestException as exc:
                LOGGER.warning("%s network error on 404-retry (%s)", d, exc)
                days_missing += 1
                polite_sleep(SLEEP_SECONDS)
                continue
        if resp.status_code == 404:
            days_404 += 1
            polite_sleep(SLEEP_SECONDS)
            continue
        if resp.status_code != 200:
            LOGGER.warning("%s unexpected HTTP %d — skipping day", d, resp.status_code)
            days_missing += 1
            polite_sleep(SLEEP_SECONDS)
            continue
        records = parse_index_close_csv(resp.text, trade_date=d)
        triples = [t for t in select_closes(records)]
        n = insert_closes(engine, triples, source_url=url)
        rows_inserted += n
        for sym, td, _ in triples:
            existing.add((sym, td))
        days_done += 1
        if days_done % 100 == 0:
            rate = days_done / max(time.time() - t0, 1e-9)
            eta_min = (days_total - days_done - days_404 - days_missing) / max(rate, 1e-9) / 60
            LOGGER.info("progress %d/%d weekdays | rows +%d | 404s %d | ETA %.0f min",
                        days_done, days_total, rows_inserted, days_404, eta_min)
        polite_sleep(SLEEP_SECONDS)

    LOGGER.info("DONE: weekdays processed=%d skipped-nontrading(404)=%d fetch-missing=%d rows_inserted=%d elapsed=%.0fs",
                days_done, days_404, days_missing, rows_inserted, time.time() - t0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    today = date.today()
    ap.add_argument("--start", type=str, default=(today - timedelta(days=365 * 10 + 4)).isoformat())
    ap.add_argument("--end", type=str, default=today.isoformat())
    args = ap.parse_args()
    backfill(date.fromisoformat(args.start), date.fromisoformat(args.end))


if __name__ == "__main__":
    main()
