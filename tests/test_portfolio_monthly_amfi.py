"""Unit tests for the AMFI monthly portfolio disclosure parser (no network).

Uses the local sample workbooks under data/datasets/Monthly Reports October 2024/.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from mutual_fund_ingestion.agent.models import ParserResult
from mutual_fund_ingestion.agent.parser import route_parser
from mutual_fund_ingestion.agent.parser.portfolio import _is_valid_isin
from mutual_fund_ingestion.agent.parser.portfolio_monthly_amfi import (
    SOURCE_DATASET,
    detect_amc,
    parse_portfolio_monthly_amfi,
    parse_portfolio_monthly_amfi_directory,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "datasets" / "Monthly Reports October 2024"
NIMF = SAMPLE_DIR / "NIMF-MONTHLY-PORTFOLIO-31-Oct-24.xls"
ABSL = SAMPLE_DIR / "Adityabirla.xls"
ICICI_DIR = SAMPLE_DIR / "icici"

pytestmark = pytest.mark.skipif(
    not SAMPLE_DIR.exists(), reason="sample workbooks not present"
)


def _parse(path: Path) -> ParserResult:
    md = {"file_ext": path.suffix, "source_file": path.name}
    return parse_portfolio_monthly_amfi(path.read_bytes(), md)


def test_router_registration():
    assert route_parser("portfolio_disclosure", "amfi_monthly_xlsx") == "portfolio_monthly_amfi"
    assert route_parser("portfolio_disclosure", "amfi_monthly_xls") == "portfolio_monthly_amfi"
    # existing routes untouched
    assert route_parser("portfolio_disclosure", "xlsx") == "portfolio_excel"


def test_detect_amc_from_filenames_and_context():
    assert detect_amc("NIMF-MONTHLY-PORTFOLIO-31-Oct-24.xls") == "Nippon India Mutual Fund"
    assert detect_amc("Adityabirla.xls") == "Aditya Birla Sun Life Mutual Fund"
    assert detect_amc("icici") == "ICICI Prudential Mutual Fund"
    assert detect_amc(None, {"amc_name": "Axis Mutual Fund"}) == "Axis Mutual Fund"
    assert detect_amc("unknown.bin", None, ["Parag Parikh Flexi Cap Fund"]) == \
        "Parag Parikh Mutual Fund"


@pytest.mark.skipif(not NIMF.exists(), reason="NIMF sample missing")
def test_parse_nimf_end_to_end():
    result = _parse(NIMF)
    assert isinstance(result, ParserResult)
    assert result.parser_name == "portfolio_monthly_amfi"
    assert result.dataset_type == "portfolio_disclosure"
    assert result.errors == []
    # NIMF alone discloses ~100 schemes per month
    schemes = {r["scheme_name"] for r in result.records}
    assert len(schemes) >= 80
    assert len(result.records) >= 3000
    # AMC detection
    assert result.metadata.get("amc_name") == "Nippon India Mutual Fund"
    # source dataset stamped in metadata and every record
    assert result.metadata.get("source_dataset") == SOURCE_DATASET
    assert all(r.get("source_dataset") == SOURCE_DATASET for r in result.records)
    # reporting date from 'as on' string, month-end
    assert all(r.get("reporting_date") == "2024-10-31" for r in result.records)
    # every holding has a valid ISIN or explicit None
    for r in result.records:
        assert r["security_name"]
        if r["isin"] is not None:
            assert _is_valid_isin(r["isin"]), r
    # junk section rows excluded (unless carrying a valid ISIN)
    from mutual_fund_ingestion.agent.parser.portfolio import JUNK_ROW_PATTERNS
    junk_re = re.compile("|".join(JUNK_ROW_PATTERNS), re.IGNORECASE)
    from mutual_fund_ingestion.agent.parser.portfolio_monthly_amfi import _is_junk
    for r in result.records:
        if _is_junk(r["security_name"]):
            assert r["isin"] and _is_valid_isin(r["isin"]), r
    # pct-to-NAV normalized to percent units: a large scheme sums near 100
    import collections
    sums = collections.defaultdict(float)
    for r in result.records:
        if r["percentage_to_nav"]:
            sums[r["scheme_name"]] += r["percentage_to_nav"]
    growth = next(s for s in sums if "GROWTH FUND" in s.upper())
    assert 60 <= sums[growth] <= 130


@pytest.mark.skipif(not ABSL.exists(), reason="ABSL sample missing")
def test_parse_absl_end_to_end():
    result = _parse(ABSL)
    assert result.errors == []
    schemes = {r["scheme_name"] for r in result.records}
    assert len(schemes) >= 80
    assert result.metadata.get("amc_name") == "Aditya Birla Sun Life Mutual Fund"
    assert all(r.get("reporting_date") == "2024-10-31" for r in result.records)
    for r in result.records:
        if r["isin"] is not None:
            assert _is_valid_isin(r["isin"]), r


@pytest.mark.skipif(not ICICI_DIR.exists(), reason="icici sample dir missing")
def test_parse_icici_directory_layout():
    result = parse_portfolio_monthly_amfi_directory(ICICI_DIR)
    assert result.errors == []
    schemes = {r["scheme_name"] for r in result.records}
    assert len(schemes) >= 100
    assert result.metadata.get("amc_name") == "ICICI Prudential Mutual Fund"
    # AMC detection on ICICI Prudential via directory name
    amcs = {r.get("amc_hint") for r in result.records}
    assert amcs == {"ICICI Prudential Mutual Fund"}
    assert all(r.get("reporting_date") == "2024-10-31" for r in result.records)
    for r in result.records:
        if r["isin"] is not None:
            assert _is_valid_isin(r["isin"]), r
    # scheme names resolved from in-sheet rows (not sheet codes)
    assert all(len(s) > 12 for s in schemes)


@pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="samples missing")
def test_all_samples_clean_and_amc_detected():
    files = [p for p in SAMPLE_DIR.iterdir()
             if p.is_file() and p.suffix.lower() in (".xlsx", ".xls")]
    assert len(files) >= 8
    total_schemes = set()
    for path in files:
        result = _parse(path)
        assert result.errors == [], (path.name, result.errors[:2])
        assert result.metadata.get("amc_name"), path.name
        schemes = {r["scheme_name"] for r in result.records}
        # no scheme name collapsed to a bare sheet code
        assert all(len(s) > 6 for s in schemes), (path.name, schemes)
        total_schemes |= schemes
    # directory layout family
    dir_result = parse_portfolio_monthly_amfi_directory(SAMPLE_DIR / "icici")
    total_schemes |= {r["scheme_name"] for r in dir_result.records}
    # Combined corpus covers ~500 schemes across the 9 sample sources
    assert len(total_schemes) >= 400
