"""GOV-01.1: post_change_reports table

Revision ID: l0a1b2c3d4e5
Revises: k0f1a2b3c4d5
Create Date: 2026-07-24 13:00:00.000000

GOV-01 任务：
- 新建 post_change_reports 表，承载 3 类"问题报告"
  （update / expiration_report / conflict_report）
- 字段：post_id / reporter_id / report_type / description / evidence_url /
  status(open/in_review/resolved/dismissed) / handler_id / handler_note /
  handled_at / created_at / updated_at
- validation_records 表保持不变（2 类互斥投票 confirmation/refutation）
- 对外统一称"5 类协同验证" = 2 类投票(validation_records) + 3 类报告(post_change_reports)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l0a1b2c3d4e5"
down_revision: Union[str, None] = "k0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_change_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False,
                  comment="帖子 ID"),
        sa.Column("reporter_id", sa.BigInteger(), nullable=False,
                  comment="报告者 user_id"),
        sa.Column("report_type", sa.String(length=20), nullable=False,
                  comment="问题报告类型：update/expiration_report/conflict_report（3 类）"),
        sa.Column("description", sa.Text(), nullable=True, comment="报告说明"),
        sa.Column("evidence_url", sa.String(length=500), nullable=True,
                  comment="证据链接"),
        sa.Column("status", sa.String(length=20), nullable=False,
                  comment="处理状态：open/in_review/resolved/dismissed"),
        sa.Column("handler_id", sa.BigInteger(), nullable=True,
                  comment="处理人 user_id"),
        sa.Column("handler_note", sa.Text(), nullable=True, comment="处理说明/原因"),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["handler_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_post_change_reports_post_id"),
        "post_change_reports", ["post_id"],
    )
    op.create_index(
        op.f("ix_post_change_reports_reporter_id"),
        "post_change_reports", ["reporter_id"],
    )
    op.create_index(
        op.f("ix_post_change_reports_status"),
        "post_change_reports", ["status"],
    )
    op.create_index(
        op.f("ix_post_change_reports_handler_id"),
        "post_change_reports", ["handler_id"],
    )
    op.create_index(
        "idx_pcr_post_status", "post_change_reports",
        ["post_id", "status"],
    )
    op.create_index(
        "idx_pcr_post_type", "post_change_reports",
        ["post_id", "report_type"],
    )
    op.create_index(
        "idx_pcr_reporter", "post_change_reports", ["reporter_id"],
    )
    op.create_index(
        "idx_pcr_handler", "post_change_reports", ["handler_id"],
    )
    op.create_index(
        "idx_pcr_created", "post_change_reports", ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_pcr_created", table_name="post_change_reports")
    op.drop_index("idx_pcr_handler", table_name="post_change_reports")
    op.drop_index("idx_pcr_reporter", table_name="post_change_reports")
    op.drop_index("idx_pcr_post_type", table_name="post_change_reports")
    op.drop_index("idx_pcr_post_status", table_name="post_change_reports")
    op.drop_index(op.f("ix_post_change_reports_handler_id"), table_name="post_change_reports")
    op.drop_index(op.f("ix_post_change_reports_status"), table_name="post_change_reports")
    op.drop_index(op.f("ix_post_change_reports_reporter_id"), table_name="post_change_reports")
    op.drop_index(op.f("ix_post_change_reports_post_id"), table_name="post_change_reports")
    op.drop_table("post_change_reports")
