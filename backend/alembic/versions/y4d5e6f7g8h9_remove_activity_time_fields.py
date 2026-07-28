"""remove activity time fields

Revision ID: y4d5e6f7g8h9
Revises: x3c4d5e6f7g8
Create Date: 2026-07-27 15:00:00.000000

Task 1.4: 移除 Post 模型的活动时间字段
- DROP COLUMN activity_start_at FROM posts
- DROP COLUMN activity_end_at FROM posts

PostType 已在 Task 1.2 中删除，活动时间字段（原用于 event 类型帖子）随之移除。
downgrade 重建列结构（与 af3fef102173 初始迁移一致）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y4d5e6f7g8h9"
down_revision: Union[str, None] = "x3c4d5e6f7g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 posts 表的活动时间字段：
    1. DROP COLUMN activity_start_at
    2. DROP COLUMN activity_end_at
    """
    op.drop_column("posts", "activity_start_at")
    op.drop_column("posts", "activity_end_at")


def downgrade() -> None:
    """回滚：重建 posts 表的活动时间字段（与初始迁移结构一致）。

    注意：原活动时间数据不可恢复，仅恢复空列结构。
    """
    op.add_column(
        "posts",
        sa.Column("activity_start_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("activity_end_at", sa.DateTime(), nullable=True),
    )
