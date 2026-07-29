"""ADD-USER-ONBOARDING-COMPLETED: ACC-01.4 首次使用引导标记字段

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-07-29 19:30:00.000000

背景：
- FirstUseGuide 原先使用 localStorage 判断是否显示教程，存在不区分用户、
  换浏览器/清缓存后重复弹出、登录也触发等问题
- 改为后端 User.onboarding_completed 字段持久化标记：
  - 注册时默认 False
  - 完成/跳过引导后 PUT /users/me/onboarding 设为 True
  - 前端只读 user.onboarding_completed 决定是否弹出（不再依赖 localStorage）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="ACC-01.4: 是否已完成首次使用引导（注册后默认 False）",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
