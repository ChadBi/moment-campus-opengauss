"""TEN-01: multi-tenant membership, invitation, settings, domain and school_id

Revision ID: h7c8d9e0f1a2
Revises: g6b7c8d9e0f1
Create Date: 2026-07-24 10:00:00.000000

TEN-01 任务：
- 新建 school_memberships / school_invitations / school_settings / school_domains 四张表
- categories / tags 增加 school_id 列（默认 1=江南大学），唯一约束改为 (school_id, code/slug)
- 旧 11 用户无损回填为江南大学 active 成员
  （role 映射：admin/super_admin→admin，user→member；不改密码/邮箱）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h7c8d9e0f1a2"
down_revision: Union[str, None] = "g6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 1. school_memberships ===
    op.create_table(
        "school_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'member'"),
                  comment="成员角色：member/admin（super_admin 仍是平台角色在 user 表）"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'"),
                  comment="成员状态：active/invited/suspended"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("invited_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_membership_user_school", "school_memberships",
                    ["user_id", "school_id"], unique=True)
    op.create_index("idx_membership_school_role", "school_memberships",
                    ["school_id", "role"])
    op.create_index("idx_membership_school_status", "school_memberships",
                    ["school_id", "status"])
    op.create_index("idx_membership_default", "school_memberships",
                    ["user_id", "is_default"])

    # === 2. school_invitations ===
    op.create_table(
        "school_invitations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'member'")),
        sa.Column("invitation_code", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'expires'"),
                  comment="邀请状态：expires/accepted/declined"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_school_invitations_email"), "school_invitations",
                    ["email"])
    op.create_index("idx_invitation_school_status", "school_invitations",
                    ["school_id", "status"])
    op.create_index("idx_invitation_email_status", "school_invitations",
                    ["email", "status"])
    op.create_index("idx_invitation_code", "school_invitations",
                    ["invitation_code"], unique=True)

    # === 3. school_settings ===
    op.create_table(
        "school_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("site_name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("require_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_anonymous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_comments", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("publish_frequency", sa.Integer(), nullable=False, server_default=sa.text("10"),
                  comment="每日发布上限（0 表示不限）"),
        sa.Column("image_limit", sa.Integer(), nullable=False, server_default=sa.text("9"),
                  comment="单帖图片上限"),
        sa.Column("default_validity_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("brand_color", sa.String(length=20), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_settings_school", "school_settings",
                    ["school_id"], unique=True)

    # === 4. school_domains ===
    op.create_table(
        "school_domains",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_domain_school", "school_domains", ["school_id"])
    op.create_index("idx_domain_unique", "school_domains",
                    ["domain"], unique=True)

    # === 5. categories 加 school_id ===
    op.add_column(
        "categories",
        sa.Column("school_id", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
    )
    op.create_foreign_key(
        "fk_categories_school_id", "categories", "schools", ["school_id"], ["id"],
    )

    # === 6. tags 加 school_id ===
    op.add_column(
        "tags",
        sa.Column("school_id", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
    )
    op.create_foreign_key(
        "fk_tags_school_id", "tags", "schools", ["school_id"], ["id"],
    )

    # === 7. 回填 school_id（安全保护，server_default 应已处理） ===
    op.execute("UPDATE categories SET school_id = 1 WHERE school_id IS NULL")
    op.execute("UPDATE tags SET school_id = 1 WHERE school_id IS NULL")

    # === 8. 删除 categories 旧唯一索引 ===
    op.drop_index("idx_category_code", table_name="categories")
    op.drop_index("ix_categories_code", table_name="categories")

    # === 9. 删除 tags 旧唯一索引 ===
    op.drop_index("idx_tag_name", table_name="tags")
    op.drop_index("idx_tag_slug", table_name="tags")
    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_index("ix_tags_slug", table_name="tags")

    # === 10. 创建新复合唯一索引 ===
    op.create_index("idx_category_school_code", "categories",
                    ["school_id", "code"], unique=True)
    op.create_index("idx_tag_school_name", "tags",
                    ["school_id", "name"], unique=True)
    op.create_index("idx_tag_school_slug", "tags",
                    ["school_id", "slug"], unique=True)

    # === 11. 移除 school_id 的 server_default（ORM default=1 接管） ===
    op.alter_column("categories", "school_id", server_default=None)
    op.alter_column("tags", "school_id", server_default=None)

    # === 12. 旧用户无损回填到 school_memberships ===
    # role 映射：admin/super_admin → admin；user → member
    # 不改密码/邮箱，保留原账号可登录
    op.execute(
        """
        INSERT INTO school_memberships
            (user_id, school_id, role, status, is_default, joined_at, created_at, updated_at)
        SELECT
            id,
            school_id,
            CASE WHEN role IN ('admin', 'super_admin') THEN 'admin' ELSE 'member' END,
            'active',
            true,
            created_at,
            created_at,
            created_at
        FROM users
        WHERE is_deleted = false
        """
    )


def downgrade() -> None:
    # === 1. 清除回填的成员数据 ===
    op.execute("DELETE FROM school_memberships")

    # === 2. 删除新复合唯一索引 ===
    op.drop_index("idx_tag_school_slug", table_name="tags")
    op.drop_index("idx_tag_school_name", table_name="tags")
    op.drop_index("idx_category_school_code", table_name="categories")

    # === 3. 恢复 school_id 的 server_default 以便安全降级 ===
    op.alter_column("categories", "school_id", server_default=sa.text("1"))
    op.alter_column("tags", "school_id", server_default=sa.text("1"))

    # === 4. 恢复 categories 旧唯一索引 ===
    op.create_index("ix_categories_code", "categories", ["code"], unique=True)
    op.create_index("idx_category_code", "categories", ["code"], unique=True)

    # === 5. 恢复 tags 旧唯一索引 ===
    op.create_index("ix_tags_slug", "tags", ["slug"], unique=True)
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)
    op.create_index("idx_tag_slug", "tags", ["slug"], unique=True)
    op.create_index("idx_tag_name", "tags", ["name"], unique=True)

    # === 6. 删除 school_id 列（先删外键再删列） ===
    op.drop_constraint("fk_tags_school_id", "tags", type_="foreignkey")
    op.drop_column("tags", "school_id")
    op.drop_constraint("fk_categories_school_id", "categories", type_="foreignkey")
    op.drop_column("categories", "school_id")

    # === 7. 删除新表 ===
    op.drop_index("idx_domain_unique", table_name="school_domains")
    op.drop_index("idx_domain_school", table_name="school_domains")
    op.drop_table("school_domains")

    op.drop_index("idx_settings_school", table_name="school_settings")
    op.drop_table("school_settings")

    op.drop_index("idx_invitation_code", table_name="school_invitations")
    op.drop_index("idx_invitation_email_status", table_name="school_invitations")
    op.drop_index("idx_invitation_school_status", table_name="school_invitations")
    op.drop_index(op.f("ix_school_invitations_email"), table_name="school_invitations")
    op.drop_table("school_invitations")

    op.drop_index("idx_membership_default", table_name="school_memberships")
    op.drop_index("idx_membership_school_status", table_name="school_memberships")
    op.drop_index("idx_membership_school_role", table_name="school_memberships")
    op.drop_index("idx_membership_user_school", table_name="school_memberships")
    op.drop_table("school_memberships")
