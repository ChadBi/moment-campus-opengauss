"""PRF-01.3: browse_histories 增加 school_id + viewed_at（按学校隔离浏览历史）

Revision ID: q5e6f7a8b9c0
Revises: p4d5e6f7a8b9
Create Date: 2026-07-25 09:30:00.000000

PRF-01.3 任务：
- browse_histories 表新增 school_id（NOT NULL，外键 schools.id）
- 新增 viewed_at（NOT NULL，最近浏览时间，默认 now）
- 由于历史数据可能存在，先填充 school_id（取 post.school_id）再设 NOT NULL
- 新增索引：
    idx_browse_user_school_post (user_id, school_id, post_id) UNIQUE
      → 同一用户在同一学校对同一帖子只保留一条记录（upsert 依据）
    idx_browse_school_viewed (school_id, viewed_at)
      → 按学校分页查询浏览历史
- 修改 idx_browse_user：由 (user_id, created_at) 改为 (user_id, viewed_at)
  → 按最近浏览时间排序
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q5e6f7a8b9c0"
down_revision: Union[str, None] = "p4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 新增列（先允许 NULL 以便回填历史数据）
    op.add_column(
        "browse_histories",
        sa.Column(
            "school_id",
            sa.BigInteger(),
            nullable=True,
            comment="学校 ID（按学校隔离浏览历史）",
        ),
    )
    op.add_column(
        "browse_histories",
        sa.Column(
            "viewed_at",
            sa.DateTime(),
            nullable=True,
            comment="最近一次浏览时间",
        ),
    )

    # 2. 回填历史数据：school_id 取 post.school_id；viewed_at 取 created_at
    op.execute(
        "UPDATE browse_histories SET school_id = (SELECT school_id FROM posts WHERE posts.id = browse_histories.post_id) "
        "WHERE school_id IS NULL"
    )
    op.execute(
        "UPDATE browse_histories SET viewed_at = created_at WHERE viewed_at IS NULL"
    )

    # 3. 设置 NOT NULL 约束
    op.alter_column("browse_histories", "school_id", nullable=False)
    op.alter_column("browse_histories", "viewed_at", nullable=False)

    # 4. 添加外键
    op.create_foreign_key(
        "fk_browse_histories_school_id_schools",
        "browse_histories",
        "schools",
        ["school_id"],
        ["id"],
    )

    # 5. 删除旧索引、创建新索引
    op.drop_index("idx_browse_user", table_name="browse_histories")
    op.create_index(
        "idx_browse_user",
        "browse_histories",
        ["user_id", "viewed_at"],
        unique=False,
    )
    op.create_index(
        "idx_browse_user_school_post",
        "browse_histories",
        ["user_id", "school_id", "post_id"],
        unique=True,
    )
    op.create_index(
        "idx_browse_school_viewed",
        "browse_histories",
        ["school_id", "viewed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_browse_school_viewed", table_name="browse_histories")
    op.drop_index("idx_browse_user_school_post", table_name="browse_histories")
    op.drop_index("idx_browse_user", table_name="browse_histories")
    op.create_index(
        "idx_browse_user",
        "browse_histories",
        ["user_id", "created_at"],
        unique=False,
    )
    op.drop_constraint(
        "fk_browse_histories_school_id_schools",
        "browse_histories",
        type_="foreignkey",
    )
    op.drop_column("browse_histories", "viewed_at")
    op.drop_column("browse_histories", "school_id")
