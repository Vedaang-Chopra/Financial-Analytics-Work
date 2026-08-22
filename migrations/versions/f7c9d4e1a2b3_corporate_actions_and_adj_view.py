"""corporate_actions table + security_prices_adj view (plan task E2)

Raw bhavcopy closes make a 10:1 split look like -90%. This migration adds:

  corporate_actions(isin, ex_date, action, ratio, source_url,
                    UNIQUE(isin, ex_date, action))
    - confirmed corporate actions only; rows here are the sole license to
      adjust prices (never auto-adjust without a confirmed row).

  security_prices_adj (view over security_prices)
    - raw close divided by the cumulative adjustment factor of all actions
      with ex_date <= trade_date... NO: factor applies to prices BEFORE
      ex_date. View computes adjusted_close = raw * cumfactor_before(t)/
      latest, i.e. back-adjusted series where the latest price equals raw.

Revision ID: f7c9d4e1a2b3
Revises: e5f8a2b3c6d1
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f7c9d4e1a2b3"
down_revision: Union[str, Sequence[str], None] = "e5f8a2b3c6d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("corporate_actions"):
        op.create_table(
            "corporate_actions",
            sa.Column("id", sa.UUID(), nullable=False,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("isin", sa.Text(), nullable=False),
            sa.Column("ex_date", sa.Date(), nullable=False),
            sa.Column("action", sa.Text(), nullable=False),
            sa.CheckConstraint(
                "action IN ('split','bonus','rights')", name="ck_ca_action"
            ),
            sa.Column("ratio", sa.Numeric(), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("isin", "ex_date", "action",
                                name="uq_corporate_actions_isin_ex_action"),
        )
        op.create_index("ix_corporate_actions_isin", "corporate_actions", ["isin"])

    # Back-adjusted price view. Adjustment semantics:
    #   ratio = new_shares / old_shares for splits/bonuses (e.g. 10 for 10:1).
    #   A holder pre-split owns the same value at price/ratio post-event, so
    #   PRE-event closes are multiplied by 1/ratio to be comparable.
    #   cumulative_factor(t) = product(1/ratio for actions with ex_date > t)
    #   adjusted_close(t)    = close(t) / cumulative_factor(t)
    #   -> most recent prices unchanged; history scaled into today's share basis.
    op.execute(
        """
        CREATE OR REPLACE VIEW security_prices_adj AS
        WITH actions AS (
            SELECT isin, ex_date,
                   CASE WHEN ratio > 0 THEN 1.0 / ratio ELSE 1.0 END AS adj
            FROM corporate_actions
        ),
        factors AS (
            SELECT sp.isin, sp.trade_date, sp.close,
                   COALESCE((
                       SELECT EXP(SUM(LN(a.adj)))
                       FROM actions a
                       WHERE a.isin = sp.isin AND a.ex_date > sp.trade_date
                   ), 1.0) AS cum_factor
            FROM security_prices sp
        )
        SELECT isin,
               trade_date,
               close                                  AS raw_close,
               ROUND((close * NULLIF(cum_factor, 0))::numeric, 6) AS adjusted_close,
               cum_factor
        FROM factors;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS security_prices_adj")
    op.drop_index("ix_corporate_actions_isin", table_name="corporate_actions")
    op.drop_table("corporate_actions")
