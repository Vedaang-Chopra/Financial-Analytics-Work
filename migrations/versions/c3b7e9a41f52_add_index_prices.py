"""add index_prices table

Benchmark index daily closes (NIFTY 50, NIFTY 500, NIFTY SMALLCAP 250,
NIFTY MIDCAP 150) sourced from the NSE archives daily all-index CSV
(ind_close_all_DDMMYYYY.csv).

Revision ID: c3b7e9a41f52
Revises: 385c429e2be4
Create Date: 2026-08-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3b7e9a41f52"
down_revision: Union[str, Sequence[str], None] = "385c429e2be4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The baseline revision (385c429e2be4) builds the schema via
    # Base.metadata.create_all(), which now includes IndexPrice. On a fresh
    # scratch DB that means index_prices already exists by the time this
    # revision runs; on the live DB (stamped at baseline before this model
    # was added) it does not. Guard so both paths work.
    bind = op.get_bind()
    if sa.inspect(bind).has_table("index_prices"):
        # Ensure the unique constraint/index exist even when create_all
        # built the table (create_all declares both via __table_args__).
        op.create_index(
            "ix_index_prices_symbol_date",
            "index_prices",
            ["index_symbol", "trade_date"],
            if_not_exists=True,
        )
        return
    op.create_table(
        "index_prices",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("index_symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("index_symbol", "trade_date", name="uq_index_prices_symbol_date"),
    )
    op.create_index(
        "ix_index_prices_symbol_date",
        "index_prices",
        ["index_symbol", "trade_date"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("index_prices"):
        op.drop_index("ix_index_prices_symbol_date", table_name="index_prices")
        op.drop_table("index_prices")
