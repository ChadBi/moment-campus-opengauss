"""merge_rec01_sub01_heads

Revision ID: a871871f04ce
Revises: t7d8e9f0a1b2, u7a8b9c0d1e2f
Create Date: 2026-07-25 22:21:44.630967

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a871871f04ce'
down_revision: Union[str, None] = ('t7d8e9f0a1b2', 'u7a8b9c0d1e2f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
