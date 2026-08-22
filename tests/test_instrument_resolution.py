"""Tests for UpsertManager.upsert_portfolio instrument resolution.

Focus: the name-fallback path added in Task A2 — holdings WITHOUT an ISIN
must resolve an existing NULL-ISIN instrument by normalized_name instead of
blind-inserting duplicates. Valid-ISIN lookups keep their existing behavior.

Runs against SQLite fixtures (same pattern as ``test_agent_db.py``); the only
extra step is creating the unique indexes that PostgreSQL already has, so the
PG-dialect ``ON CONFLICT`` statements used by ``upsert_portfolio`` compile and
match a constraint under SQLite too.
"""
from __future__ import annotations

import os
import tempfile
import unittest
import uuid

from sqlalchemy import text

from mutual_fund_ingestion.agent.db import (
    Instrument,
    PortfolioHolding,
    create_tables,
    get_session_maker,
)
from mutual_fund_ingestion.agent.upserts import UpsertManager
from utils.text_utils import normalize_amc_name

SOURCE_URL = "https://test.example.com/portfolio.xlsx"


def _record(security_name: str, isin: str | None) -> dict:
    return {
        "scheme_name": "Test Fund",
        "reporting_date": "2026-06-30",
        "security_name": security_name,
        "isin": isin,
        "sector": "Energy",
        "percentage_to_nav": 5.0,
    }


class InstrumentResolutionTests(unittest.TestCase):
    """Instrument resolution logic in upsert_portfolio."""

    def setUp(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._db_temp_path = db_path
        url = f"sqlite:///{db_path}"
        create_tables(url)
        self.session_maker = get_session_maker(url)
        # Unique indexes mirroring the live PostgreSQL schema, needed for the
        # ON CONFLICT clauses in upsert_portfolio to work under SQLite.
        with self.session_maker() as session:
            session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_test_snapshots "
                "ON portfolio_snapshots (scheme_id, reporting_date)"
            ))
            session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_test_documents "
                "ON documents (scheme_id, reporting_date, document_type, source_url)"
            ))
            session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_test_holdings "
                "ON portfolio_holdings (snapshot_id, security_name, isin)"
            ))
            session.commit()

    def tearDown(self):
        if hasattr(self, "_db_temp_path"):
            try:
                os.unlink(self._db_temp_path)
            except OSError:
                pass

    def _run_upsert(self, *records: dict) -> dict:
        manager = UpsertManager()
        stats: dict = {}
        with self.session_maker() as session:
            manager.upsert_portfolio(
                session,
                list(records),
                uuid.uuid4(),
                SOURCE_URL,
                stats,
            )
            session.commit()
        return stats

    def _instrument_count(self) -> int:
        with self.session_maker() as session:
            return session.query(Instrument).count()

    def test_missing_isin_resolves_by_normalized_name(self):
        """A NULL-ISIN holding reuses an existing instrument with the same normalized_name."""
        normalized = normalize_amc_name("Reliance Industries Limited")
        with self.session_maker() as session:
            session.add(Instrument(
                isin=None, name="Reliance Industries Ltd", normalized_name=normalized,
            ))
            session.commit()

        self._run_upsert(_record("Reliance Industries Limited", None))

        self.assertEqual(self._instrument_count(), 1)
        with self.session_maker() as session:
            holding = session.query(PortfolioHolding).one()
            instrument = session.query(Instrument).one()
        self.assertEqual(holding.instrument_id, instrument.id)
        self.assertIsNone(instrument.isin)

    def test_missing_isin_creates_only_one_instrument_across_runs(self):
        """Repeated NULL-ISIN holdings with the same name do not duplicate instruments."""
        self._run_upsert(_record("HDFC Bank Limited", None))
        self.assertEqual(self._instrument_count(), 1)

        # Second disclosure, same security, still no ISIN
        self._run_upsert(_record("HDFC Bank Limited", None))
        self.assertEqual(
            self._instrument_count(), 1,
            "name-fallback must prevent blind duplicate NULL-ISIN inserts",
        )

    def test_missing_isin_distinct_names_get_distinct_instruments(self):
        """Different normalized names are not collapsed into one instrument."""
        self._run_upsert(
            _record("HDFC Bank Limited", None),
            _record("Infosys Limited", None),
        )
        self.assertEqual(self._instrument_count(), 2)

    def test_valid_isin_lookup_prefers_isin_match(self):
        """Valid-ISIN behavior unchanged: ISIN match wins even if names differ."""
        with self.session_maker() as session:
            session.add(Instrument(
                isin="INE002A01018",
                name="RIL OLD NAME",
                normalized_name=normalize_amc_name("RIL OLD NAME"),
            ))
            session.commit()

        self._run_upsert(_record("Reliance Industries Limited", "INE002A01018"))

        self.assertEqual(self._instrument_count(), 1)
        with self.session_maker() as session:
            holding = session.query(PortfolioHolding).one()
            instrument = session.query(Instrument).one()
        self.assertEqual(holding.instrument_id, instrument.id)
        self.assertEqual(instrument.isin, "INE002A01018")

    def test_valid_isin_not_found_creates_new_instrument(self):
        """Unknown valid ISIN still creates a new instrument (existing behavior)."""
        self._run_upsert(_record("Tata Consultancy Services", "INE467B01029"))

        self.assertEqual(self._instrument_count(), 1)
        with self.session_maker() as session:
            instrument = session.query(Instrument).one()
        self.assertEqual(instrument.isin, "INE467B01029")

    def test_mixed_holdings_share_snapshot_without_duplicate_instruments(self):
        """Mixed batch: ISIN-backed and name-only securities resolve correctly."""
        with self.session_maker() as session:
            session.add(Instrument(
                isin="INE002A01018", name="Reliance Industries",
                normalized_name=normalize_amc_name("Reliance Industries"),
            ))
            session.commit()

        self._run_upsert(
            _record("Reliance Industries", "INE002A01018"),
            _record("Cash and Cash Equivalents", None),
            _record("Cash and cash equivalents", None),  # case-insensitive via normalize
        )

        self.assertEqual(self._instrument_count(), 2)
        with self.session_maker() as session:
            holdings = session.query(PortfolioHolding).all()
            self.assertEqual(len(holdings), 3)
            resolved = {str(h.instrument_id) for h in holdings}
            instruments = {str(i.id) for i in session.query(Instrument).all()}
        self.assertTrue(resolved.issubset(instruments))


if __name__ == "__main__":
    unittest.main()
