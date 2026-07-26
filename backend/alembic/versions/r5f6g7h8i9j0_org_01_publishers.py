"""ORG-01: 官方发布主体（publisher_profiles / publisher_memberships / post_templates）

Revision ID: r5f6g7h8i9j0
Revises: q5e6f7a8b9c0
Create Date: 2026-07-25 09:00:00.000000

ORG-01 任务：
- 新建 publisher_profiles 表：部门/社团/服务组织认证主页
  字段：id / school_id / name / type / intro / logo_url / location_id /
        service_hours / contact / verified_status / verified_at / verified_by /
        verify_note / view_count / subscribe_count / share_count /
        valid_feedback_count / invalid_feedback_count / zero_result_count /
        created_at / updated_at / is_deleted / deleted_at
- 新建 publisher_memberships 表：发布主体成员关系
  字段：id / publisher_id / user_id / role / joined_at / created_at / updated_at
- 新建 post_templates 表：高频场景发布模板（营业时间/讲座/失物/通知）
  字段：id / school_id / publisher_id / name / title_template / content_template /
        category_id / post_type_id / scene / sort_order / is_active /
        created_at / updated_at
- posts 表新增 publisher_id 列（可空，外键 SET NULL），用于关联官方发布主体

关键约束：
- verified_status 只能由 admin 审核流转（pending/verified/revoked/rejected）
- 认证不代表内容免审：publisher_id 关联的帖子仍走原 post_status 审核流程
- 三校隔离：school_id 来自 TenantContext，跨校访问统一 404
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r5f6g7h8i9j0"
down_revision: Union[str, None] = "q5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # publisher_profiles：官方发布主体认证主页
    # ============================================================
    op.create_table(
        "publisher_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False,
                  comment="所属学校 ID（TEN-02 三校隔离）"),
        sa.Column("name", sa.String(length=100), nullable=False,
                  comment="主体名称"),
        sa.Column("type", sa.String(length=20), nullable=False,
                  comment="主体类型：department/club/service_org"),
        sa.Column("intro", sa.Text(), nullable=True, comment="简介"),
        sa.Column("logo_url", sa.String(length=500), nullable=True,
                  comment="Logo URL"),
        sa.Column("location_id", sa.BigInteger(), nullable=True,
                  comment="服务地点 ID（关联 locations）"),
        sa.Column("service_hours", sa.String(length=200), nullable=True,
                  comment="服务时间"),
        sa.Column("contact", sa.String(length=255), nullable=True,
                  comment="联系方式"),
        sa.Column("verified_status", sa.String(length=20), nullable=False,
                  server_default="pending",
                  comment="认证状态：pending/verified/revoked/rejected（仅 admin 可流转）"),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verified_by", sa.BigInteger(), nullable=True,
                  comment="审核人 user_id"),
        sa.Column("verify_note", sa.Text(), nullable=True,
                  comment="审核备注/原因"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subscribe_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("share_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_feedback_count", sa.Integer(), nullable=False, server_default="0",
                  comment="有效性反馈-有效数"),
        sa.Column("invalid_feedback_count", sa.Integer(), nullable=False, server_default="0",
                  comment="有效性反馈-无效数"),
        sa.Column("zero_result_count", sa.Integer(), nullable=False, server_default="0",
                  comment="零结果关联需求聚合（用户标记该主体内容未找到所需）"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_publisher_profiles_school_id"),
        "publisher_profiles", ["school_id"],
    )
    op.create_index(
        op.f("ix_publisher_profiles_verified_status"),
        "publisher_profiles", ["verified_status"],
    )
    op.create_index(
        "idx_publisher_school_status",
        "publisher_profiles", ["school_id", "verified_status"],
    )
    op.create_index(
        "idx_publisher_type",
        "publisher_profiles", ["school_id", "type"],
    )

    # ============================================================
    # publisher_memberships：发布主体成员关系
    # ============================================================
    op.create_table(
        "publisher_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("publisher_id", sa.BigInteger(), nullable=False,
                  comment="发布主体 ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False,
                  comment="成员 user_id"),
        sa.Column("role", sa.String(length=20), nullable=False,
                  server_default="member",
                  comment="成员角色：owner/admin/member"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["publisher_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publisher_id", "user_id", name="uq_publisher_membership"),
    )
    op.create_index(
        op.f("ix_publisher_memberships_publisher_id"),
        "publisher_memberships", ["publisher_id"],
    )
    op.create_index(
        op.f("ix_publisher_memberships_user_id"),
        "publisher_memberships", ["user_id"],
    )
    op.create_index(
        "idx_pm_user",
        "publisher_memberships", ["user_id", "role"],
    )

    # ============================================================
    # post_templates：高频场景发布模板
    # ============================================================
    op.create_table(
        "post_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False,
                  comment="所属学校 ID（TEN-02 三校隔离）"),
        sa.Column("publisher_id", sa.BigInteger(), nullable=True,
                  comment="关联发布主体（NULL 表示学校级公共模板）"),
        sa.Column("name", sa.String(length=100), nullable=False,
                  comment="模板名称"),
        sa.Column("title_template", sa.String(length=200), nullable=False,
                  comment="标题模板"),
        sa.Column("content_template", sa.Text(), nullable=False,
                  comment="内容模板（含占位符）"),
        sa.Column("category_id", sa.BigInteger(), nullable=True,
                  comment="预设分类 ID"),
        sa.Column("post_type_id", sa.BigInteger(), nullable=True,
                  comment="预设信息类型 ID"),
        sa.Column("scene", sa.String(length=30), nullable=False,
                  comment="场景：business_hours/lecture/lost/notification/other"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["publisher_id"], ["publisher_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_type_id"], ["post_types.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_post_templates_school_id"),
        "post_templates", ["school_id"],
    )
    op.create_index(
        op.f("ix_post_templates_publisher_id"),
        "post_templates", ["publisher_id"],
    )
    op.create_index(
        "idx_pt_school_scene",
        "post_templates", ["school_id", "scene", "is_active"],
    )

    # ============================================================
    # posts 表新增 publisher_id 列
    # ============================================================
    op.add_column(
        "posts",
        sa.Column("publisher_id", sa.BigInteger(), nullable=True,
                  comment="关联官方发布主体（NULL 表示普通用户发布）"),
    )
    op.create_index(
        op.f("ix_posts_publisher_id"),
        "posts", ["publisher_id"],
    )
    op.create_foreign_key(
        "fk_posts_publisher_id_publisher_profiles",
        "posts", "publisher_profiles",
        ["publisher_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # posts.publisher_id
    op.drop_constraint("fk_posts_publisher_id_publisher_profiles", "posts", type_="foreignkey")
    op.drop_index(op.f("ix_posts_publisher_id"), table_name="posts")
    op.drop_column("posts", "publisher_id")

    # post_templates
    op.drop_index("idx_pt_school_scene", table_name="post_templates")
    op.drop_index(op.f("ix_post_templates_publisher_id"), table_name="post_templates")
    op.drop_index(op.f("ix_post_templates_school_id"), table_name="post_templates")
    op.drop_table("post_templates")

    # publisher_memberships
    op.drop_index("idx_pm_user", table_name="publisher_memberships")
    op.drop_index(op.f("ix_publisher_memberships_user_id"), table_name="publisher_memberships")
    op.drop_index(op.f("ix_publisher_memberships_publisher_id"), table_name="publisher_memberships")
    op.drop_table("publisher_memberships")

    # publisher_profiles
    op.drop_index("idx_publisher_type", table_name="publisher_profiles")
    op.drop_index("idx_publisher_school_status", table_name="publisher_profiles")
    op.drop_index(op.f("ix_publisher_profiles_verified_status"), table_name="publisher_profiles")
    op.drop_index(op.f("ix_publisher_profiles_school_id"), table_name="publisher_profiles")
    op.drop_table("publisher_profiles")
