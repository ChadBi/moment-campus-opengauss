"""ANA-01: product_events table for analytics whitelist + idempotent ingest

Revision ID: k0f1a2b3c4d5
Revises: j9e0f1a2b3c4
Create Date: 2026-07-24 12:30:00.000000

ANA-01 任务：
- 新建 product_events 表（产品分析事件）
- 字段：event_id(幂等键 UUID)/event_name/school_id/user_id(可空)/session_id/trace_id/
  occurred_at/received_at/environment(production/demo/test/seed)/fields_json(JSONB)
- event_id 唯一约束保证幂等：客户端重复上报同 event_id 不重复入库
- 索引：school_id+event_name+occurred_at / environment+occurred_at / session_id+occurred_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "k0f1a2b3c4d5"
down_revision: Union[str, None] = "j9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False,
                  comment="客户端生成的 UUID，幂等键"),
        sa.Column("event_name", sa.String(length=50), nullable=False,
                  comment="事件名（必须在白名单内）"),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True,
                  comment="触发用户 ID；游客事件为 NULL"),
        sa.Column("session_id", sa.String(length=64), nullable=True,
                  comment="前端会话 ID（前端生成）"),
        sa.Column("trace_id", sa.String(length=128), nullable=True,
                  comment="关联 X-Request-ID"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False,
                  comment="事件发生时间（客户端上报）"),
        sa.Column("received_at", sa.DateTime(), nullable=False,
                  comment="服务端接收时间"),
        sa.Column("environment", sa.String(length=20), nullable=False,
                  comment="环境标记：production/demo/test/seed"),
        sa.Column("fields_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment="最小字段集（白名单 schema 严格校验）"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_product_event_event_id"),
    )
    op.create_index(op.f("ix_product_events_event_id"), "product_events",
                    ["event_id"], unique=True)
    op.create_index(op.f("ix_product_events_event_name"), "product_events",
                    ["event_name"])
    op.create_index(op.f("ix_product_events_school_id"), "product_events",
                    ["school_id"])
    op.create_index(op.f("ix_product_events_user_id"), "product_events",
                    ["user_id"])
    op.create_index(op.f("ix_product_events_session_id"), "product_events",
                    ["session_id"])
    op.create_index(op.f("ix_product_events_trace_id"), "product_events",
                    ["trace_id"])
    op.create_index(op.f("ix_product_events_occurred_at"), "product_events",
                    ["occurred_at"])
    op.create_index(op.f("ix_product_events_environment"), "product_events",
                    ["environment"])
    op.create_index("idx_product_event_school_name_time", "product_events",
                    ["school_id", "event_name", "occurred_at"])
    op.create_index("idx_product_event_env_time", "product_events",
                    ["environment", "occurred_at"])
    op.create_index("idx_product_event_session", "product_events",
                    ["session_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("idx_product_event_session", table_name="product_events")
    op.drop_index("idx_product_event_env_time", table_name="product_events")
    op.drop_index("idx_product_event_school_name_time", table_name="product_events")
    op.drop_index(op.f("ix_product_events_environment"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_occurred_at"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_trace_id"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_session_id"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_user_id"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_school_id"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_event_name"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_event_id"), table_name="product_events")
    op.drop_table("product_events")
