"""REC-01: user_recommendation_preferences 用户推荐隐私偏好表

Revision ID: t7d8e9f0a1b2
Revises: s6g7h8i9j0k1
Create Date: 2026-07-25 11:00:00.000000

REC-01.2 任务：
- 新建 user_recommendation_preferences 表：用户推荐隐私偏好（一对一，user_id 唯一）
  personalization_enabled: 个性化推荐开关（默认 True）
- 用户可关闭个性化推荐；关闭后改用冷启动（本校热门/最新/管理员推荐）
- 偏好按 user_id 隔离，跨校共用同一份开关（隐私设置不随学校切换而变）
- 现有用户首次访问偏好 API 时自动 upsert 默认行
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t7d8e9f0a1b2"
down_revision: Union[str, None] = "s6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_recommendation_preferences",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="用户 ID",
        ),
        sa.Column(
            "personalization_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="REC-01.2: 是否启用个性化推荐；关闭后改用冷启动",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", name="uq_user_recommendation_preference_user"),
    )
    op.create_index(
        "ix_user_recommendation_preferences_user_id",
        "user_recommendation_preferences",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_recommendation_preferences_user_id",
        table_name="user_recommendation_preferences",
    )
    op.drop_table("user_recommendation_preferences")
