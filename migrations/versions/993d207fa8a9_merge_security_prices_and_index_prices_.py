"""merge security_prices and index_prices branches

Revision ID: 993d207fa8a9
Revises: a7f3c1d94e52, c3b7e9a41f52
Create Date: 2026-08-22 06:24:53.298513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '993d207fa8a9'
down_revision: Union[str, Sequence[str], None] = ('a7f3c1d94e52', 'c3b7e9a41f52')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
