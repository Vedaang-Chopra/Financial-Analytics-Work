"""Tests for mutual_fund_ingestion/analysis/consensus_panel.sql (Task D1).

Two layers:

1. ``test_sql_structure`` — offline parse check of the SQL file (no DB needed):
   required statements/columns present, statements split cleanly.

2. ``test_applies_to_scratch_schema`` — full apply against PostgreSQL using an
   isolated scratch schema seeded with minimal dummy rows, verifying the
   materialized view builds and aggregates correctly.

Note: SQLite is NOT supported for these tests (SQLite has no materialized
views, no ILIKE, no FILTER aggregates) — when PostgreSQL/psycopg2 are
unavailable we skip, documented via ``pytest.mark.skipif`` / runtime skip.
"""
from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = REPO_ROOT / "mutual_fund_ingestion" / "analysis" / "consensus_panel.sql"

sys.path.insert(0, str(REPO_ROOT))

from db_config import mutual_funds_url  # noqa: E402

try:
    import psycopg2
    import psycopg2.extensions
except ImportError:  # pragma: no cover - environment-dependent
    psycopg2 = None

DSN = mutual_funds_url()

pg_available = psycopg2 is not None


def _pg_reachable() -> bool:
    if not pg_available:
        return False
    try:
        conn = psycopg2.connect(DSN, connect_timeout=5)
    except Exception:
        return False
    conn.close()
    return True


# ---------------------------------------------------------------- layer 1 ----

def test_sql_structure():
    sql = SQL_PATH.read_text()
    # idempotent drop + materialized view create + lookup indexes
    assert re.search(r"DROP\s+MATERIALIZED\s+VIEW\s+IF\s+EXISTS\s+consensus_panel", sql)
    assert re.search(r"CREATE\s+MATERIALIZED\s+VIEW\s+consensus_panel\s+AS", sql)
    assert re.search(
        r"CREATE\s+UNIQUE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+\w+\s+ON\s+consensus_panel\s*\(isin,\s*qtr\)",
        sql,
    )
    # grain definition comes from quarter truncation of reporting_date
    assert "date_trunc('quarter'" in sql
    # join path
    assert "portfolio_holdings" in sql
    assert "portfolio_snapshots" in sql
    assert re.search(r"JOIN\s+schemes", sql)
    assert re.search(r"LEFT\s+JOIN\s+instruments", sql)
    # required outputs
    for col in (
        "holders_total",
        "holders_smallcap",
        "avg_pct_to_nav",
        "max_pct_to_nav",
        "total_aum_weighted_exposure_cr",
    ):
        assert f"AS {col}" in sql
    # smallcap segment rule from the plan
    assert re.search(r"category\s+ILIKE\s+'%small%'", sql)
    # statements are semicolon-separated (parseable batch); strip comments first
    clean = re.sub(r"--[^\n]*", "", sql)
    stmts = [s.strip() for s in clean.split(";") if s.strip()]
    assert len(stmts) >= 3


# ---------------------------------------------------------------- layer 2 ----

DUMMY_SCHEMA_SQL = """
CREATE TABLE schemes (
    id text PRIMARY KEY,
    amc_id text,
    scheme_code text,
    scheme_name text,
    normalized_scheme_name text,
    category text,
    sub_category text,
    scheme_type text,
    benchmark text,
    metadata_json json,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
CREATE TABLE instruments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    isin text,
    name text,
    normalized_name text,
    instrument_type text,
    issuer text,
    sector text,
    metadata_json json,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
CREATE TABLE portfolio_snapshots (
    id text PRIMARY KEY,
    amc_id text,
    scheme_id text REFERENCES schemes(id),
    reporting_date date,
    document_id uuid,
    source_url text,
    parser_version text,
    validation_status text,
    metadata_json json,
    created_at timestamptz DEFAULT now()
);
CREATE TABLE portfolio_holdings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id text REFERENCES portfolio_snapshots(id),
    instrument_id uuid,
    security_name text,
    isin text,
    sector text,
    asset_class text,
    quantity numeric,
    market_value numeric,
    market_value_currency text,
    percentage_to_nav numeric,
    coupon numeric,
    maturity_date date,
    rating text,
    metadata_json json,
    created_at timestamptz DEFAULT now()
);
CREATE TABLE scheme_aum_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_id text,
    month_start date,
    avg_aum_cr numeric,
    source_url text,
    created_at timestamptz DEFAULT now()
);
"""

DUMMY_DATA_SQL = """
-- two schemes hold ISIN X in Q1-2025; one is small-cap, one flexi-cap
INSERT INTO schemes (id, scheme_name, category) VALUES
    ('sc-1', 'Some Small Cap Fund', 'Equity Scheme - Small Cap Fund'),
    ('flx-1', 'Some Flexi Cap Fund', 'Equity Scheme - Flexi Cap Fund');
INSERT INTO instruments (isin, name) VALUES ('INE000TEST01', 'Test Industries Ltd.');
INSERT INTO portfolio_snapshots (id, scheme_id, reporting_date) VALUES
    ('snap-1', 'sc-1', '2025-03-31'),
    ('snap-2', 'flx-1', '2025-02-15');
INSERT INTO portfolio_holdings (snapshot_id, isin, percentage_to_nav) VALUES
    ('snap-1', 'INE000TEST01', 4.0),
    ('snap-2', 'INE000TEST01', 2.0);
INSERT INTO scheme_aum_history (scheme_id, month_start, avg_aum_cr) VALUES
    ('sc-1', '2025-03-01', 1000.0),
    ('sc-1', '2024-06-01', 800.0),   -- >12 months before qtr end: ignored
    ('flx-1', '2025-01-01', 500.0);
"""

EXPECTED_COLUMNS = [
    "isin", "qtr", "instrument_name", "holders_total", "holders_smallcap",
    "holders_largecap", "holders_midcap", "holders_flexicap", "holders_elss",
    "holders_index", "holders_other_category", "avg_pct_to_nav",
    "max_pct_to_nav", "latest_aum_cr_basis", "total_aum_weighted_exposure_cr",
]


@pytest.mark.skipif(not _pg_reachable(), reason="PostgreSQL or psycopg2 unavailable")
def test_applies_to_scratch_schema():
    """Apply consensus_panel.sql inside an isolated scratch schema with dummy
    tables, verify build + aggregates, then tear down."""
    conn = psycopg2.connect(DSN)
    schema = f"consensus_panel_test_{uuid.uuid4().hex[:8]}"
    try:
        cur = conn.cursor()
        cur.execute(f'CREATE SCHEMA "{schema}"')
        # Restrict search_path so every unqualified object in the SQL file
        # resolves inside the scratch schema only — public is untouched.
        cur.execute(f'SET search_path TO "{schema}"')
        conn.commit()

        cur.execute(DUMMY_SCHEMA_SQL)
        cur.execute(DUMMY_DATA_SQL)
        conn.commit()

        sql = SQL_PATH.read_text()
        cur.execute(sql)
        conn.commit()

        cur.execute("SELECT count(*) FROM consensus_panel")
        assert cur.fetchone()[0] == 1

        cur.execute("""
            SELECT instrument_name, holders_total, holders_smallcap,
                   holders_flexicap, avg_pct_to_nav, max_pct_to_nav,
                   latest_aum_cr_basis, total_aum_weighted_exposure_cr
            FROM consensus_panel
            WHERE isin = 'INE000TEST01' AND qtr = '2025-01-01'
        """)
        row = cur.fetchone()
        assert row is not None
        (name, total, small, flexi, avgpct, maxpct, aum_basis, wexp) = row
        assert name == "Test Industries Ltd."
        assert total == 2          # two distinct schemes
        assert small == 1          # one ILIKE '%small%' scheme
        assert flexi == 1
        assert float(avgpct) == pytest.approx(3.0)   # mean of 4.0, 2.0
        assert float(maxpct) == pytest.approx(4.0)
        assert aum_basis == 2      # both schemes have AUM within prior 12 months
        # weighted exposure: 4% * 1000cr + 2% * 500cr = 50cr
        assert float(wexp) == pytest.approx(50.0)

        # information_schema.columns excludes materialized views -> use pg catalogs
        cur.execute("""
            SELECT a.attname
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = 'consensus_panel' AND n.nspname = %s
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (schema,))
        got = [r[0] for r in cur.fetchall()]
        assert got == EXPECTED_COLUMNS

        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = %s AND tablename = 'consensus_panel'
              AND indexname LIKE 'ux%%'
        """, (schema,))
        assert cur.fetchone() is not None  # unique (isin, qtr) index exists
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        conn.commit()
        conn.close()


@pytest.mark.skipif(_pg_reachable(), reason="only meaningful without PostgreSQL")
@pytest.mark.skipif(pg_available, reason="psycopg2 installed")
def test_sqlite_unsupported_documented():
    """Documented fallback: SQLite cannot run this SQL (no materialized views /
    ILIKE / FILTER), so without PostgreSQL the suite skips rather than fails."""
    pytest.skip("SQLite has no materialized views; consensus_panel requires PostgreSQL")
