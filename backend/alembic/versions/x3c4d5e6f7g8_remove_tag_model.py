"""remove tag model

Revision ID: x3c4d5e6f7g8
Revises: w2b3c4d5e6f7
Create Date: 2026-07-27 14:00:00.000000

Task 1.3: 删除 Tag 模型与标签功能
- DROP TABLE post_tags
- DROP TABLE tags

标签功能与分类（Category）冲突，按 docs/需要调整的地方.md §12 完全移除。
downgrade 重建表结构（含多租户 school_id 字段与索引）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x3c4d5e6f7g8"
down_revision: Union[str, None] = "w2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除标签相关表：
    1. DROP TABLE post_tags（帖子-标签关联表）
    2. DROP TABLE tags（标签表）
    """
    # ---- 1. DROP TABLE post_tags ----
    # 先删关联表（含 FK 指向 tags 与 posts）
    op.drop_index("ix_post_tags_tag_id", table_name="post_tags")
    op.drop_index("ix_post_tags_post_id", table_name="post_tags")
    op.drop_index("idx_posttag_tag", table_name="post_tags")
    op.drop_index("idx_posttag_post_tag", table_name="post_tags")
    op.drop_table("post_tags")

    # ---- 2. DROP TABLE tags ----
    # 删除多租户迁移后建立的索引（含 school_id 复合索引）
    op.drop_index("idx_tag_school_slug", table_name="tags")
    op.drop_index("idx_tag_school_name", table_name="tags")
    op.drop_index("idx_tag_usage", table_name="tags")
    op.drop_index("idx_tag_official", table_name="tags")
    op.drop_table("tags")


def downgrade() -> None:
    """回滚：重建 tags 与 post_tags 表（含多租户 school_id 字段）。

    注意：原标签数据不可恢复，仅恢复空表结构。
    """
    # ---- 1. 重建 tags 表（含 school_id，与 h7c8d9e0f1a2 多租户迁移后的结构一致）----
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("is_official", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tag_school_name", "tags", ["school_id", "name"], unique=True)
    op.create_index("idx_tag_school_slug", "tags", ["school_id", "slug"], unique=True)
    op.create_index("idx_tag_usage", "tags", ["usage_count"], unique=False)
    op.create_index("idx_tag_official", "tags", ["is_official"], unique=False)

    # ---- 2. 重建 post_tags 关联表 ----
    op.create_table(
        "post_tags",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_posttag_post_tag", "post_tags", ["post_id", "tag_id"], unique=True)
    op.create_index("idx_posttag_tag", "post_tags", ["tag_id"], unique=False)
    op.create_index("ix_post_tags_post_id", "post_tags", ["post_id"], unique=False)
    op.create_index("ix_post_tags_tag_id", "post_tags", ["tag_id"], unique=False)
