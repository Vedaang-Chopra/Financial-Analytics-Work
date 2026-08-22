"""NSE bhavcopy download and parsing for daily equity prices.

Verified working endpoints (probed 2026-08-22):
  1. Old-format bhavcopy (zip), ~2016-01 through ~2024-07:
       https://archives.nseindia.com/content/historical/EQUITIES/<YYYY>/<MON>/cm<DDMMMYYYY>bhav.csv.zip
     Columns: SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,
              TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,
     Has ISIN directly.

  2. Full bhavdata CSV, ~2019-10 through present:
       https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_<DDMMYYYY>.csv
     Columns: SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE,
              LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY,
              TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
     NOTE: no ISIN column — ISIN is resolved via the symbol map built from
     EQUITY_L.csv (https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv).

  3. The UDiFF common bhavcopy
     (BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.csv) returns 404 on both
     archives.nseindia.com and nsearchives.nseindia.com as of 2026-08-22.
"""
from __future__ import annotations

import csv
import io
import logging
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Iterator, Mapping, Optional

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

OLD_BHAVCOPY_URL = (
    "https://archives.nseindia.com/content/historical/"
    "EQUITIES/{year}/{mon}/cm{dd}{mon}{year}bhav.csv.zip"
)
FULL_BHAVDATA_URL = (
    "https://nsearchives.nseindia.com/products/content/"
    "sec_bhavdata_full_{ddmmyyyy}.csv"
)
EQUITY_L_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

# NSE switched from the old historical zips to sec_bhavdata_full around
# Jul/Aug 2024. For each date we try the era-appropriate format first and
# fall back to the other on 404, so exact boundary drift is handled.
FULL_FORMAT_PREFERRED_FROM = date(2024, 8, 1)

# Equity series kept when filtering rows (govt securities 'GS', TBills,
# ETFs/mutual fund series etc. are excluded).
EQUITY_SERIES = {"EQ", "BE", "BZ", "SM", "ST", "AM"}


@dataclass(frozen=True)
class PriceRow:
    """One security's price for one trade date."""

    isin: str
    close: float
    volume: Optional[int]
    symbol: str = ""


@dataclass(frozen=True)
class SymbolRow:
    """A parsed row keyed by SYMBOL (used when the file has no ISIN)."""

    symbol: str
    series: str
    close: float
    volume: Optional[int]


def _clean(value: str) -> str:
    return value.strip() if isinstance(value, str) else ""


def _to_float(value: str) -> Optional[float]:
    value = _clean(value)
    if not value or value == "-":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str) -> Optional[int]:
    f = _to_float(value)
    return None if f is None else int(round(f))


# ---------------------------------------------------------------------------
# Parsing (pure functions — unit-testable without network)
# ---------------------------------------------------------------------------

def parse_old_bhavcopy_csv(csv_text: str) -> list[PriceRow]:
    """Parse old-format cm*bhav.csv content into PriceRows.

    Header: SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,
            TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,(trailing comma)
    """
    rows: list[PriceRow] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for rec in reader:
        rec = {
            (_clean(k) or "").upper(): v
            for k, v in rec.items()
            if k is not None
        }
        isin = _clean(rec.get("ISIN", ""))
        series = _clean(rec.get("SERIES", "")).upper()
        if not isin or series not in EQUITY_SERIES:
            continue
        close = _to_float(rec.get("CLOSE", ""))
        if close is None or close <= 0:
            continue
        rows.append(
            PriceRow(
                isin=isin.upper(),
                close=close,
                volume=_to_int(rec.get("TOTTRDQTY", "")),
                symbol=_clean(rec.get("SYMBOL", "")).upper(),
            )
        )
    return rows


def parse_full_bhavdata_csv(csv_text: str) -> list[SymbolRow]:
    """Parse sec_bhavdata_full_<DDMMYYYY>.csv content into SymbolRows.

    Fields are space-padded ("SYMBOL, SERIES, DATE1, ..."); ISIN is absent.
    """
    rows: list[SymbolRow] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for rec in reader:
        rec = {
            (_clean(k) or "").upper(): v
            for k, v in rec.items()
            if k is not None
        }
        series = _clean(rec.get("SERIES", "")).upper()
        if series not in EQUITY_SERIES:
            continue
        close = _to_float(rec.get("CLOSE_PRICE", ""))
        if close is None or close <= 0:
            continue
        symbol = _clean(rec.get("SYMBOL", "")).upper()
        if not symbol:
            continue
        rows.append(
            SymbolRow(
                symbol=symbol,
                series=series,
                close=close,
                volume=_to_int(rec.get("TTL_TRD_QNTY", "")),
            )
        )
    return rows


def build_symbol_isin_map(equity_l_csv: str) -> dict[str, str]:
    """Build {SYMBOL: ISIN} from the EQUITY_L.csv master list."""
    mapping: dict[str, str] = {}
    reader = csv.DictReader(io.StringIO(equity_l_csv))
    for rec in reader:
        rec = {
            (_clean(k) or "").upper(): v
            for k, v in rec.items()
            if k is not None
        }
        symbol = _clean(rec.get("SYMBOL", "")).upper()
        isin = _clean(rec.get("ISIN NUMBER", "")).upper()
        if symbol and isin:
            mapping[symbol] = isin
    return mapping


def resolve_price_rows(
    symbol_rows: Iterable[SymbolRow], symbol_map: Mapping[str, str]
) -> tuple[list[PriceRow], int]:
    """Join SymbolRows to PriceRows via a symbol->ISIN map.

    Returns (rows, unmatched_count).
    """
    out: list[PriceRow] = []
    unmatched = 0
    seen: set[str] = set()
    for r in symbol_rows:
        if r.symbol in seen:
            # Same symbol can appear in multiple series; keep first EQ-class hit.
            pass
        isin = symbol_map.get(r.symbol)
        if not isin:
            unmatched += 1
            continue
        seen.add(r.symbol)
        out.append(PriceRow(isin=isin, close=r.close, volume=r.volume, symbol=r.symbol))
    return out, unmatched


def trading_days(start: date, end: date) -> Iterator[date]:
    """All weekdays in [start, end] inclusive (holidays handled as misses)."""
    d = start
    one = timedelta(days=1)
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += one


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

class BhavcopyClient:
    """Polite sequential fetcher for NSE bhavcopy files."""

    def __init__(
        self,
        sleep_seconds: float = 2.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.sleep_seconds = max(sleep_seconds, 1.0)  # politeness floor
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/csv,application/zip,*/*",
                "Referer": "https://www.nseindia.com/all-reports",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.symbol_map: dict[str, str] = {}
        self.consecutive_errors = 0

    # -- low level ----------------------------------------------------------

    def _get(self, url: str) -> Optional[bytes]:
        """GET with retry/backoff. None on definitive 404; raises on block."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:  # network hiccup
                last_exc = exc
                time.sleep(min(2 ** attempt * 2, 30))
                continue
            if resp.status_code == 200:
                self.consecutive_errors = 0
                return resp.content
            if resp.status_code == 404:
                self.consecutive_errors = 0
                return None
            # 403/429/5xx — rate limiting or block: back off hard.
            self.consecutive_errors += 1
            wait = min(2 ** attempt * 5, 60)
            logger.warning(
                "HTTP %s for %s (attempt %d/%d); backing off %ss",
                resp.status_code, url, attempt + 1, self.max_retries, wait,
            )
            time.sleep(wait)
        raise ConnectionError(
            f"Failed to fetch {url} after {self.max_retries} retries "
            f"(last error: {last_exc})"
        )

    def _polite_pause(self) -> None:
        time.sleep(self.sleep_seconds)

    # -- endpoints ----------------------------------------------------------

    def old_bhavcopy_url(self, d: date) -> str:
        mon = d.strftime("%b").upper()
        return OLD_BHAVCOPY_URL.format(year=d.year, mon=mon, dd=d.strftime("%d"))

    def full_bhavdata_url(self, d: date) -> str:
        return FULL_BHAVDATA_URL.format(ddmmyyyy=d.strftime("%d%m%Y"))

    def ensure_symbol_map(self) -> dict[str, str]:
        if not self.symbol_map:
            raw = self._get(EQUITY_L_URL)
            if raw is None:
                raise ConnectionError("EQUITY_L.csv unavailable (404)")
            self.symbol_map = build_symbol_isin_map(raw.decode("utf-8", "replace"))
            logger.info("Symbol->ISIN map loaded: %d symbols", len(self.symbol_map))
            self._polite_pause()
        return self.symbol_map

    def fetch_date(self, d: date) -> tuple[Optional[list[PriceRow]], str]:
        """Fetch prices for one trade date.

        Returns (price_rows_or_None_if_no_file, source_url_used_or_attempted).
        Raises ConnectionError if blocked/rate-limited after retries.
        """
        prefer_full = d >= FULL_FORMAT_PREFERRED_FROM
        order = ["full", "old"] if prefer_full else ["old", "full"]

        for which in order:
            if which == "old":
                url = self.old_bhavcopy_url(d)
            else:
                url = self.full_bhavdata_url(d)
            raw = self._get(url)
            self._polite_pause()
            if raw is None:
                continue  # 404 → try other format
            if which == "old":
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    name = zf.namelist()[0]
                    csv_text = zf.read(name).decode("utf-8", "replace")
                return parse_old_bhavcopy_csv(csv_text), url
            self.ensure_symbol_map()
            symbol_rows = parse_full_bhavdata_csv(raw.decode("utf-8", "replace"))
            rows, unmatched = resolve_price_rows(symbol_rows, self.symbol_map)
            if unmatched:
                logger.debug("%s: %d symbols had no ISIN mapping", d, unmatched)
            return rows, url

        return None, ""  # holiday / not published in either format


# ---------------------------------------------------------------------------
# Upsert (idempotent)
# ---------------------------------------------------------------------------

def _security_prices_table() -> Any:
    import uuid as _uuid

    from sqlalchemy import Column as _Column, Date as _Date, MetaData
    from sqlalchemy import Numeric as _Numeric, Table as _Table, Text as _Text
    from sqlalchemy import DateTime as _DateTime, func as _func
    from sqlalchemy import UUID as _UUID

    meta = MetaData()
    return _Table(
        "security_prices",
        meta,
        _Column("id", _UUID(as_uuid=True), primary_key=True,
                default=_uuid.uuid4),
        _Column("isin", _Text),
        _Column("trade_date", _Date),
        _Column("close", _Numeric),
        _Column("volume", _Text),
        _Column("source_url", _Text),
        _Column("created_at", _DateTime(timezone=True), default=_func.now()),
    )


def upsert_prices(
    target: Any, rows: Iterable[PriceRow], trade_date: date, source_url: str
) -> tuple[int, int]:
    """Insert/update security_prices rows for one trade date.

    ``target`` is a SQLAlchemy Engine or Connection. Uses
    ON CONFLICT (isin, trade_date) DO UPDATE so re-runs are idempotent.
    Returns (rows_upserted, rows_skipped_invalid).
    """
    payload = []
    skipped = 0
    for r in rows:
        if not r.isin or r.close is None:
            skipped += 1
            continue
        payload.append(
            {
                "isin": r.isin,
                "trade_date": trade_date,
                "close": r.close,
                "volume": r.volume,
                "source_url": source_url,
            }
        )
    if not payload:
        return 0, skipped

    security_prices = _security_prices_table()
    stmt = pg_insert(security_prices).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["isin", "trade_date"],
        set_={
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "source_url": stmt.excluded.source_url,
        },
    )
    if hasattr(target, "begin"):
        with target.begin() as conn:
            conn.execute(stmt)
    else:
        target.execute(stmt)
    return len(payload), skipped
