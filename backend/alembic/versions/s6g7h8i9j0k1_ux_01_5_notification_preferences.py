"""UX-01.5: notification_preferences 用户通知偏好表

Revision ID: s6g7h8i9j0k1
Revises: r5f6g7h8i9j0
Create Date: 2026-07-25 10:00:00.000000

UX-01.5 任务：
- 新建 notification_preferences 表：用户通知偏好（一对一，user_id 唯一）
  7 类开关：instant / site_digest / subscription / interaction / audit / governance / system
  digest_time: 每日摘要投递时间（HH:MM，默认 09:00）
  email_enabled: 是否同步邮件（预留，默认关）
- 安全账号通知不可全关（system/audit）：通过 API 层校验保证至少 instant=true
- 现有用户首次访问偏好 API 时自动 upsert 默认行
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s6g7h8i9j0k1"
down_revision: Union[str, None] = "r5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, unique=True, comment="用户 ID"),
        sa.Column("instant_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="站内即时通知"),
        sa.Column("site_digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="每日摘要"),
        sa.Column("subscription_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="订阅类"),
        sa.Column("interaction_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="互动类"),
        sa.Column("audit_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="审核类（安全账号通知不可全关）"),
        sa.Column("governance_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="治理类"),
        sa.Column("system_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="系统类（安全账号通知不可全关）"),
        sa.Column("digest_time", sa.String(length=5), nullable=False, server_default="09:00", comment="每日摘要投递时间 HH:MM"),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="是否同步邮件通知"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )
    op.create_index(
        "idx_notification_preference_user",
        "notification_preferences",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_notification_preference_user", table_name="notification_preferences")
    op.drop_table("notification_preferences")
