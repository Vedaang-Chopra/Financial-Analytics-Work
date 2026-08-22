"""Tests: scheme -> AMC auto-linking on upsert (Phase A2).

Covers:
1. upsert_portfolio stamps amc_hint into record -> scheme gets amc_id
2. upsert_schemes resolves AMC via record['amc_name'] AND amc_hint
3. upsert_schemes conflict-update no longer wipes an existing amc_id
4. upsert_portfolio links existing orphaned schemes when the hint matches
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mutual_fund_ingestion.agent.db import Base, AMC, Scheme  # noqa: E402
from mutual_fund_ingestion.agent.upserts import UpsertManager  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # Live Postgres has documents_scheme_date_type_url_key; db.py doesn't yet
    # model it (other workstream). Recreate it so the Document upsert works.
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS documents_scheme_date_type_url_key "
                "ON documents (scheme_id, reporting_date, document_type, source_url)"
            )
        )
        # Live Postgres enforces portfolio_snapshots uniqueness via
        # uq_portfolio_snapshots_scheme_date; db.py models it as a plain Index.
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_snapshots_scheme_date "
                "ON portfolio_snapshots (scheme_id, reporting_date)"
            )
        )
        # holdings upsert conflict target (partial unique in live Postgres)
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_holdings_snapshot_security "
                "ON portfolio_holdings (snapshot_id, security_name, isin)"
            )
        )
    s = sessionmaker(bind=engine)()
    s.add(AMC(id=uuid.uuid4(), name="Axis Mutual Fund", normalized_name="axis"))
    s.add(AMC(id=uuid.uuid4(), name="ICICI Prudential Mutual Fund", normalized_name="icici prudential"))
    s.commit()
    yield s
    s.close()


def _upsert_portfolio(session, records, amc_name=None):
    mgr = UpsertManager()
    mgr.upsert_portfolio(
        session,
        records,
        raw_artifact_id=uuid.uuid4(),
        source_url="https://example.com/portfolio.xlsx",
        stats={},
        amc_name=amc_name,
    )
    session.commit()


def test_portfolio_amc_hint_creates_linked_scheme(session):
    recs = [{
        "scheme_name": "Axis Bluechip Fund",
        "reporting_date": "2026-07-31",
        "security_name": "Reliance Industries",
        "percentage_to_nav": 5.0,
    }]
    _upsert_portfolio(session, recs, amc_name="Axis Mutual Fund")
    sch = session.query(Scheme).filter(Scheme.scheme_name == "Axis Bluechip Fund").one()
    assert sch.amc_id is not None, "new scheme from portfolio upsert must be AMC-linked"


def test_portfolio_links_existing_orphan_scheme(session):
    orphan = Scheme(scheme_name="Axis Bluechip Fund", normalized_scheme_name="axis bluechip fund")
    session.add(orphan)
    session.commit()
    assert orphan.amc_id is None
    recs = [{
        "scheme_name": "Axis Bluechip Fund",
        "reporting_date": "2026-07-31",
        "security_name": "Reliance Industries",
        "percentage_to_nav": 5.0,
    }]
    _upsert_portfolio(session, recs, amc_name="Axis Mutual Fund")
    session.refresh(orphan)
    assert orphan.amc_id is not None, "existing orphan scheme must be linked when hint arrives"


def test_schemes_upsert_resolves_amc_name(session):
    mgr = UpsertManager()
    mgr.upsert_schemes(
        session,
        [{"scheme_code": "AX01", "scheme_name": "ICICI Prudential Bluechip Fund", "amc_name": "ICICI Prudential"}],
        raw_artifact_id=uuid.uuid4(),
        source_url="https://example.com/schemes.csv",
        stats={},
    )
    session.commit()
    sch = session.query(Scheme).filter(Scheme.scheme_code == "AX01").one()
    assert sch.amc_id is not None


def test_schemes_upsert_resolves_amc_hint(session):
    mgr = UpsertManager()
    mgr.upsert_schemes(
        session,
        [{"scheme_code": "AX02", "scheme_name": "Bluechip Fund", "amc_hint": "Axis Mutual Fund"}],
        raw_artifact_id=uuid.uuid4(),
        source_url="https://example.com/schemes.csv",
        stats={},
    )
    session.commit()
    sch = session.query(Scheme).filter(Scheme.scheme_code == "AX02").one()
    assert sch.amc_id is not None, "amc_hint metadata must resolve AMC linkage"


def test_schemes_upsert_preserves_existing_amc_id(session):
    amc = session.query(AMC).filter(AMC.normalized_name == "axis").one()
    existing = Scheme(scheme_code="AX03", scheme_name="Bluechip Fund", normalized_scheme_name="bluechip fund", amc_id=amc.id)
    session.add(existing)
    session.commit()
    mgr = UpsertManager()
    # re-upsert WITHOUT any amc info — must not wipe the link
    mgr.upsert_schemes(
        session,
        [{"scheme_code": "AX03", "scheme_name": "Bluechip Fund Renamed"}],
        raw_artifact_id=uuid.uuid4(),
        source_url="https://example.com/schemes.csv",
        stats={},
    )
    session.commit()
    session.refresh(existing)
    assert existing.amc_id == amc.id, "conflict-update must not clear amc_id"
