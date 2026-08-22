"""Market data fetchers for NSE benchmark index daily closes.

Source (verified working 2026-08-22):
    https://archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv
  - published once per trading day; 404 on weekends / non-trading days
  - one CSV covers ALL indices (Nifty 50, Nifty 500, Nifty Smallcap 250,
    Nifty Midcap 150, ...), so one request per day serves every index
  - archive depth: files exist back to ~2012 (spotty before 2016)

Politeness: callers must issue requests sequentially with >=1s sleep.
"""
from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Iterator

import requests

ARCHIVES_BASE = "https://archives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/",
}

# Canonical thesis symbols -> exact "Index Name" label in the NSE CSV.
INDEX_LABELS: dict[str, str] = {
    "NIFTY 50": "Nifty 50",
    "NIFTY 500": "Nifty 500",
    "NIFTY SMALLCAP 250": "Nifty Smallcap 250",
    "NIFTY MIDCAP 150": "Nifty Midcap 150",
}


@dataclass(frozen=True)
class IndexClose:
    """One parsed (index, date, close) observation from the daily CSV."""

    index_label: str
    trade_date: date
    close: float


def daily_close_all_url(d: date) -> str:
    """Build the ind_close_all CSV URL for a given date."""
    return ARCHIVES_BASE.format(ddmmyyyy=d.strftime("%d%m%Y"))


def _match_row_date(raw: str, expected: date | None) -> date | None:
    """Resolve an ambiguous DD-MM-YYYY vs MM-DD-YYYY row date.

    The NSE archive switched between DD-MM-YYYY and MM-DD-YYYY over the
    years (verified 2026-08-22: 2021 files are DD-MM, Apr 2023 files are
    MM-DD, Jun 2024 files are DD-MM again). When the caller supplies the
    expected (URL) date, accept the row date only if one of the two
    interpretations matches it exactly; otherwise return None so the
    record can be skipped rather than stored under a swapped date.
    """
    for fmt in ("%d-%m-%Y", "%m-%d-%Y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        if expected is None or parsed == expected:
            return parsed
    return None


def parse_index_close_csv(text: str, trade_date: date | None = None) -> list[IndexClose]:
    """Parse an ind_close_all_DDMMYYYY.csv payload into IndexClose records.

    Pure function (no network) so it can be unit-tested with a fixture.
    Rows with missing/invalid closes are skipped. Pass ``trade_date`` (the
    date in the requested URL) to disambiguate the row's DD-MM vs MM-DD
    date formats; rows whose date cannot be reconciled with it are skipped.
    """
    records: list[IndexClose] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        label = (row.get("Index Name") or "").strip()
        if not label:
            continue
        close_raw = (row.get("Closing Index Value") or "").strip()
        try:
            close = float(close_raw)
        except (TypeError, ValueError):
            continue
        row_date = trade_date
        raw_date = (row.get("Index Date") or "").strip()
        if raw_date:
            row_date = _match_row_date(raw_date, trade_date)
        if row_date is None:
            continue
        records.append(IndexClose(index_label=label, trade_date=row_date, close=close))
    return records


def fetch_daily_close_all(
    d: date,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> list[IndexClose] | None:
    """Fetch and parse the daily all-index CSV for one date.

    Returns None for non-trading days (NSE returns 404), including
    weekends. Raises requests exceptions on transient network errors
    (callers decide retry policy).
    """
    sess = session or requests.Session()
    url = daily_close_all_url(d)
    resp = sess.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return parse_index_close_csv(resp.text, trade_date=d)


def select_closes(
    records: Iterable[IndexClose],
    symbols: Iterable[str] = tuple(INDEX_LABELS),
) -> Iterator[tuple[str, date, float]]:
    """Yield (canonical_symbol, trade_date, close) for the wanted indices."""
    wanted = {INDEX_LABELS[s]: s for s in symbols}
    for rec in records:
        sym = wanted.get(rec.index_label)
        if sym is not None:
            yield sym, rec.trade_date, rec.close


def weekday_range(start: date, end: date) -> Iterator[date]:
    """Yield Mon-Fri dates in [start, end]; weekends are never trading days."""
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            yield cur
        cur += timedelta(days=1)


def polite_sleep(seconds: float = 1.1) -> None:
    """Sleep between sequential NSE requests (politeness floor >=1s)."""
    time.sleep(seconds)
