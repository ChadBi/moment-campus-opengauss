"""ANA-01: 产品事件模型。

存储产品分析事件（白名单约束），用于后续 ANA-02 指标计算与漏斗分析。

设计要点：
1. event_id（客户端生成 UUID）为幂等键，唯一约束保证重复上报不重复入库。
2. 事件名必须在白名单内（见 app/core/analytics.py），非白名单事件拒绝入库。
3. fields_json 只允许存「最小字段」——搜索类事件只记 keyword_length / category 等
   聚合字段，**严禁**写正文 / 密码 / Token / 完整搜索关键词原文。
4. environment 字段标记数据来源（production/demo/test/seed），从配置读取，区分演示与生产数据。
5. user_id 可空（游客事件无 user_id）；school_id 必填（从 TenantContext 解析）。
"""
from sqlalchemy import (
    BigInteger, Integer, String, DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class ProductEvent(Base):
    """产品分析事件（ANA-01）。

    - event_id：客户端生成的 UUID，作为幂等键（唯一约束）。
    - event_name：事件名，必须在白名单内（app.core.analytics.EVENT_WHITELIST）。
    - school_id：事件所属学校（从 TenantContext 解析，忽略载荷中的 school_id）。
    - user_id：触发用户 ID；游客事件为 NULL。
    - session_id：前端会话 ID（前端生成，便于串联同一会话内多个事件）。
    - trace_id：关联 X-Request-ID，便于与请求日志关联。
    - occurred_at：事件发生时间（客户端上报）。
    - received_at：服务端接收时间（服务端填，便于诊断延迟）。
    - environment：环境标记（production/demo/test/seed），从 settings 读取。
    - fields_json：最小字段集（JSONB），由白名单 schema 严格校验。

    幂等实现说明：
        openGauss 不支持 PostgreSQL 的 INSERT ... ON CONFLICT DO NOTHING 语法，
        track_event 内部采用「SELECT event_id → 不存在则 INSERT」模式，
        并依赖 event_id 上的唯一约束在并发场景下兜底（重复 INSERT 抛唯一冲突，
        调用方捕获并视为已存在）。
    """

    __tablename__ = "product_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True,
    )
    event_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="客户端生成的 UUID，幂等键",
    )
    event_name: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="事件名（必须在白名单内）",
    )
    school_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="触发用户 ID；游客事件为 NULL",
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
        comment="前端会话 ID（前端生成）",
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True,
        comment="关联 X-Request-ID",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True,
        comment="事件发生时间（客户端上报）",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False,
        comment="服务端接收时间",
    )
    environment: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="环境标记：production/demo/test/seed",
    )
    fields_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="最小字段集（白名单 schema 严格校验，不含正文/密码/Token/完整搜索关键词）",
    )

    # 关系
    school: Mapped["School"] = relationship()
    user: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("idx_product_event_school_name_time", "school_id", "event_name", "occurred_at"),
        Index("idx_product_event_env_time", "environment", "occurred_at"),
        Index("idx_product_event_session", "session_id", "occurred_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductEvent(event_id={self.event_id!r}, "
            f"event_name={self.event_name!r}, school_id={self.school_id}, "
            f"environment={self.environment!r})>"
        )
