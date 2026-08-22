"""add scheme_aum_history table

Monthly/quarterly average AUM (₹ crore) per scheme, sourced from the
AMFI scheme-wise Average AUM API (quarterly periods keyed by AMFI
scheme code). month_start is the first day of the reporting period's
opening month. UNIQUE (scheme_id, month_start) makes backfills
idempotent via ON CONFLICT DO UPDATE.

Revision ID: b3a7e5c1d904
Revises: 993d207fa8a9
Create Date: 2026-08-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3a7e5c1d904"
down_revision: Union[str, Sequence[str], None] = "993d207fa8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The baseline revision builds the schema via Base.metadata.create_all(),
    # which now includes SchemeAumHistory; on the live DB (stamped before this
    # model existed) it does not. Guard so both paths work.
    bind = op.get_bind()
    if sa.inspect(bind).has_table("scheme_aum_history"):
        op.create_index(
            "ix_scheme_aum_history_scheme_month",
            "scheme_aum_history",
            ["scheme_id", "month_start"],
            if_not_exists=True,
        )
        return
    op.create_table(
        "scheme_aum_history",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheme_id", sa.UUID(), nullable=True),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("avg_aum_cr", sa.Numeric(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["scheme_id"], ["schemes.id"]),
        sa.UniqueConstraint("scheme_id", "month_start", name="uq_scheme_aum_history_scheme_month"),
    )
    op.create_index(
        "ix_scheme_aum_history_scheme_month",
        "scheme_aum_history",
        ["scheme_id", "month_start"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("scheme_aum_history"):
        op.drop_index("ix_scheme_aum_history_scheme_month", table_name="scheme_aum_history")
        op.drop_table("scheme_aum_history")
