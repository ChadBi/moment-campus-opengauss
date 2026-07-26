"""AI-01.2: AI 调用日志模型。

记录每次 AI 调用的元数据（不保存完整敏感输入），用于：
- 监控 AI 降级率 / 各场景成功率 / 延迟分布
- 平台后台展示各校 AI 调用情况
- 故障排查（trace_id 关联请求链路）

隐私约束：
- 默认不保存完整 prompt（可能含搜索关键词/正文片段）。
- 仅保存 input_length（长度）与 input_hash（SHA-256 摘要，便于去重统计而不泄露内容）。
- 不保存模型完整输出（output_status 只记状态），结果数/候选数仅记数量。
"""
from sqlalchemy import BigInteger, Integer, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.database import Base


class AIInvocationLog(Base):
    """AI 调用日志（按学校/用户/场景/时间索引）。"""

    __tablename__ = "ai_invocation_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True,
    )
    # 必须来自 TenantContext，不接受 body 传入（三校隔离）
    school_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
        comment="学校 ID（来自 TenantContext，三校隔离）",
    )
    # 游客调用时为 NULL
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True,
        comment="用户 ID（游客为 NULL）",
    )
    scene: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="调用场景：search_intent / publish_suggestion 等",
    )
    model: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="模型名（如 gpt-4o-mini / mock-model）",
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Provider 类型：mock / openai",
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="调用延迟（毫秒）",
    )
    input_length: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="输入长度（字符数），不保存完整输入",
    )
    input_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="输入 SHA-256 摘要（便于去重统计，不可逆推内容）",
    )
    # output_status：success/timeout/rate_limit/insufficient_quota/network_error/json_parse_error/circuit_breaker/error
    output_status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="输出状态：success / timeout / rate_limit / insufficient_quota / network_error / json_parse_error / circuit_breaker / error",
    )
    fallback_reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="降级原因（失败时填，如 AI 超时已降级普通搜索）",
    )
    candidate_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="候选数（检索阶段命中的原始结果数）",
    )
    result_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="最终返回给用户的结果数",
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
        comment="链路追踪 ID（关联 X-Request-ID）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, index=True,
    )

    __table_args__ = (
        Index("idx_ai_log_school_created", "school_id", "created_at"),
        Index("idx_ai_log_school_scene", "school_id", "scene", "created_at"),
        Index("idx_ai_log_status", "output_status", "created_at"),
        Index("idx_ai_log_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIInvocationLog(id={self.id}, school_id={self.school_id}, "
            f"scene='{self.scene}', output_status='{self.output_status}')>"
        )
