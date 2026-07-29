"""DROP-PUBLISHER: 彻底移除发布主体相关表与字段

Revision ID: a6b7c8d9e0f1
Revises: z5e6f7g8h9i0
Create Date: 2026-07-29 18:00:00.000000

背景：
- 「需要调整的地方1」增量整改已删除前端 publisher UI 与后端 api/publishers.py / api/admin_publishers.py
- 但数据库表 publisher_profiles / publisher_memberships / post_templates 与 posts.publisher_id 字段仍保留
- 本次迁移彻底 drop 这三张表与一个字段，恢复数据模型整洁

删除内容：
- posts.publisher_id 列（含外键 fk_posts_publisher_id_publisher_profiles 与索引 ix_posts_publisher_id）
- post_templates 表（含 3 索引）
- publisher_memberships 表（含 3 索引）
- publisher_profiles 表（含 4 索引）

downgrade 提供：
- 重建 publisher_profiles / publisher_memberships / post_templates 三表
- posts 表恢复 publisher_id 列与外键
- 注意：downgrade 仅恢复表结构，不恢复数据（已被 seed_data 重跑清空）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "z5e6f7g8h9i0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. posts 表移除 publisher_id 列
    # ============================================================
    op.drop_constraint("fk_posts_publisher_id_publisher_profiles", "posts", type_="foreignkey")
    op.drop_index(op.f("ix_posts_publisher_id"), table_name="posts")
    op.drop_column("posts", "publisher_id")

    # ============================================================
    # 2. post_templates 表（先 drop 索引再 drop 表）
    # ============================================================
    op.drop_index("idx_pt_school_scene", table_name="post_templates")
    op.drop_index(op.f("ix_post_templates_publisher_id"), table_name="post_templates")
    op.drop_index(op.f("ix_post_templates_school_id"), table_name="post_templates")
    op.drop_table("post_templates")

    # ============================================================
    # 3. publisher_memberships 表
    # ============================================================
    op.drop_index("idx_pm_user", table_name="publisher_memberships")
    op.drop_index(op.f("ix_publisher_memberships_user_id"), table_name="publisher_memberships")
    op.drop_index(op.f("ix_publisher_memberships_publisher_id"), table_name="publisher_memberships")
    op.drop_table("publisher_memberships")

    # ============================================================
    # 4. publisher_profiles 表
    # ============================================================
    op.drop_index("idx_publisher_type", table_name="publisher_profiles")
    op.drop_index("idx_publisher_school_status", table_name="publisher_profiles")
    op.drop_index(op.f("ix_publisher_profiles_verified_status"), table_name="publisher_profiles")
    op.drop_index(op.f("ix_publisher_profiles_school_id"), table_name="publisher_profiles")
    op.drop_table("publisher_profiles")


def downgrade() -> None:
    # ============================================================
    # 1. 重建 publisher_profiles 表
    # ============================================================
    op.create_table(
        "publisher_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("location_id", sa.BigInteger(), nullable=True),
        sa.Column("service_hours", sa.String(length=200), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("verified_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        sa.Column("verify_note", sa.Text(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subscribe_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("share_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_feedback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_feedback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("zero_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_publisher_profiles_school_id"), "publisher_profiles", ["school_id"])
    op.create_index(op.f("ix_publisher_profiles_verified_status"), "publisher_profiles", ["verified_status"])
    op.create_index("idx_publisher_school_status", "publisher_profiles", ["school_id", "verified_status"])
    op.create_index("idx_publisher_type", "publisher_profiles", ["school_id", "type"])

    # ============================================================
    # 2. 重建 publisher_memberships 表
    # ============================================================
    op.create_table(
        "publisher_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("publisher_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["publisher_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publisher_id", "user_id", name="uq_publisher_membership"),
    )
    op.create_index(op.f("ix_publisher_memberships_publisher_id"), "publisher_memberships", ["publisher_id"])
    op.create_index(op.f("ix_publisher_memberships_user_id"), "publisher_memberships", ["user_id"])
    op.create_index("idx_pm_user", "publisher_memberships", ["user_id", "role"])

    # ============================================================
    # 3. 重建 post_templates 表
    # ============================================================
    op.create_table(
        "post_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("publisher_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("title_template", sa.String(length=200), nullable=False),
        sa.Column("content_template", sa.Text(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        # 注：post_type_id 字段已随 w2b3c4d5e6f7_remove_post_type_unify_category 移除，downgrade 不重建
        sa.Column("scene", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["publisher_id"], ["publisher_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_templates_school_id"), "post_templates", ["school_id"])
    op.create_index(op.f("ix_post_templates_publisher_id"), "post_templates", ["publisher_id"])
    op.create_index("idx_pt_school_scene", "post_templates", ["school_id", "scene", "is_active"])

    # ============================================================
    # 4. posts 表恢复 publisher_id 列
    # ============================================================
    op.add_column(
        "posts",
        sa.Column("publisher_id", sa.BigInteger(), nullable=True,
                  comment="关联官方发布主体（NULL 表示普通用户发布）"),
    )
    op.create_index(op.f("ix_posts_publisher_id"), "posts", ["publisher_id"])
    op.create_foreign_key(
        "fk_posts_publisher_id_publisher_profiles",
        "posts", "publisher_profiles",
        ["publisher_id"], ["id"],
        ondelete="SET NULL",
    )
