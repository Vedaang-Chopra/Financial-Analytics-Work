"""Yahoo Finance daily price history (secondary source for deep back-history).

Uses the public chart API: GET /v8/finance/chart/<SYMBOL>.NS?period1=&period2=&interval=1d
Returns daily OHLC + adjusted close + volume back to each stock's listing.
Screener remains the primary source for fundamentals; this only fills price_points.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone

import requests

LOGGER = logging.getLogger(__name__)

BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT_S = 20
MAX_RETRIES = 3


class YahooError(RuntimeError):
    pass


def yahoo_symbol(screener_slug: str, nse_code: str | None = None) -> str:
    """Map our stock identity to a Yahoo symbol (NSE suffix .NS, fallback .BO)."""
    base = (nse_code or screener_slug).upper().replace("&", "")
    return f"{base}.NS"


def fetch_daily(symbol: str, period1: int = 0, period2: int | None = None) -> dict:
    """Fetch full daily history for one Yahoo symbol. Returns raw chart JSON."""
    if period2 is None:
        period2 = int(datetime.now(timezone.utc).timestamp())
    url = f"{BASE}/{symbol}"
    params = {"period1": period1, "period2": period2, "interval": "1d"}
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params,
                                headers={"User-Agent": UA},
                                timeout=TIMEOUT_S)
            if resp.status_code == 429:
                wait = 30 * attempt
                LOGGER.warning("Yahoo 429 for %s; sleeping %ss", symbol, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(5 * attempt)
    raise YahooError(f"Yahoo fetch failed for {symbol}: {last_exc}")


def parse_daily(chart_json: dict) -> tuple[list[dict], dict]:
    """Parse chart JSON into daily price-point rows.

    Returns (rows, meta) where rows are dicts:
      {point_date, series='daily', open, high, low, close, adj_close, volume}
    and meta = {symbol, first_date, last_date, count}.
    """
    result = ((chart_json.get("chart") or {}).get("result") or [None])[0]
    if result is None:
        err = (chart_json.get("chart") or {}).get("error") or {}
        raise YahooError(f"no result: {err.get('description', 'unknown error')}")

    meta = result.get("meta") or {}
    symbol = meta.get("symbol")
    ts = result.get("timestamp") or []
    quote = (result.get("indicators") or {}).get("quote") or [{}]
    quote = quote[0] if quote else {}
    adj_closes = ((result.get("indicators") or {}).get("adjclose") or [{}])
    adj_closes = adj_closes[0].get("adjclose") if adj_closes else None

    rows: list[dict] = []
    for i, t in enumerate(ts):
        try:
            d = date.fromtimestamp(t)  # exchange-local date
        except (ValueError, OSError, OverflowError):
            continue
        o = quote.get("open", [None] * len(ts))[i] if quote.get("open") else None
        h = quote.get("high", [None] * len(ts))[i] if quote.get("high") else None
        l = quote.get("low", [None] * len(ts))[i] if quote.get("low") else None
        c = quote.get("close", [None] * len(ts))[i] if quote.get("close") else None
        v = quote.get("volume", [None] * len(ts))[i] if quote.get("volume") else None
        ac = adj_closes[i] if adj_closes and i < len(adj_closes) else None
        if c is None:
            continue  # skip dead rows
        rows.append({
            "point_date": d.isoformat(),
            "series": "daily",
            "open": round(float(o), 4) if o is not None else None,
            "high": round(float(h), 4) if h is not None else None,
            "low": round(float(l), 4) if l is not None else None,
            "close": round(float(c), 4),
            "adj_close": round(float(ac), 4) if ac is not None else None,
            "volume": int(v) if v is not None else None,
            "delivery_pct": None,
        })

    return rows, {
        "symbol": symbol,
        "first_date": rows[0]["point_date"] if rows else None,
        "last_date": rows[-1]["point_date"] if rows else None,
        "count": len(rows),
    }
