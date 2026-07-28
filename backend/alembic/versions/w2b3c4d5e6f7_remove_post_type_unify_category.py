"""remove post_type and unify categories

Revision ID: w2b3c4d5e6f7
Revises: v1a2b3c4d5e6
Create Date: 2026-07-27 11:00:00.000000

Task 1.2: 删除 PostType 模型，Category 重构为统一「信息分类」5 类
- 删除 posts.post_type_id 列与相关索引
- 删除 drafts.post_type_id 列（草稿不再关联 PostType）
- 删除 post_templates.post_type_id 列（模板不再关联 PostType）
- DROP TABLE post_types
- 重置 categories 为 5 类统一信息分类（每校 5 类：share/teamup/trade/lost_found/other）
- 现有 posts.category_id 在迁移过程中被映射到该学校的"其他"分类（code=other）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w2b3c4d5e6f7"
down_revision: Union[str, None] = "v1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 5 类统一信息分类（每校均创建）
NEW_CATEGORY_CODES = ("share", "teamup", "trade", "lost_found", "other")


def upgrade() -> None:
    """迁移步骤：
    1. 为每所学校创建新的 5 类分类（若不存在）
    2. 将所有 posts.category_id 更新到该学校的"其他"分类（避免删除旧分类时 FK 失败）
    3. 删除旧分类（不属于新 5 类的所有分类）
    4. 删除 posts.post_type_id 索引、FK 约束、列
    5. 删除 drafts.post_type_id FK 约束、列
    6. 删除 post_templates.post_type_id FK 约束、列
    7. DROP TABLE post_types
    """
    # ---- 1. 为每所学校创建新的 5 类分类（若不存在）----
    op.execute(
        """
        INSERT INTO categories (school_id, name, code, icon, description, default_validity_days, sort_order, is_active, created_at, updated_at)
        SELECT s.id, c.name, c.code, c.icon, c.description, c.validity, c.sort_order, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM schools s
        CROSS JOIN (VALUES
            ('分享吐槽', 'share', '💬', '校园生活分享、吐槽、心得', 30, 1),
            ('组队交友', 'teamup', '🤝', '组队、交友、活动搭子', 30, 2),
            ('二手交易', 'trade', '💰', '二手物品买卖、赠予', 30, 3),
            ('失物招领', 'lost_found', '🔍', '丢失与拾到物品信息', 30, 4),
            ('其他', 'other', '📝', '其他类型信息', 30, 5)
        ) AS c(name, code, icon, description, validity, sort_order)
        WHERE NOT EXISTS (
            SELECT 1 FROM categories cat
            WHERE cat.school_id = s.id AND cat.code = c.code
        )
        """
    )

    # ---- 2. 将所有 posts.category_id 更新到该学校的"其他"分类 ----
    # 避免删除旧分类时 FK 约束失败
    op.execute(
        """
        UPDATE posts p
        SET category_id = (
            SELECT c.id FROM categories c
            WHERE c.school_id = p.school_id AND c.code = 'other'
        )
        WHERE NOT EXISTS (
            SELECT 1 FROM categories c2
            WHERE c2.id = p.category_id
            AND c2.code IN ('share', 'teamup', 'trade', 'lost_found', 'other')
        )
        """
    )

    # ---- 3. 删除旧分类（不属于新 5 类的所有分类）----
    op.execute(
        """
        DELETE FROM categories
        WHERE code NOT IN ('share', 'teamup', 'trade', 'lost_found', 'other')
        """
    )

    # ---- 4. 删除 posts.post_type_id 索引、FK 约束、列 ----
    # 注意：约束名采用 SQLAlchemy 默认命名约定 posts_<column>_fkey
    op.drop_index("idx_post_type", table_name="posts")
    op.drop_constraint("posts_post_type_id_fkey", "posts", type_="foreignkey")
    op.drop_column("posts", "post_type_id")

    # ---- 5. 删除 drafts.post_type_id FK 约束、列 ----
    op.drop_constraint("drafts_post_type_id_fkey", "drafts", type_="foreignkey")
    op.drop_column("drafts", "post_type_id")

    # ---- 6. 删除 post_templates.post_type_id FK 约束、列 ----
    op.drop_constraint("post_templates_post_type_id_fkey", "post_templates", type_="foreignkey")
    op.drop_column("post_templates", "post_type_id")

    # ---- 7. DROP TABLE post_types ----
    op.drop_table("post_types")


def downgrade() -> None:
    """回滚：重建 post_types 表与 posts.post_type_id 列。

    注意：旧分类（12 类）不可恢复，但 5 类新分类保留。
    """
    # ---- 重建 post_types 表 ----
    op.create_table(
        "post_types",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_posttype_code", "post_types", ["code"], unique=True)

    # ---- 重新添加 posts.post_type_id 列 ----
    op.add_column("posts", sa.Column("post_type_id", sa.BigInteger(), nullable=True))
    op.create_index("idx_post_type", "posts", ["post_type_id"])
    op.create_foreign_key(
        "posts_post_type_id_fkey",
        "posts",
        "post_types",
        ["post_type_id"],
        ["id"],
    )

    # ---- 重新添加 drafts.post_type_id 列 ----
    op.add_column("drafts", sa.Column("post_type_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "drafts_post_type_id_fkey",
        "drafts",
        "post_types",
        ["post_type_id"],
        ["id"],
    )

    # ---- 重新添加 post_templates.post_type_id 列 ----
    op.add_column("post_templates", sa.Column("post_type_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "post_templates_post_type_id_fkey",
        "post_templates",
        "post_types",
        ["post_type_id"],
        ["id"],
    )

    # ---- 注入 3 类原始 PostType 数据 ----
    op.execute(
        """
        INSERT INTO post_types (name, code, description, sort_order, is_active, created_at, updated_at)
        VALUES
            ('普通信息', 'normal', '通用校园信息，无特殊字段', 1, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('活动信息', 'event', '校园活动，需填写活动起止时间', 2, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('失物信息', 'lost_found', '失物招领，需填写 lost_type（lost/picked）', 3, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (code) DO NOTHING
        """
    )

    # ---- 设置已存在 posts 的 post_type_id 为"普通信息"（id=1 或按 code 查询）----
    op.execute(
        """
        UPDATE posts
        SET post_type_id = (SELECT id FROM post_types WHERE code = 'normal' LIMIT 1)
        WHERE post_type_id IS NULL
        """
    )
