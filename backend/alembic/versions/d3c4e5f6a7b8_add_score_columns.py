"""add score columns

Revision ID: d3c4e5f6a7b8
Revises: c2b3d4e5f6a7
Create Date: 2026-07-05 13:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3c4e5f6a7b8"
down_revision: Union[str, None] = "c2b3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "reputation_score",
            sa.Numeric(5, 2),
            nullable=True,
            comment="用户信誉分（0-100），由 sp_update_reputation 计算",
        ),
    )
    op.add_column(
        "posts",
        sa.Column(
            "credibility_score",
            sa.Numeric(5, 2),
            nullable=True,
            comment="信息可信度（0-100），由 sp_recalc_credibility 计算",
        ),
    )


def downgrade() -> None:
    op.drop_column("posts", "credibility_score")
    op.drop_column("users", "reputation_score")
