"""Task 2.2: 移除每日摘要与邮件通知相关字段

Revision ID: z5e6f7g8h9i0
Revises: y4d5e6f7g8h9
Create Date: 2026-07-27

调整说明：
- 「保存当前查询」功能：后端从未实现，无需迁移
- 「每日摘要」「邮件通知」：从 notification_preferences 表移除三个字段
  - site_digest_enabled: 每日摘要开关（默认关）
  - digest_time: 每日摘要投递时间（HH:MM，默认 09:00）
  - email_enabled: 邮件通知开关（默认关）

通知偏好由 7 类降为 6 类（instant/subscription/interaction/audit/governance/system）。
"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "z5e6f7g8h9i0"
down_revision: Union[str, None] = "y4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除 notification_preferences 表的三个字段
    op.drop_column("notification_preferences", "site_digest_enabled")
    op.drop_column("notification_preferences", "digest_time")
    op.drop_column("notification_preferences", "email_enabled")


def downgrade() -> None:
    # 回滚：恢复三个字段（默认值与原迁移一致）
    op.add_column(
        "notification_preferences",
        sa.Column(
            "site_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="每日摘要",
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "digest_time",
            sa.String(length=5),
            nullable=False,
            server_default="09:00",
            comment="每日摘要投递时间 HH:MM",
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="是否同步邮件通知",
        ),
    )
