"""Tests: portfolio_snapshots.amc_id resolution on upsert (Task A4).

Covers:
1. Snapshot amc_id is stamped from the scheme's amc_id (preferred path)
2. Fallback: source-URL domain matched against configs/amc_sources.yaml
3. resolve_amc_by_source_url unit behaviour (match / no-match / unknown AMC)
4. Conflict-update path never wipes an existing snapshot amc_id
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

from mutual_fund_ingestion.agent.db import Base, AMC, PortfolioSnapshot, Scheme  # noqa: E402
from mutual_fund_ingestion.agent.upserts import (  # noqa: E402
    UpsertManager,
    resolve_amc_by_source_url,
)


@pytest.fixture()
def session(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS documents_scheme_date_type_url_key "
                "ON documents (scheme_id, reporting_date, document_type, source_url)"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_snapshots_scheme_date "
                "ON portfolio_snapshots (scheme_id, reporting_date)"
            )
        )
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


@pytest.fixture()
def registry_yaml(tmp_path):
    """Minimal stand-in for configs/amc_sources.yaml."""
    path = tmp_path / "amc_sources.yaml"
    path.write_text(
        "sources:\n"
        "- seed_url: https://www.axisfundexample.com/downloads/\n"
        "  amc_name: Axis Mutual Fund\n"
        "- seed_url: https://mutualfund.iciciexample.com/forms-and-downloads/portfolio\n"
        "  amc_name: ICICI Prudential Mutual Fund\n",
        encoding="utf-8",
    )
    return path


def _upsert(session, records, source_url, amc_name=None):
    UpsertManager().upsert_portfolio(
        session,
        records,
        raw_artifact_id=uuid.uuid4(),
        source_url=source_url,
        stats={},
        amc_name=amc_name,
    )
    session.commit()


def test_snapshot_amc_id_prefers_scheme_link(session):
    recs = [{
        "scheme_name": "Axis Bluechip Fund",
        "reporting_date": "2026-07-31",
        "security_name": "Reliance Industries",
        "percentage_to_nav": 5.0,
    }]
    # Unrelated source URL: only the scheme link can provide the AMC
    _upsert(session, recs, "https://example.com/portfolio.xlsx", amc_name="Axis Mutual Fund")
    snap = session.query(PortfolioSnapshot).one()
    axis = session.query(AMC).filter(AMC.normalized_name == "axis").one()
    assert snap.amc_id == axis.id, "snapshot must inherit amc_id from its scheme"


def test_snapshot_amc_id_url_domain_fallback(session, registry_yaml, monkeypatch):
    import mutual_fund_ingestion.agent.upserts as upserts_mod

    monkeypatch.setattr(upserts_mod, "_AMC_SOURCES_YAML", registry_yaml)
    recs = [{
        "scheme_name": "Generic Balanced Advantage Fund",
        "reporting_date": "2026-07-31",
        "security_name": "Some Security",
        "percentage_to_nav": 5.0,
    }]
    # Scheme has no resolvable AMC; source URL domain matches the registry
    _upsert(
        session,
        recs,
        "https://www.axisfundexample.com/downloads/monthly-portfolio.xlsx",
        amc_name=None,
    )
    snap = session.query(PortfolioSnapshot).one()
    axis = session.query(AMC).filter(AMC.normalized_name == "axis").one()
    assert snap.amc_id == axis.id, (
        "unresolvable scheme must fall back to source-URL domain -> amc_sources.yaml"
    )


def test_resolve_amc_by_source_url_direct(session, registry_yaml):
    axis = session.query(AMC).filter(AMC.normalized_name == "axis").one()

    hit = resolve_amc_by_source_url(
        session, "https://www.axisfundexample.com/downloads/x.xlsx", config_path=registry_yaml
    )
    assert hit is not None and hit.id == axis.id

    miss = resolve_amc_by_source_url(
        session, "https://unknown-domain.example.com/x.xlsx", config_path=registry_yaml
    )
    assert miss is None

    missing_file = resolve_amc_by_source_url(
        session, "https://axisfundexample.com/x.xlsx", config_path=registry_yaml.parent / "nope.yaml"
    )
    assert missing_file is None


def test_conflict_update_does_not_wipe_existing_snapshot_amc_id(session, monkeypatch):
    import mutual_fund_ingestion.agent.upserts as upserts_mod

    # Point the registry at an empty dir so the URL fallback finds nothing
    monkeypatch.setattr(
        upserts_mod,
        "_AMC_SOURCES_YAML",
        upserts_mod._AMC_SOURCES_YAML.parent / "does_not_exist.yaml",
    )
    recs = [{
        "scheme_name": "Axis Bluechip Fund",
        "reporting_date": "2026-07-31",
        "security_name": "Reliance Industries",
        "percentage_to_nav": 5.0,
    }]
    _upsert(session, recs, "https://example.com/p.xlsx", amc_name="Axis Mutual Fund")
    snap = session.query(PortfolioSnapshot).one()
    before = snap.amc_id
    assert before is not None

    # Re-ingest with an unresolvable AMC context: existing link must survive
    _upsert(session, recs, "https://totally-unrelated.example.org/p.xlsx", amc_name=None)
    session.refresh(snap)
    assert snap.amc_id == before, "ON CONFLICT update must never clear an existing amc_id"


def test_snapshot_amc_id_stays_null_when_unresolvable(session):
    recs = [{
        "scheme_name": "Mystery Unknown Fund XYZ",
        "reporting_date": "2026-07-31",
        "security_name": "Some Security",
        "percentage_to_nav": 5.0,
    }]
    _upsert(session, recs, "https://unknown-domain.example.com/p.xlsx", amc_name=None)
    snap = session.query(PortfolioSnapshot).one()
    assert snap.amc_id is None, "never fabricate an AMC link"
