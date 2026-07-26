"""AI-01.2: ai_invocation_logs 表

Revision ID: p4d5e6f7a8b9
Revises: o3c4d5e6f7a8
Create Date: 2026-07-24 15:00:00.000000

AI-01.2 任务：
- 新建 ai_invocation_logs 表（AI 调用日志）
  字段：id / school_id / user_id / scene / model / provider / latency_ms /
        input_length / input_hash / output_status / fallback_reason /
        candidate_count / result_count / trace_id / created_at
- 隐私约束：不保存完整敏感输入，仅保存 input_length 与 input_hash（SHA-256 摘要）
- 三校隔离：school_id 必须来自 TenantContext，索引按 school_id + scene + created_at 建组合索引
- output_status：success / timeout / rate_limit / insufficient_quota /
                 network_error / json_parse_error / circuit_breaker / error
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p4d5e6f7a8b9"
down_revision: Union[str, None] = "o3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_invocation_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.BigInteger(), nullable=False,
                  comment="学校 ID（来自 TenantContext，三校隔离）"),
        sa.Column("user_id", sa.BigInteger(), nullable=True,
                  comment="用户 ID（游客为 NULL）"),
        sa.Column("scene", sa.String(length=50), nullable=False,
                  comment="调用场景：search_intent / publish_suggestion 等"),
        sa.Column("model", sa.String(length=100), nullable=False,
                  comment="模型名（如 gpt-4o-mini / mock-model）"),
        sa.Column("provider", sa.String(length=50), nullable=False,
                  comment="Provider 类型：mock / openai"),
        sa.Column("latency_ms", sa.Integer(), nullable=False,
                  comment="调用延迟（毫秒）"),
        sa.Column("input_length", sa.Integer(), nullable=False,
                  comment="输入长度（字符数），不保存完整输入"),
        sa.Column("input_hash", sa.String(length=64), nullable=True,
                  comment="输入 SHA-256 摘要（便于去重统计，不可逆推内容）"),
        sa.Column("output_status", sa.String(length=32), nullable=False,
                  comment="输出状态：success/timeout/rate_limit/insufficient_quota/"
                          "network_error/json_parse_error/circuit_breaker/error"),
        sa.Column("fallback_reason", sa.String(length=200), nullable=True,
                  comment="降级原因（失败时填）"),
        sa.Column("candidate_count", sa.Integer(), nullable=True,
                  comment="候选数（检索阶段命中的原始结果数）"),
        sa.Column("result_count", sa.Integer(), nullable=True,
                  comment="最终返回给用户的结果数"),
        sa.Column("trace_id", sa.String(length=64), nullable=True,
                  comment="链路追踪 ID（关联 X-Request-ID）"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_invocation_logs_id"),
                    "ai_invocation_logs", ["id"])
    op.create_index(op.f("ix_ai_invocation_logs_school_id"),
                    "ai_invocation_logs", ["school_id"])
    op.create_index(op.f("ix_ai_invocation_logs_user_id"),
                    "ai_invocation_logs", ["user_id"])
    op.create_index(op.f("ix_ai_invocation_logs_scene"),
                    "ai_invocation_logs", ["scene"])
    op.create_index(op.f("ix_ai_invocation_logs_output_status"),
                    "ai_invocation_logs", ["output_status"])
    op.create_index(op.f("ix_ai_invocation_logs_trace_id"),
                    "ai_invocation_logs", ["trace_id"])
    op.create_index(op.f("ix_ai_invocation_logs_created_at"),
                    "ai_invocation_logs", ["created_at"])
    op.create_index("idx_ai_log_school_created",
                    "ai_invocation_logs", ["school_id", "created_at"])
    op.create_index("idx_ai_log_school_scene",
                    "ai_invocation_logs", ["school_id", "scene", "created_at"])
    op.create_index("idx_ai_log_status",
                    "ai_invocation_logs", ["output_status", "created_at"])
    op.create_index("idx_ai_log_user_created",
                    "ai_invocation_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_ai_log_user_created", table_name="ai_invocation_logs")
    op.drop_index("idx_ai_log_status", table_name="ai_invocation_logs")
    op.drop_index("idx_ai_log_school_scene", table_name="ai_invocation_logs")
    op.drop_index("idx_ai_log_school_created", table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_created_at"),
                  table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_trace_id"),
                  table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_output_status"),
                  table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_scene"),
                  table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_user_id"),
                  table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_school_id"),
                  table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_id"),
                  table_name="ai_invocation_logs")
    op.drop_table("ai_invocation_logs")
