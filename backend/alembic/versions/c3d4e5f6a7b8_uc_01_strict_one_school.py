"""UC-01: 严格一对一学校绑定 + 评论/评价匿名化列

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3040506
Create Date: 2026-08-05 23:00:00.000000

校园用户系统优化（工作流 A/C）：
- school_memberships：唯一约束由 (user_id, school_id) 改为 user_id 在
  status='active' 下的部分唯一索引（每用户至多一条 active 成员关系）；
  现有多校数据清理：每用户保留一条 active（is_default 优先，其次最早 joined），
  其余置 status='left'（保留历史，不删除）。
- comments / location_reviews 新增 is_anonymous 列（用户离校后匿名化原校内容）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3040506"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 清理多校数据：每用户保留一条 active（is_default 优先，其次最早 joined），其余置 left
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE school_memberships SET status = 'left', updated_at = now()
            WHERE status = 'active'
              AND id NOT IN (
                  SELECT DISTINCT ON (user_id) id
                  FROM school_memberships
                  WHERE status = 'active'
                  ORDER BY user_id, is_default DESC, joined_at ASC
              )
            """
        )
    )

    # 2) 索引替换：删除旧组合唯一索引，创建 active 部分唯一索引
    op.drop_index("idx_membership_user_school", table_name="school_memberships")
    op.create_index(
        "idx_membership_user_active",
        "school_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # 3) comments / location_reviews 匿名化列
    op.add_column(
        "comments",
        sa.Column(
            "is_anonymous", sa.Boolean(), nullable=False, server_default="false",
            comment="UC-01: 用户离校后原校评论匿名化标记",
        ),
    )
    op.add_column(
        "location_reviews",
        sa.Column(
            "is_anonymous", sa.Boolean(), nullable=False, server_default="false",
            comment="UC-01: 用户离校后原校评价匿名化标记",
        ),
    )


def downgrade() -> None:
    op.drop_column("location_reviews", "is_anonymous")
    op.drop_column("comments", "is_anonymous")
    op.drop_index("idx_membership_user_active", table_name="school_memberships")
    op.create_index(
        "idx_membership_user_school",
        "school_memberships",
        ["user_id", "school_id"],
        unique=True,
    )
