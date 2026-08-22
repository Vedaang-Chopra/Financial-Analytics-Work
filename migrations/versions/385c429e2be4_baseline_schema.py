"""baseline schema

Replicates the CURRENT live mutual_funds PostgreSQL schema (as of 2026-08-22)
so that `alembic upgrade head` on an empty database produces a schema
equivalent to the live one.

Strategy:
  1. Create all tables from the SQLAlchemy metadata
     (mutual_fund_ingestion.agent.db Base), which is what
     Base.metadata.create_all() has been doing historically.
  2. Hand-fix the known drift between metadata and the live DB:
     - live has UNIQUE constraints the models do not declare:
         portfolio_holdings_snapshot_security_isin_key
         portfolio_snapshots_scheme_id_reporting_date_key
     - the models declare column-level unique=True on amc_coverage.amc_id and
       scheme_coverage.scheme_id that do NOT exist in the live DB; drop them.
  3. Create the two partial unique indexes via raw SQL (autogenerate cannot
     express partial predicates portably):
         uq_instruments_isin
         uq_holdings_snapshot_security_null_isin

Revision ID: 385c429e2be4
Revises:
Create Date: 2026-08-22 06:04:25.395623
"""
from typing import Sequence, Union

from alembic import op

from mutual_fund_ingestion.agent.db import Base

# revision identifiers, used by Alembic.
revision: str = "385c429e2be4"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. All 24 tables exactly as create_all() has always built them.
    Base.metadata.create_all(bind=op.get_bind())

    # 2a. Live-only unique constraints the models don't declare.
    op.create_unique_constraint(
        "portfolio_holdings_snapshot_security_isin_key",
        "portfolio_holdings",
        ["snapshot_id", "security_name", "isin"],
    )
    op.create_unique_constraint(
        "portfolio_snapshots_scheme_id_reporting_date_key",
        "portfolio_snapshots",
        ["scheme_id", "reporting_date"],
    )

    # 2b. Model-only column-level unique=True constraints absent from live.
    op.drop_constraint("amc_coverage_amc_id_key", "amc_coverage", type_="unique")
    op.drop_constraint("scheme_coverage_scheme_id_key", "scheme_coverage", type_="unique")

    # 3. Partial unique indexes (raw SQL — partial predicates aren't portable).
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_instruments_isin
        ON instruments (isin) WHERE (isin IS NOT NULL)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_holdings_snapshot_security_null_isin
        ON portfolio_holdings (snapshot_id, security_name) WHERE (isin IS NULL)
        """
    )


def downgrade() -> None:
    # Drop the partial unique indexes first.
    op.execute("DROP INDEX IF EXISTS uq_holdings_snapshot_security_null_isin")
    op.execute("DROP INDEX IF EXISTS uq_instruments_isin")

    # Restore the model-level column unique constraints (reverse of 2b).
    op.create_unique_constraint(
        "amc_coverage_amc_id_key", "amc_coverage", ["amc_id"]
    )
    op.create_unique_constraint(
        "scheme_coverage_scheme_id_key", "scheme_coverage", ["scheme_id"]
    )

    # Drop the live-only unique constraints (reverse of 2a).
    op.drop_constraint(
        "portfolio_snapshots_scheme_id_reporting_date_key",
        "portfolio_snapshots",
        type_="unique",
    )
    op.drop_constraint(
        "portfolio_holdings_snapshot_security_isin_key",
        "portfolio_holdings",
        type_="unique",
    )

    # Drop everything else.
    Base.metadata.drop_all(bind=op.get_bind())
