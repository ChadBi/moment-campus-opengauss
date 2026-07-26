from sqlalchemy import BigInteger, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class SchoolSubscription(Base):
    """学校订阅记录（COM-01）。

    一个学校同时只允许一个 active 订阅（唯一索引 school_id + status='active'）。
    状态机：active → expired / suspended；可由 super_admin 续期 / 暂停 / 恢复。
    """

    __tablename__ = "school_subscriptions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_plans.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False,
                                        comment="订阅状态：active/expired/suspended")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="到期时间；NULL 表示不限")
    assigned_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
                                                     comment="分配/续期操作者 user_id")
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False,
                                                  comment="最近一次分配/续期时间")
    note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="操作备注（旧值/新值/原因）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    school: Mapped["School"] = relationship()
    plan: Mapped["ProductPlan"] = relationship(back_populates="subscriptions")
    assigner: Mapped["User | None"] = relationship(foreign_keys=[assigned_by])

    __table_args__ = (
        Index("idx_subscription_school_status", "school_id", "status"),
        Index("idx_subscription_status_expires", "status", "expires_at"),
        Index("idx_subscription_school_active", "school_id",
              "status"),  # 用于过滤 active；唯一性由应用层在分配时校验
    )

    def __repr__(self) -> str:
        return f"<SchoolSubscription(school_id={self.school_id}, plan_id={self.plan_id}, status='{self.status}')>"
