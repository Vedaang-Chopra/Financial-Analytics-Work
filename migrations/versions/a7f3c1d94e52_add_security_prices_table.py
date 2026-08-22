"""add security_prices table

Task C2: full-market daily stock prices from NSE bhavcopy.

Creates:
  - security_prices (id UUID PK default gen_random_uuid(), isin TEXT NOT NULL,
    trade_date DATE NOT NULL, close NUMERIC NOT NULL, volume BIGINT,
    source_url TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (isin, trade_date))
  - ix_security_prices_isin_date ON security_prices(isin, trade_date)

NOTE: the baseline revision builds tables via Base.metadata.create_all(), and
the SecurityPrice ORM model now lives in mutual_fund_ingestion.agent.db, so
the table can already exist by the time this revision runs on a fresh
database. The upgrade therefore checks has_table() before creating anything,
which keeps both paths (fresh DB and live DB) correct and idempotent.

Revision ID: a7f3c1d94e52
Revises: 385c429e2be4
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "a7f3c1d94e52"
down_revision: Union[str, Sequence[str], None] = "385c429e2be4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "security_prices"
INDEX_NAME = "ix_security_prices_isin_date"


def _table_exists(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _index_exists(bind, name: str) -> bool:
    return name in [ix["name"] for ix in sa.inspect(bind).get_indexes(TABLE_NAME)]


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.UUID(), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("isin", sa.Text(), nullable=False),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("close", sa.Numeric(), nullable=False),
            sa.Column("volume", sa.BigInteger(), nullable=True),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("now()")),
            sa.UniqueConstraint("isin", "trade_date",
                                name="uq_security_prices_isin_trade_date"),
        )
    if not _index_exists(bind, INDEX_NAME):
        op.create_index(INDEX_NAME, TABLE_NAME, ["isin", "trade_date"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    if _table_exists(bind, TABLE_NAME):
        # Only drop if we own it — i.e. it was NOT created by create_all()
        # from the model metadata. Simplest safe policy for a new-table-only
        # revision: drop it (downgrade is only run deliberately).
        op.drop_table(TABLE_NAME)
