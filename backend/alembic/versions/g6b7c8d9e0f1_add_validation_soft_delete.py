"""add validation soft delete fields

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-05 13:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6b7c8d9e0f1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validation_records",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "validation_records",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.alter_column("validation_records", "is_deleted", server_default=None)


def downgrade() -> None:
    op.drop_column("validation_records", "deleted_at")
    op.drop_column("validation_records", "is_deleted")
