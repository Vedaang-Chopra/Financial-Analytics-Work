"""Unit tests for NSE bhavcopy CSV parsing and upsert logic (task C2).

All tests are offline — they read fixture files under tests/fixtures/bhavcopy/.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from market_data.bhavcopy import (
    EQUITY_SERIES,
    PriceRow,
    SymbolRow,
    build_symbol_isin_map,
    parse_full_bhavdata_csv,
    parse_old_bhavcopy_csv,
    resolve_price_rows,
    trading_days,
    upsert_prices,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bhavcopy"


@pytest.fixture(scope="module")
def old_rows() -> list[PriceRow]:
    return parse_old_bhavcopy_csv((FIXTURES / "cm15JAN2021bhav.csv").read_text())


@pytest.fixture(scope="module")
def full_rows() -> list[SymbolRow]:
    return parse_full_bhavdata_csv(
        (FIXTURES / "sec_bhavdata_full_21082026.csv").read_text()
    )


# ---------------------------------------------------------------------------
# Old-format parser (cm*bhav.csv — has ISIN)
# ---------------------------------------------------------------------------

def test_old_format_parses_isin_close_volume(old_rows) -> None:
    by_isin = {r.isin: r for r in old_rows}
    assert "INE002A01018" in by_isin  # RELIANCE
    rel = by_isin["INE002A01018"]
    assert rel.close == pytest.approx(1005.30)
    assert rel.volume == 1234567
    assert rel.symbol == "RELIANCE"
    tcs = by_isin["INE467B01029"]
    assert tcs.close == pytest.approx(3040.75)
    assert tcs.volume == 456789


def test_old_format_filters_non_equity_series_and_bad_rows(old_rows) -> None:
    isins = {r.isin for r in old_rows}
    # GS (government security) row must be excluded
    assert "IN0020260011" not in isins
    # zero close row must be excluded
    assert "INE888YYY018" not in isins
    # missing-ISIN row must be excluded
    assert all(r.isin for r in old_rows)
    assert len(old_rows) == 4  # RELIANCE, TCS, HDFCBANK, SOMETINC


# ---------------------------------------------------------------------------
# Full-bhavdata parser (no ISIN column)
# ---------------------------------------------------------------------------

def test_full_format_parses_close_volume(full_rows) -> None:
    by_symbol = {r.symbol: r for r in full_rows}
    rel = by_symbol["RELIANCE"]
    assert rel.close == pytest.approx(2935.60)
    assert rel.volume == 5123456
    assert rel.series == "EQ"
    assert len(full_rows) == 4  # 3 large-caps + NEWLIST; GS + zero-close dropped


def test_full_format_handles_padded_fields(full_rows) -> None:
    # Fields in this format are space-padded; symbols must come back clean.
    assert all(r.symbol == r.symbol.strip() for r in full_rows)
    assert {r.series for r in full_rows} <= EQUITY_SERIES


# ---------------------------------------------------------------------------
# Symbol->ISIN resolution
# ---------------------------------------------------------------------------

def test_build_symbol_isin_map() -> None:
    mapping = build_symbol_isin_map((FIXTURES / "EQUITY_L.csv").read_text())
    assert mapping["RELIANCE"] == "INE002A01018"
    assert mapping["TCS"] == "INE467B01029"
    assert mapping["HDFCBANK"] == "INE040A01034"
    assert mapping["NEWLIST"] == "INE777NEW017"


def test_resolve_price_rows_joins_and_counts_unmatched(full_rows) -> None:
    mapping = build_symbol_isin_map((FIXTURES / "EQUITY_L.csv").read_text())
    rows, unmatched = resolve_price_rows(full_rows, mapping)
    assert unmatched == 0
    assert len(rows) == 4
    by_isin = {r.isin: r for r in rows}
    assert by_isin["INE040A01034"].close == pytest.approx(1718.90)


def test_resolve_price_rows_reports_unknown_symbols() -> None:
    symbol_rows = [
        SymbolRow(symbol="KNOWN", series="EQ", close=10.0, volume=100),
        SymbolRow(symbol="UNKNOWN", series="EQ", close=11.0, volume=200),
    ]
    rows, unmatched = resolve_price_rows(symbol_rows, {"KNOWN": "INE000KNOW009"})
    assert [r.isin for r in rows] == ["INE000KNOW009"]
    assert unmatched == 1


def test_trading_days_skips_weekends() -> None:
    days = list(trading_days(date(2026, 8, 17), date(2026, 8, 23)))
    # Mon 17 .. Fri 21 (Sat 22 / Sun 23 excluded)
    assert [d.weekday() for d in days] == [0, 1, 2, 3, 4]
    assert date(2026, 8, 22) not in days


# ---------------------------------------------------------------------------
# Upsert idempotency (SQLite ON CONFLICT, no network)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    from mutual_fund_ingestion.agent.db import Base

    Base.metadata.create_all(
        engine, tables=[Base.metadata.tables["security_prices"]]
    )
    yield engine
    engine.dispose()


def _count(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM security_prices")).scalar()


def _get(engine, isin: str):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT close, volume FROM security_prices WHERE isin = :i"
            ),
            {"i": isin},
        ).fetchone()


def test_upsert_inserts_then_updates_idempotently(sqlite_engine) -> None:
    d = date(2026, 8, 21)
    url = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_21082026.csv"

    rows1 = [
        PriceRow(isin="INE002A01018", close=2935.60, volume=5123456),
        PriceRow(isin="INE467B01029", close=3140.85, volume=1234567),
    ]
    inserted, skipped = upsert_prices(sqlite_engine, rows1, d, url)
    assert (inserted, skipped) == (2, 0)
    assert _count(sqlite_engine) == 2

    # Same day again with a corrected close → UPDATE not duplicate insert.
    rows2 = [
        PriceRow(isin="INE002A01018", close=2936.00, volume=6000000),
        PriceRow(isin="INE040A01034", close=1718.90, volume=3456789),  # new
    ]
    upserted, skipped = upsert_prices(sqlite_engine, rows2, d, url)
    assert (upserted, skipped) == (2, 0)
    assert _count(sqlite_engine) == 3

    rel = _get(sqlite_engine, "INE002A01018")
    assert float(rel[0]) == pytest.approx(2936.00)
    assert rel[1] == 6000000


def test_upsert_skips_invalid_rows(sqlite_engine) -> None:
    d = date(2026, 8, 20)
    rows = [
        PriceRow(isin="", close=10.0, volume=1),
        PriceRow(isin="INE002A01018", close=2900.0, volume=10),
    ]
    inserted, skipped = upsert_prices(
        sqlite_engine, rows, d, "https://example.test/x.csv"
    )
    assert (inserted, skipped) == (1, 1)
