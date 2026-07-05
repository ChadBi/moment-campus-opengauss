"""drop favorites

Revision ID: e4f5a6b7c8d9
Revises: d3c4e5f6a7b8
Create Date: 2026-07-05 13:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3c4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS favorites CASCADE")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS favorite_count")


def downgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("favorite_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "favorites",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_favorite_post_user", "favorites", ["post_id", "user_id"], unique=True)
    op.create_index("idx_favorite_user", "favorites", ["user_id", "created_at"], unique=False)
