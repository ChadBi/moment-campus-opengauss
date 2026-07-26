from sqlalchemy import BigInteger, Integer, String, Date, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime

from app.database import Base


class TenantUsageDaily(Base):
    """租户日级用量汇总（COM-01.3 幂等任务）。

    用于 EntitlementService 软限制告警与硬限制校验时获取当前用量。
    写入采用 UPSERT（INSERT ... ON CONFLICT (school_id, usage_date) DO UPDATE），
    保证重复运行同一天不会翻倍累加——每次基于当日实际 count 重算并覆盖。
    """

    __tablename__ = "tenant_usage_daily"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, comment="统计日期 YYYY-MM-DD")
    members_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_used_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    school: Mapped["School"] = relationship()

    __table_args__ = (
        UniqueConstraint("school_id", "usage_date", name="uq_usage_daily_school_date"),
        Index("idx_usage_daily_date", "usage_date"),
        Index("idx_usage_daily_school_date", "school_id", "usage_date"),
    )

    def __repr__(self) -> str:
        return f"<TenantUsageDaily(school_id={self.school_id}, date={self.usage_date}, posts={self.posts_count}, ai={self.ai_calls_count})>"
