"""add funds table + schemes.fund_id (fund-level rollup entity, plan E1)

`schemes.scheme_code` is AMFI plan-level: Direct-Growth and Regular-IDCW of
one fund are distinct rows holding identical portfolios, which double-counts
consensus. This migration adds the missing fund-level entity:

  funds(id UUID PK, amc_id FK, base_name, normalized_base_name,
        UNIQUE(amc_id, normalized_base_name))
  schemes.fund_id UUID NULL REFERENCES funds(id)

History-preserving: no scheme rows are dropped or merged; linking is additive.
Backfill lives in scripts/backfill_fund_rollup.py (backup-first, idempotent).

Revision ID: e5f8a2b3c6d1
Revises: b3a7e5c1d904
Create Date: 2026-08-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f8a2b3c6d1"
down_revision: Union[str, Sequence[str], None] = "b3a7e5c1d904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("funds"):
        op.create_table(
            "funds",
            sa.Column("id", sa.UUID(), nullable=False,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("amc_id", sa.UUID(), nullable=True),
            sa.Column("base_name", sa.Text(), nullable=False),
            sa.Column("normalized_base_name", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["amc_id"], ["amcs.id"]),
            sa.UniqueConstraint("amc_id", "normalized_base_name",
                                name="uq_funds_amc_normbase"),
        )
    op.create_index("ix_funds_normalized_base", "funds", ["normalized_base_name"],
                    if_not_exists=True)

    if not any(c["name"] == "fk_schemes_fund_id"
               for c in sa.inspect(bind).get_foreign_keys("schemes")):
        op.add_column("schemes", sa.Column("fund_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            "fk_schemes_fund_id", "schemes", "funds", ["fund_id"], ["id"]
        )
    op.create_index("ix_schemes_fund_id", "schemes", ["fund_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_schemes_fund_id", table_name="schemes")
    op.drop_constraint("fk_schemes_fund_id", "schemes", type_="foreignkey")
    op.drop_column("schemes", "fund_id")
    op.drop_index("ix_funds_normalized_base", table_name="funds")
    op.drop_table("funds")
