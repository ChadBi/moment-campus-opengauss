"""COM-01: product plans, plan entitlements, school subscriptions, tenant usage daily

Revision ID: i8d9e0f1a2b3
Revises: h7c8d9e0f1a2
Create Date: 2026-07-24 11:00:00.000000

COM-01 任务：
- 新建 product_plans / plan_entitlements / school_subscriptions / tenant_usage_daily 四张表
- 预置 3 档套餐：trial(试用) / standard(标准) / operations(运营)
- 每档套餐的权益项：
    members_max / posts_max / storage_mb / ai_calls_daily
  其中：
    - trial: members_max=20(hard) / posts_max=50(hard) / storage_mb=200(soft) / ai_calls_daily=20(hard)
    - standard: members_max=200(hard) / posts_max=2000(hard) / storage_mb=2048(soft) / ai_calls_daily=200(hard)
    - operations: members_max=NULL(不限) / posts_max=NULL / storage_mb=10240(soft) / ai_calls_daily=2000(hard)
- 给江南大学（school_id=1）分配 operations 档 active 订阅，started_at=now(), expires_at=NULL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i8d9e0f1a2b3"
down_revision: Union[str, None] = "h7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 1. product_plans ===
    op.create_table(
        "product_plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_plans_code"), "product_plans", ["code"], unique=True)
    op.create_index("idx_product_plan_status_sort", "product_plans", ["status", "sort_order"])

    # === 2. plan_entitlements ===
    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("is_hard", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["product_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_plan_entitlement_plan_key", "plan_entitlements",
                    ["plan_id", "key"], unique=True)

    # === 3. school_subscriptions ===
    op.create_table(
        "school_subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["product_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_subscription_school_status", "school_subscriptions",
                    ["school_id", "status"])
    op.create_index("idx_subscription_status_expires", "school_subscriptions",
                    ["status", "expires_at"])
    op.create_index("idx_subscription_school_active", "school_subscriptions",
                    ["school_id", "status"])

    # === 4. tenant_usage_daily ===
    op.create_table(
        "tenant_usage_daily",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("members_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("posts_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("storage_used_mb", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ai_calls_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "usage_date", name="uq_usage_daily_school_date"),
    )
    op.create_index("idx_usage_daily_date", "tenant_usage_daily", ["usage_date"])
    op.create_index("idx_usage_daily_school_date", "tenant_usage_daily",
                    ["school_id", "usage_date"])

    # === 5. seed 3 档套餐 ===
    op.execute(
        """
        INSERT INTO product_plans (code, name, description, status, sort_order, created_at, updated_at)
        VALUES
            ('trial', '试用档', '体验基础功能，适合小规模评估', 'active', 10, NOW(), NOW()),
            ('standard', '标准档', '面向中等规模学校的标准额度', 'active', 20, NOW(), NOW()),
            ('operations', '运营档', '面向正式运营学校的全功能档', 'active', 30, NOW(), NOW())
        """
    )

    # === 6. seed 各套餐权益项 ===
    # trial
    op.execute(
        """
        INSERT INTO plan_entitlements (plan_id, key, limit_value, is_hard, description, created_at, updated_at)
        SELECT id, k, lv, hard, descr, NOW(), NOW() FROM product_plans, (
            VALUES
                ('members_max', 20, TRUE, '试用档：成员上限 20 人（硬限制）'),
                ('posts_max', 50, TRUE, '试用档：发布上限 50 条（硬限制）'),
                ('storage_mb', 200, FALSE, '试用档：存储 200MB（软限制，超出告警）'),
                ('ai_calls_daily', 20, TRUE, '试用档：AI 调用每日 20 次（硬限制，超出降级）')
        ) AS t(k, lv, hard, descr)
        WHERE code = 'trial'
        """
    )
    # standard
    op.execute(
        """
        INSERT INTO plan_entitlements (plan_id, key, limit_value, is_hard, description, created_at, updated_at)
        SELECT id, k, lv, hard, descr, NOW(), NOW() FROM product_plans, (
            VALUES
                ('members_max', 200, TRUE, '标准档：成员上限 200 人（硬限制）'),
                ('posts_max', 2000, TRUE, '标准档：发布上限 2000 条（硬限制）'),
                ('storage_mb', 2048, FALSE, '标准档：存储 2GB（软限制，超出告警）'),
                ('ai_calls_daily', 200, TRUE, '标准档：AI 调用每日 200 次（硬限制）')
        ) AS t(k, lv, hard, descr)
        WHERE code = 'standard'
        """
    )
    # operations
    op.execute(
        """
        INSERT INTO plan_entitlements (plan_id, key, limit_value, is_hard, description, created_at, updated_at)
        SELECT id, k, lv, hard, descr, NOW(), NOW() FROM product_plans, (
            VALUES
                ('members_max', NULL, FALSE, '运营档：成员不限（软限制）'),
                ('posts_max', NULL, FALSE, '运营档：发布不限（软限制）'),
                ('storage_mb', 10240, FALSE, '运营档：存储 10GB（软限制，超出告警）'),
                ('ai_calls_daily', 2000, TRUE, '运营档：AI 调用每日 2000 次（硬限制，超出降级）')
        ) AS t(k, lv, hard, descr)
        WHERE code = 'operations'
        """
    )

    # === 7. 给江南大学（school_id=1）分配 operations 档 active 订阅 ===
    # 仅在 schools 表中存在 id=1 时插入；若不存在则跳过，避免破坏空库场景
    op.execute(
        """
        INSERT INTO school_subscriptions
            (school_id, plan_id, status, started_at, expires_at, assigned_by, assigned_at, note, created_at, updated_at)
        SELECT
            s.id,
            pp.id,
            'active',
            NOW(),
            NULL,
            NULL,
            NOW(),
            'COM-01 seed：演示学校江南大学默认运营档订阅',
            NOW(),
            NOW()
        FROM schools s
        CROSS JOIN product_plans pp
        WHERE s.id = 1 AND pp.code = 'operations'
        AND NOT EXISTS (
            SELECT 1 FROM school_subscriptions sub
            WHERE sub.school_id = s.id AND sub.status = 'active'
        )
        """
    )


def downgrade() -> None:
    op.drop_index("idx_usage_daily_school_date", table_name="tenant_usage_daily")
    op.drop_index("idx_usage_daily_date", table_name="tenant_usage_daily")
    op.drop_table("tenant_usage_daily")

    op.drop_index("idx_subscription_school_active", table_name="school_subscriptions")
    op.drop_index("idx_subscription_status_expires", table_name="school_subscriptions")
    op.drop_index("idx_subscription_school_status", table_name="school_subscriptions")
    op.drop_table("school_subscriptions")

    op.drop_index("idx_plan_entitlement_plan_key", table_name="plan_entitlements")
    op.drop_table("plan_entitlements")

    op.drop_index("idx_product_plan_status_sort", table_name="product_plans")
    op.drop_index(op.f("ix_product_plans_code"), table_name="product_plans")
    op.drop_table("product_plans")
