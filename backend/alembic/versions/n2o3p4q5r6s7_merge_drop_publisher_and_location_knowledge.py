"""MERGE: drop_publisher (a6b7c8d9e0f1) + location_knowledge (b8c9d0e1f2a3)

Revision ID: n2o3p4q5r6s7
Revises: a6b7c8d9e0f1, b8c9d0e1f2a3
Create Date: 2026-08-06

仅合并两个 DDL 分支，不产生额外对象；实际 DDL 已在两个分支迁移中。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n2o3p4q5r6s7"
down_revision: Union[str, None] = ("a6b7c8d9e0f1", "b8c9d0e1f2a3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
