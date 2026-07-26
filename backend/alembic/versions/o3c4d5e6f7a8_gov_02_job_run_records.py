"""GOV-02.2: job_run_records table

Revision ID: o3c4d5e6f7a8
Revises: n2b3c4d5e6f7
Create Date: 2026-07-24 15:00:00.000000

GOV-02 任务：
- 新建 job_run_records 表，记录后台批量任务（自动过期 published → expired）的执行情况
- 字段：job_name / status(running/success/failed) / started_at / finished_at /
  processed_count / failed_count / error_message / triggered_by /
  triggered_user_id / dry_run / metadata / created_at
- 用于 GOV-02.2 的 dry-run 与手动重跑支持，记录开始/成功/失败/处理数量/耗时

注：原文件 revision 与 acc_01_2 迁移冲突（同为 n2b3c4d5e6f7），改为 o3c4d5e6f7a8
并链式接续 n2b3c4d5e6f7，消除多 head。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o3c4d5e6f7a8"
down_revision: Union[str, None] = "n2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_run_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_name", sa.String(length=50), nullable=False,
                  comment="任务名：expire_posts / summarize_usage 等"),
        sa.Column("status", sa.String(length=20), nullable=False,
                  comment="运行状态：running / success / failed"),
        sa.Column("started_at", sa.DateTime(), nullable=False,
                  comment="任务开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True,
                  comment="任务结束时间（running 时为 NULL）"),
        sa.Column("processed_count", sa.Integer(), nullable=False,
                  server_default="0", comment="成功处理数量"),
        sa.Column("failed_count", sa.Integer(), nullable=False,
                  server_default="0", comment="失败数量"),
        sa.Column("error_message", sa.Text(), nullable=True,
                  comment="失败原因或 JSON 文本（含 failed_ids 等）"),
        sa.Column("triggered_by", sa.String(length=50), nullable=False,
                  server_default="system",
                  comment="触发者：system / manual / 手动触发的 user_id"),
        sa.Column("triggered_user_id", sa.BigInteger(), nullable=True,
                  comment="手动触发时的 user_id；NULL 表示系统定时触发"),
        sa.Column("dry_run", sa.Boolean(), nullable=False,
                  server_default=sa.text("false"),
                  comment="是否为 dry-run（只报告不执行）"),
        sa.Column("metadata", sa.Text(), nullable=True,
                  comment="JSON 文本，存放额外元数据（如 failed_ids 列表）"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["triggered_user_id"], ["users.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_job_run_records_job_name"),
        "job_run_records", ["job_name"],
    )
    op.create_index(
        op.f("ix_job_run_records_status"),
        "job_run_records", ["status"],
    )
    op.create_index(
        op.f("ix_job_run_records_started_at"),
        "job_run_records", ["started_at"],
    )
    op.create_index(
        "idx_job_run_name_status",
        "job_run_records", ["job_name", "status"],
    )
    op.create_index(
        "idx_job_run_started",
        "job_run_records", ["started_at"],
    )
    op.create_index(
        "idx_job_run_triggered",
        "job_run_records", ["triggered_by", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_job_run_triggered", table_name="job_run_records")
    op.drop_index("idx_job_run_started", table_name="job_run_records")
    op.drop_index("idx_job_run_name_status", table_name="job_run_records")
    op.drop_index(op.f("ix_job_run_records_started_at"),
                  table_name="job_run_records")
    op.drop_index(op.f("ix_job_run_records_status"),
                  table_name="job_run_records")
    op.drop_index(op.f("ix_job_run_records_job_name"),
                  table_name="job_run_records")
    op.drop_table("job_run_records")
