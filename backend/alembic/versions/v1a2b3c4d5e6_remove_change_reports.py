"""remove post_change_reports table

Revision ID: v1a2b3c4d5e6
Revises: a871871f04ce
Create Date: 2026-07-27 10:00:00.000000

GOV-01.1 调整：
- 移除"问题报告"功能（update / expiration_report / conflict_report）
- 删除 post_change_reports 表
- 保留 validation_records（证实/证伪）协同验证，不变更
- 后续帖子状态机改为：仅由管理员通过举报队列处理过期/冲突标记
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v1a2b3c4d5e6"
down_revision: Union[str, None] = "a871871f04ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("post_change_reports")


def downgrade() -> None:
    op.create_table(
        "post_change_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False, comment="帖子 ID"),
        sa.Column("reporter_id", sa.BigInteger(), nullable=False, comment="报告者 user_id"),
        sa.Column("report_type", sa.String(length=20), nullable=False,
                  comment="问题报告类型：update/expiration_report/conflict_report（3 类）"),
        sa.Column("description", sa.Text(), nullable=True, comment="报告说明"),
        sa.Column("evidence_url", sa.String(length=500), nullable=True, comment="证据链接"),
        sa.Column("status", sa.String(length=20), nullable=False,
                  comment="处理状态：open/in_review/resolved/dismissed"),
        sa.Column("handler_id", sa.BigInteger(), nullable=True, comment="处理人 user_id"),
        sa.Column("handler_note", sa.Text(), nullable=True, comment="处理说明/原因"),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["handler_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pcr_post_status", "post_change_reports", ["post_id", "status"])
    op.create_index("idx_pcr_post_type", "post_change_reports", ["post_id", "report_type"])
    op.create_index("idx_pcr_reporter", "post_change_reports", ["reporter_id"])
    op.create_index("idx_pcr_handler", "post_change_reports", ["handler_id"])
    op.create_index("idx_pcr_created", "post_change_reports", ["created_at"])
