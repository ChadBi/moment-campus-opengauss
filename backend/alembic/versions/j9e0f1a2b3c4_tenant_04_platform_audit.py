"""TEN-04.3: platform audit logs table

Revision ID: j9e0f1a2b3c4
Revises: i8d9e0f1a2b3
Create Date: 2026-07-24 12:00:00.000000

TEN-04.3 任务：
- 新建 platform_audit_logs 表，记录 super_admin 跨校动作
- 字段：操作者 / 目标学校 / 动作类型 / 旧值 / 新值 / 原因 / IP / UA / 时间
- 与 admin_operation_logs（校内管理员动作）解耦
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j9e0f1a2b3c4"
down_revision: Union[str, None] = "i8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("operator_id", sa.BigInteger(), nullable=True,
                  comment="操作者 user_id（super_admin）"),
        sa.Column("target_school_id", sa.BigInteger(), nullable=True,
                  comment="目标学校 ID（创建学校动作可能为 NULL）"),
        sa.Column("action", sa.String(length=50), nullable=False,
                  comment="动作类型：school.create / school.suspend / school.reactivate / subscription.assign / subscription.update"),
        sa.Column("old_value", sa.Text(), nullable=True, comment="旧值（JSON 文本）"),
        sa.Column("new_value", sa.Text(), nullable=True, comment="新值（JSON 文本）"),
        sa.Column("reason", sa.Text(), nullable=True, comment="操作原因/备注"),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_platform_audit_logs_operator_id"),
        "platform_audit_logs", ["operator_id"],
    )
    op.create_index(
        op.f("ix_platform_audit_logs_target_school_id"),
        "platform_audit_logs", ["target_school_id"],
    )
    op.create_index(
        op.f("ix_platform_audit_logs_action"),
        "platform_audit_logs", ["action"],
    )
    op.create_index(
        op.f("ix_platform_audit_logs_created_at"),
        "platform_audit_logs", ["created_at"],
    )
    op.create_index(
        "idx_platform_audit_operator", "platform_audit_logs",
        ["operator_id", "created_at"],
    )
    op.create_index(
        "idx_platform_audit_target", "platform_audit_logs",
        ["target_school_id", "action"],
    )


def downgrade() -> None:
    op.drop_index("idx_platform_audit_target", table_name="platform_audit_logs")
    op.drop_index("idx_platform_audit_operator", table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_created_at"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_action"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_target_school_id"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_operator_id"), table_name="platform_audit_logs")
    op.drop_table("platform_audit_logs")
