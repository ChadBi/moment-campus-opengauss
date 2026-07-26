from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PlanEntitlement(Base):
    """套餐权益项（COM-01）。

    描述某个 ProductPlan 在指定 key 上的额度限制与策略。
    - key 例：members_max / posts_max / storage_mb / ai_calls_daily
    - is_hard=True 表示硬限制（超出时拒绝并返回明确错误码），
      False 表示软限制（超出仅返回告警，不拒绝业务调用）
    - limit_value 为对应上限数值；0 或 NULL 视为不限。
    """

    __tablename__ = "plan_entitlements"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_plans.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(40), nullable=False,
                                     comment="权益 key：members_max/posts_max/storage_mb/ai_calls_daily 等")
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                    comment="额度上限；NULL 或 0 表示不限")
    is_hard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
                                          comment="True=硬限制（拒绝），False=软限制（告警）")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="权益项说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    plan: Mapped["ProductPlan"] = relationship(back_populates="entitlements")

    __table_args__ = (
        Index("idx_plan_entitlement_plan_key", "plan_id", "key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PlanEntitlement(plan_id={self.plan_id}, key='{self.key}', limit={self.limit_value}, is_hard={self.is_hard})>"
