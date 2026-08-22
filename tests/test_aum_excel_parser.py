"""Unit tests for the AMFI Average-AUM parsers (aum_excel).

All fixtures are built in-memory — no network access.
"""
from __future__ import annotations

import json
from io import BytesIO

import openpyxl
import pytest

from mutual_fund_ingestion.agent.parser import aum_excel


# ---------------------------------------------------------------------------
# Fixture builders (mimic real AMFI layouts, verified 2026-08-22)
# ---------------------------------------------------------------------------

def _build_schemewise_xlsx() -> bytes:
    """Excel render of /api/average-aum-schemewise?...&excel=true."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Average Assets under Management (AAUM) for January - March 2026", None, None, None])
    ws.append(["AMFI Code", "Scheme NAV Name",
               "Excluding Fund of Funds - Domestic but including Fund of Funds - Overseas",
               "Fund Of Funds - Domestic"])
    # AMC header row -> current_amc
    ws.append(["360 ONE Mutual Fund", None, None, None])
    ws.append(["Open Ended", None, None, None])
    ws.append([122612, "360 ONE Dynamic Bond Fund - Regular Plan - Growth Option", 31850.15, 0])
    ws.append([122715, "360 ONE Dynamic Bond Fund Direct Plan Growth", 29852.99, 12.5])
    ws.append([None, None, None, None])
    # second AMC
    ws.append(["HDFC Mutual Fund", None, None, None])
    ws.append([119061, "HDFC Flexi Cap Fund - Growth", 28000.0, 0])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_industry_repo_xls() -> bytes:
    """MCR sheet layout of portal.amfiindia.com/spages/am{mon}{yyyy}repo.xls."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MCR"
    ws.append([None] * 11)
    ws.append(["Monthly Report for the month of July 2026", None, None, None, None,
               None, None, None, None, None, None])
    ws.append(["Sr", "Scheme Name", "No. of Schemes as on July 31, 2026",
               "No. of Folios as on July 31, 2026", "Funds Mobilized", "Repurchase/Redemption",
               "Net Inflow", "Net Assets Under Management",
               "Average Net Assets Under Management", "No. of segregated portfolios",
               "Net Assets in segregated portfolios"])
    ws.append(["A", "Open ended Schemes"] + [None] * 9)
    ws.append(["I", "Income/Debt Oriented Schemes"] + [None] * 9)
    ws.append(["i", "Overnight Fund", 38, 786208, 708935.346868, 668522.799665,
               40412.547203, 120911.583687, 133762.470742, 0, 0])
    ws.append(["ii", "Liquid Fund", 42, 3668470, 597426.207773, 478360.353727,
               119065.854045, 694140.423034, 727985.513595, 0, 0])
    ws.append(["Sub total \"A\"", None, None, None, None, None, None, None,
               861748.0, None, None])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _schemewise_json_payload() -> dict:
    return {
        "type": "data",
        "data": [
            {
                "strMFId": "0",
                "Mfname": "360 ONE Mutual Fund",
                "SchemeType_Desc": "Open Ended",
                "schemes": [
                    {
                        "SchemeNAVName": "360 ONE Balanced Hybrid Fund - Direct Plan - IDCW",
                        "AMFI_Code": 152073,
                        "AverageAumForTheMonth": {
                            "ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas": 26.09,
                            "FundOfFundsDomestic": 0,
                        },
                    },
                    {
                        "SchemeNAVName": "360 ONE Dynamic Bond Fund - Regular Plan - Growth Option",
                        "AMFI_Code": 122612,
                        "AverageAumForTheMonth": {
                            "ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas": 31850.15,
                            "FundOfFundsDomestic": 55.5,
                        },
                    },
                ],
            }
        ],
    }


SRC_URL = "https://www.amfiindia.com/api/average-aum-schemewise?strType=Typewise"


# ---------------------------------------------------------------------------
# period label -> month_start
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("January - March 2026", "2026-01-01"),
        ("April - June 2025", "2025-04-01"),
        ("July - September 2026", "2026-07-01"),
        ("October - December 2025", "2025-10-01"),
        ("July 2026", "2026-07-01"),
        (None, None),
        ("garbage", None),
    ],
)
def test_period_to_month_start(label, expected):
    assert aum_excel.period_to_month_start(label) == expected


# ---------------------------------------------------------------------------
# Scheme-wise Excel parser
# ---------------------------------------------------------------------------

def test_schemewise_excel_parses_records():
    content = _build_schemewise_xlsx()
    result = aum_excel.parse_amfi_schemewise_aum_excel(
        content,
        {"file_ext": ".xlsx", "source_url": SRC_URL},
    )
    assert result.dataset_type == "scheme_aum"
    assert result.parser_name == "aum_excel_schemewise_v1"
    assert not result.errors
    assert len(result.records) == 3
    assert result.metadata["month_start"] == "2026-01-01"
    assert result.metadata["industry_level"] is False


def test_schemewise_excel_amc_attribution_and_totals():
    result = aum_excel.parse_amfi_schemewise_aum_excel(
        _build_schemewise_xlsx(), {"file_ext": ".xlsx", "source_url": SRC_URL}
    )
    by_code = {r["amfi_scheme_code"]: r for r in result.records}

    r = by_code["122612"]
    assert r["amc_name"] == "360 ONE Mutual Fund"
    # fixture raw value is ₹ lakh; parser converts to ₹ crore (÷100)
    assert r["avg_aum_cr"] == pytest.approx(318.5015)
    assert r["avg_aum_excl_fof_domestic_cr"] == pytest.approx(318.5015)
    assert r["fof_domestic_cr"] == pytest.approx(0.0)

    # FoF domestic is added into the total
    r2 = by_code["122715"]
    assert r2["avg_aum_cr"] == pytest.approx((29852.99 + 12.5) / 100)

    # AMC header switch
    assert by_code["119061"]["amc_name"] == "HDFC Mutual Fund"

    # confidence reflects fully-attributed rows
    assert result.confidence == pytest.approx(0.95)


def test_router_sends_workbook_to_right_parser():
    schemewise = aum_excel.parse_amfi_aum_excel(
        _build_schemewise_xlsx(), {"file_ext": ".xlsx", "source_url": SRC_URL}
    )
    assert schemewise.parser_name == "aum_excel_schemewise_v1"

    industry = aum_excel.parse_amfi_industry_aum_excel(
        _build_industry_repo_xls(), {"file_ext": ".xls", "source_url": "x"}
    )
    assert industry.parser_name == "aum_excel_industry_repo_v1"


# ---------------------------------------------------------------------------
# Scheme-wise JSON parser
# ---------------------------------------------------------------------------

def test_schemewise_json_parses_records():
    payload = _schemewise_json_payload()
    result = aum_excel.parse_amfi_schemewise_aum_json(
        payload, {"source_url": SRC_URL, "period_label": "January - March 2026"}
    )
    assert not result.errors
    assert len(result.records) == 2
    rec = {r["amfi_scheme_code"]: r for r in result.records}["152073"]
    assert rec["amc_name"] == "360 ONE Mutual Fund"
    assert rec["scheme_name"].startswith("360 ONE Balanced Hybrid")
    # raw lakh value 26.09 → crore
    assert rec["avg_aum_cr"] == pytest.approx(0.2609)
    assert rec["month_start"] == "2026-01-01"

    total_rec = {r["amfi_scheme_code"]: r for r in result.records}["122612"]
    # raw lakh values converted to crore (÷100)
    assert total_rec["avg_aum_cr"] == pytest.approx((31850.15 + 55.5) / 100)


def test_schemewise_json_bad_payload():
    result = aum_excel.parse_amfi_schemewise_aum_json({"nope": True}, {"source_url": SRC_URL})
    assert result.confidence == 0.0
    assert result.records == []
    assert result.errors


def test_schemewise_json_roundtrip_via_json_module():
    payload = json.loads(json.dumps(_schemewise_json_payload()))
    result = aum_excel.parse_amfi_schemewise_aum_json(payload, {"source_url": "api"})
    assert len(result.records) == 2


# ---------------------------------------------------------------------------
# Legacy industry workbook parser (honest limitations)
# ---------------------------------------------------------------------------

def test_industry_repo_parses_category_rows_only():
    result = aum_excel.parse_amfi_industry_aum_excel(
        _build_industry_repo_xls(),
        {"file_ext": ".xls", "source_url": "https://portal.amfiindia.com/spages/amjul2026repo.xls"},
    )
    assert not result.errors
    names = [r["scheme_name"] for r in result.records]
    assert names == ["Overnight Fund", "Liquid Fund"]  # headers/subtotals excluded
    first = result.records[0]
    assert first["amc_name"] is None            # no AMC data exists in this source
    assert first["amfi_scheme_code"] is None    # no scheme codes exist either
    assert first["avg_aum_cr"] == pytest.approx(133762.470742)
    assert first["month_start"] == "2026-07-01"
    assert result.metadata["industry_level"] is True
    assert "no AMC/scheme codes" in result.metadata["note"]
