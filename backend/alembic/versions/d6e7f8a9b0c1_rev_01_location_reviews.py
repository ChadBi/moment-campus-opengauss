"""REV-01: location_reviews + locations 评分字段

Revision ID: d6e7f8a9b0c1
Revises: d5e6f7a8b9c1
Create Date: 2026-08-05 10:00:00.000000

导师反馈完善（工作流 A：附近 + 设施评分评价）：
- 新建 location_reviews 表：地点评分/评价
  字段：id / location_id / user_id / school_id / score(1-5) / content / status
        / created_at / updated_at / is_deleted / deleted_at
  唯一约束 (location_id, user_id)：每地点每用户一条评价（可改可撤回）
- locations 表新增评分汇总字段：avg_score / rating_count / review_count
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "d5e6f7a8b9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False,
                  comment="地点 ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False,
                  comment="评价用户 ID"),
        sa.Column("school_id", sa.BigInteger(), nullable=False,
                  comment="所属学校 ID（多租户隔离）"),
        sa.Column("score", sa.Integer(), nullable=False,
                  comment="评分 1-5"),
        sa.Column("content", sa.String(length=500), nullable=True,
                  comment="评价内容"),
        sa.Column("status", sa.String(length=20), nullable=False,
                  comment="状态：published"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False,
                  comment="物理模型扩展：软删除标记"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "user_id", name="uq_location_reviews_location_user"),
    )
    op.create_index(op.f("ix_location_reviews_id"),
                    "location_reviews", ["id"])
    op.create_index(op.f("ix_location_reviews_location_id"),
                    "location_reviews", ["location_id"])
    op.create_index(op.f("ix_location_reviews_user_id"),
                    "location_reviews", ["user_id"])
    op.create_index(op.f("ix_location_reviews_school_id"),
                    "location_reviews", ["school_id"])
    op.create_index("idx_location_reviews_location_created",
                    "location_reviews", ["location_id", "created_at"])

    op.add_column(
        "locations",
        sa.Column("avg_score", sa.Numeric(precision=3, scale=2), nullable=False,
                  server_default="0", comment="平均评分（1-5，保留 2 位）"),
    )
    op.add_column(
        "locations",
        sa.Column("rating_count", sa.Integer(), nullable=False,
                  server_default="0", comment="评分人数（有分评价数）"),
    )
    op.add_column(
        "locations",
        sa.Column("review_count", sa.Integer(), nullable=False,
                  server_default="0", comment="评价条数"),
    )


def downgrade() -> None:
    op.drop_column("locations", "review_count")
    op.drop_column("locations", "rating_count")
    op.drop_column("locations", "avg_score")
    op.drop_index("idx_location_reviews_location_created", table_name="location_reviews")
    op.drop_index(op.f("ix_location_reviews_school_id"), table_name="location_reviews")
    op.drop_index(op.f("ix_location_reviews_user_id"), table_name="location_reviews")
    op.drop_index(op.f("ix_location_reviews_location_id"), table_name="location_reviews")
    op.drop_index(op.f("ix_location_reviews_id"), table_name="location_reviews")
    op.drop_table("location_reviews")