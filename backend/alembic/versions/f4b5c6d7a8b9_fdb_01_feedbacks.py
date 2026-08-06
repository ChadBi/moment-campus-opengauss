"""FDB-01: feedbacks 反馈表

Revision ID: f4b5c6d7a8b9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-06 00:00:00.000000

用户反馈（建议/问题/投诉/其他）：
- 新建 feedbacks 表
  字段：id / user_id / school_id / feedback_type / content / contact
        / status / remark / resolved_at / created_at / updated_at
- feedback_type：suggestion / bug / complaint / other
- status：open / in_review / resolved（默认 open）
- remark：管理员处理备注（可空）
- resolved_at：进入 resolved 状态时写入
- 反馈严格按学校隔离：school_id 由 TenantContext 决定（TEN-02 三校隔离）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b5c6d7a8b9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="提交反馈的用户 ID",
        ),
        sa.Column(
            "school_id",
            sa.BigInteger(),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
            comment="学校 ID（TEN-02 三校隔离）",
        ),
        sa.Column(
            "feedback_type",
            sa.String(length=30),
            nullable=False,
            comment="反馈类型：suggestion / bug / complaint / other",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="反馈内容",
        ),
        sa.Column(
            "contact",
            sa.String(length=200),
            nullable=True,
            comment="联系方式（可空）",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="open",
            comment="状态：open / in_review / resolved",
        ),
        sa.Column(
            "remark",
            sa.Text(),
            nullable=True,
            comment="管理员处理备注",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(),
            nullable=True,
            comment="处理完成时间（进入 resolved 时写入）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # 查询索引：管理端按学校+状态过滤（反馈管理列表）
    op.create_index(
        "idx_feedback_school_status",
        "feedbacks",
        ["school_id", "status", "created_at"],
        unique=False,
    )
    # 查询索引：我的反馈（user_id + school_id）
    op.create_index(
        "idx_feedback_user_school",
        "feedbacks",
        ["user_id", "school_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_feedback_user_school", table_name="feedbacks")
    op.drop_index("idx_feedback_school_status", table_name="feedbacks")
    op.drop_table("feedbacks")