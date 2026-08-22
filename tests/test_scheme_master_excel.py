"""Tests for the AMFI scheme master Excel/CSV parser (Task B1).

No network: fixtures are real AMFI scheme master data snapshots stored under
tests/fixtures/scheme_master/ (CSV + xlsx variants of the same slice), plus
the in-repo historical SchemeData CSVs under data/datasets/.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mutual_fund_ingestion.agent.models import ParserResult
from mutual_fund_ingestion.agent.parser import route_parser
from mutual_fund_ingestion.agent.parser.scheme_master_excel import (
    parse_scheme_master_excel,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "scheme_master"
CSV_FIXTURE = FIXTURES / "amfi_scheme_master_sample.csv"
XLSX_FIXTURE = FIXTURES / "amfi_scheme_master_sample.xlsx"

MIN_CATEGORY_RATE = 0.80


def _load(path: Path, file_ext: str) -> ParserResult:
    content = path.read_bytes()
    return parse_scheme_master_excel(
        content,
        {"source_url": "https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?MF=0", "file_ext": file_ext},
    )


def test_router_registers_scheme_master_excel():
    assert route_parser("scheme_master", "xlsx") == "scheme_master_excel"
    assert route_parser("scheme_master", "xls") == "scheme_master_excel"
    # csv keeps its existing route
    assert route_parser("scheme_master", "csv") == "scheme_master_csv"


def test_parse_fixture_csv_snapshot():
    result = _load(CSV_FIXTURE, ".csv")
    assert not result.errors
    assert len(result.records) >= 400
    first = result.records[0]
    for field in ("scheme_code", "scheme_name", "amc_name", "category"):
        assert first.get(field), f"missing {field} in {first}"
    rate = sum(1 for r in result.records if r.get("category")) / len(result.records)
    assert rate >= MIN_CATEGORY_RATE, f"category extraction rate {rate:.3f} < {MIN_CATEGORY_RATE}"
    assert result.metadata["category_extraction_rate"] == pytest.approx(rate)


def test_parse_fixture_xlsx_workbook():
    result = _load(XLSX_FIXTURE, ".xlsx")
    assert not result.errors
    assert len(result.records) >= 400
    rate = sum(1 for r in result.records if r.get("category")) / len(result.records)
    assert rate >= MIN_CATEGORY_RATE, f"category extraction rate {rate:.3f} < {MIN_CATEGORY_RATE}"
    sample = result.records[0]
    assert sample["scheme_code"].isdigit()
    assert sample["sub_category"]  # Scheme Type -> sub_category


def test_parse_real_historical_schemedata_csv():
    """The in-repo AMFI SchemeData CSVs use the same header layout."""
    hist = REPO_ROOT / "data" / "datasets" / "list_of_mutual_funds" / "scheme_data" / "SchemeData0104232159SS.csv"
    if not hist.exists():
        pytest.skip("historical SchemeData CSV not present")
    result = _load(hist, ".csv")
    assert result.records, "no records parsed from historical scheme master"
    rate = sum(1 for r in result.records if r.get("category")) / len(result.records)
    assert rate >= MIN_CATEGORY_RATE, f"category extraction rate {rate:.3f} < {MIN_CATEGORY_RATE}"
    with_launch = [r for r in result.records if r.get("launch_date")]
    assert with_launch, "launch dates should be extracted"


def test_plan_option_split_and_launch_date():
    result = _load(XLSX_FIXTURE, ".xlsx")
    by_code = {r["scheme_code"]: r for r in result.records if r.get("scheme_code")}
    rec = by_code["100033"]
    assert rec["plan"] == "Regular"
    assert rec["option"] == "Growth"
    assert rec["launch_date"] is not None
    # A Direct-plan row somewhere in the snapshot must split to plan=Direct
    direct = [r for r in result.records if (r.get("plan") or "") == "Direct"]
    assert direct, "expected at least one Direct plan row"


def test_validate_then_upsert_wiring_sqlite(tmp_path):
    """Parser output flows through validate -> UpsertManager.upsert_canonical."""
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from mutual_fund_ingestion.agent.db import Base, Scheme
    from mutual_fund_ingestion.agent.upserts import UpsertManager
    from mutual_fund_ingestion.agent.validate import validate_scheme_master_record

    engine = create_engine(f"sqlite:///{tmp_path / 'b1.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    result = _load(CSV_FIXTURE, ".csv")
    records = [
        r for r in result.records
        if validate_scheme_master_record(r)[0] and r.get("category")
    ]
    assert records

    stats: dict = {}
    UpsertManager().upsert_canonical(
        session,
        records,
        "scheme_master",
        raw_artifact_id=uuid.uuid4(),
        source_url="test://fixture",
        stats=stats,
    )
    session.commit()

    rows = session.query(Scheme).all()
    assert rows
    with_cat = [s for s in rows if s.category]
    assert len(with_cat) / len(rows) >= MIN_CATEGORY_RATE
    spot = next(s for s in rows if s.scheme_code == "100033")
    assert spot.category == "Equity Scheme - Large & Mid Cap Fund"
    assert spot.sub_category == "Open Ended"
    session.close()
