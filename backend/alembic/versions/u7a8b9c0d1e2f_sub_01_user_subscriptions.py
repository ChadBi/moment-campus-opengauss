"""SUB-01: 用户级内容订阅（分类/地点/专题）

Revision ID: u7a8b9c0d1e2f
Revises: s6g7h8i9j0k1
Create Date: 2026-07-25 11:00:00.000000

SUB-01 任务：
- 新建 subscriptions 表：用户对分类/地点/专题的订阅关系
  字段：id / user_id / school_id / target_type / target_id / created_at
  唯一键：(user_id, school_id, target_type, target_id) —— 同一用户在同一学校对同一目标只能订阅一次
- target_type 取值：category / location / topic
- 订阅与通知严格按学校隔离：school_id 强制由 TenantContext 决定，跨校不可见
- 四类通知触发（由 app/services/subscription_notifier 实现）：
  * 新帖通知：帖子发布（status=published）时通知订阅该分类/地点/专题的用户
  * 更新通知：已发布帖子被实质修改回审后再次发布时通知
  * 过期通知：帖子 published → expired 时通知（GOV-02 复用）
  * 冲突通知：冲突报告被处理时通知报告人
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u7a8b9c0d1e2f"
down_revision: Union[str, None] = "s6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="订阅用户 ID",
        ),
        sa.Column(
            "school_id",
            sa.BigInteger(),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
            comment="学校 ID（TEN-02 三校隔离）",
        ),
        sa.Column(
            "target_type",
            sa.String(length=20),
            nullable=False,
            comment="订阅目标类型：category / location / topic",
        ),
        sa.Column(
            "target_id",
            sa.BigInteger(),
            nullable=False,
            comment="订阅目标 ID（categories.id / locations.id / topic_collections.id）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "school_id",
            "target_type",
            "target_id",
            name="uq_subscription_user_school_target",
        ),
    )
    # 查询索引：用户在某校的全部订阅（订阅页列表用）
    op.create_index(
        "idx_subscription_user_school",
        "subscriptions",
        ["user_id", "school_id"],
        unique=False,
    )
    # 查询索引：按目标检索订阅用户（通知触发用：给定 target_type+target_id 查订阅者）
    op.create_index(
        "idx_subscription_target",
        "subscriptions",
        ["target_type", "target_id", "school_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_subscription_target", table_name="subscriptions")
    op.drop_index("idx_subscription_user_school", table_name="subscriptions")
    op.drop_table("subscriptions")
