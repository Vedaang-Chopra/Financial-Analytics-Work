"""Unit tests for NSE index close CSV parsing (task C3) — no network."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from mutual_fund_ingestion.market_data.index_prices import (
    INDEX_LABELS,
    IndexClose,
    daily_close_all_url,
    parse_index_close_csv,
    select_closes,
    weekday_range,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def nse_daily_csv() -> str:
    return (FIXTURES_DIR / "nse_ind_close_all.csv").read_text(encoding="utf-8")


def test_daily_url_format() -> None:
    assert daily_close_all_url(date(2026, 8, 21)) == (
        "https://archives.nseindia.com/content/indices/ind_close_all_21082026.csv"
    )


def test_parse_csv_extracts_wanted_indices(nse_daily_csv: str) -> None:
    records = parse_index_close_csv(nse_daily_csv, trade_date=date(2026, 8, 21))
    by_label = {r.index_label: r for r in records}
    for sym, label in INDEX_LABELS.items():
        assert label in by_label, f"{label} missing from parsed records"
    assert by_label["Nifty 50"].close == pytest.approx(24252.0)
    assert by_label["Nifty Smallcap 250"].trade_date == date(2026, 8, 21)


def test_parse_csv_row_date_consistent_with_url(nse_daily_csv: str) -> None:
    # Row dates that match the requested (URL) date are kept.
    records = parse_index_close_csv(nse_daily_csv, trade_date=date(2026, 8, 21))
    assert len(records) > 0
    assert {r.trade_date for r in records} == {date(2026, 8, 21)}


def test_parse_csv_skips_rows_that_cannot_match_url_date(nse_daily_csv: str) -> None:
    # A wrong URL date cannot be reconciled with the row dates -> skip all.
    records = parse_index_close_csv(nse_daily_csv, trade_date=date(1999, 12, 31))
    assert records == []


def test_parse_csv_handles_mmdf_era_files() -> None:
    # Apr-2023-era files wrote MM-DD-YYYY ("04-06-2023" = April 6). The
    # parser must store them under the requested date, not June 4.
    csv_text = (
        "Index Name,Index Date,Closing Index Value\n"
        "Nifty 50,04-06-2023,17599.15\n"
    )
    recs = parse_index_close_csv(csv_text, trade_date=date(2023, 4, 6))
    assert [r.trade_date for r in recs] == [date(2023, 4, 6)]
    assert recs[0].close == pytest.approx(17599.15)
    # A genuinely inconsistent pair is rejected.
    assert parse_index_close_csv(csv_text, trade_date=date(2025, 1, 1)) == []


def test_parse_csv_skips_bad_rows() -> None:
    csv_text = (
        "Index Name,Index Date,Open Index Value,High Index Value,"
        "Low Index Value,Closing Index Value,Points Change,Change(%)\n"
        "Nifty 50,20-08-2021,100,110,99,105.5,1.0,.9\n"
        "Broken Index,20-08-2021,1,2,,notanumber,0,0\n"  # bad close -> skipped
        ",20-08-2021,1,2,0.5,50,0,0\n"  # empty name -> skipped
    )
    records = parse_index_close_csv(csv_text)
    assert len(records) == 1
    assert records[0].index_label == "Nifty 50"
    assert records[0].close == pytest.approx(105.5)


def test_select_closes_maps_labels_to_symbols(nse_daily_csv: str) -> None:
    records = parse_index_close_csv(nse_daily_csv)
    triples = dict((s, c) for s, _, c in select_closes(records))
    assert set(triples) == set(INDEX_LABELS)
    assert triples["NIFTY 50"] == pytest.approx(24252.0)


def test_weekday_range_skips_weekends() -> None:
    days = list(weekday_range(date(2026, 8, 17), date(2026, 8, 23)))  # Mon..Sun
    assert [d.strftime("%a") for d in days] == ["Mon", "Tue", "Wed", "Thu", "Fri"]


def test_fixture_is_real_nse_shape(nse_daily_csv: str) -> None:
    first = nse_daily_csv.splitlines()[0]
    assert first.startswith("Index Name,Index Date,Open Index Value")
