"""drop post is_top

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-05 13:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS is_top")


def downgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("is_top", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
