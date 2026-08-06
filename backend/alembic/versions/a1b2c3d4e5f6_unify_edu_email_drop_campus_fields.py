"""统一教育邮箱：删除 users.campus_email / users.student_id 字段

Revision ID: a1b2c3d4e5f6
Revises: f4b5c6d7a8b9
Create Date: 2026-08-06 00:00:00.000000

登录与校园认证统一为教育邮箱（用户决策）：
- 只保留一个邮箱字段 users.email，认证用登录邮箱发码验证
- 删除 users.student_id（无需学号）、users.campus_email（认证邮箱与登录邮箱同值）
- 保留 users.campus_verified / campus_verified_at
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f4b5c6d7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "campus_email")
    op.drop_column("users", "student_id")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column(
        "users",
        sa.Column("student_id", sa.String(length=50), nullable=True,
                  comment="B-01: 校园学号（认证通过后记录）"),
    )
    op.add_column(
        "users",
        sa.Column("campus_email", sa.String(length=255), nullable=True,
                  comment="B-01: 用于认证的校园邮箱"),
    )