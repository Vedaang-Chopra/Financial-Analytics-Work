"""Yahoo Finance daily price history (secondary source for deep back-history).

Uses the `yfinance` library (handles Yahoo's cookie/crumb session auth that
breaks raw HTTP calls). Returns daily OHLC + volume + dividends/splits back to
each stock's listing. Screener remains the primary source for fundamentals;
this only fills the 'daily' series in price_points.
"""

from __future__ import annotations

import logging
import time
from datetime import date

LOGGER = logging.getLogger(__name__)


class YahooError(RuntimeError):
    pass


def yahoo_symbol(screener_slug: str, nse_code: str | None = None) -> str:
    """Map our stock identity to a Yahoo symbol (NSE suffix .NS).

    Yahoo keeps '&' in symbols (e.g. 'ARE&M.NS'), so only map the slug when
    no NSE code is available.
    """
    base = (nse_code or screener_slug).upper()
    return f"{base}.NS"


def fetch_daily(symbol: str, period: str = "max") -> dict:
    """Fetch full daily history via yfinance. Returns {'history': DataFrame-like dict}."""
    import yfinance as yf

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            hist = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
            if hist is None or hist.empty:
                raise YahooError(f"empty history for {symbol}")
            return {"symbol": symbol, "frame": hist}
        except Exception as exc:
            last_exc = exc
            wait = 60 * attempt
            LOGGER.warning("yfinance attempt %d failed for %s (%s); sleeping %ss",
                           attempt, symbol, str(exc)[:80], wait)
            time.sleep(wait)
    raise YahooError(f"Yahoo fetch failed for {symbol}: {last_exc}")


def parse_daily(result: dict) -> tuple[list[dict], dict]:
    """Convert a fetch_daily result into daily price-point rows.

    Rows: {point_date, series='daily', open, high, low, close, adj_close,
           volume, delivery_pct=None}
    """
    frame = result["frame"]
    symbol = result.get("symbol")
    rows: list[dict] = []
    for idx, row in frame.iterrows():
        close = row.get("Close")
        if close is None or (isinstance(close, float) and close != close):  # NaN check
            continue
        d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])

        def _f(v):
            try:
                return round(float(v), 4)
            except (TypeError, ValueError):
                return None

        rows.append({
            "point_date": d.isoformat(),
            "series": "daily",
            "open": _f(row.get("Open")),
            "high": _f(row.get("High")),
            "low": _f(row.get("Low")),
            "close": _f(close),
            "adj_close": _f(row.get("Adj Close")),
            "volume": int(row["Volume"]) if row.get("Volume") == row.get("Volume") else None,
            "delivery_pct": None,
        })

    return rows, {
        "symbol": symbol,
        "first_date": rows[0]["point_date"] if rows else None,
        "last_date": rows[-1]["point_date"] if rows else None,
        "count": len(rows),
    }
