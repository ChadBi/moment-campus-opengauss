from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class ProductPlan(Base):
    """产品套餐定义（COM-01）。

    定义可分配给学校的套餐档位（如试用 / 标准 / 运营档）。
    具体可被使用的资源额度由 PlanEntitlement 行描述。
    """

    __tablename__ = "product_plans"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True,
                                      comment="套餐代码：trial/standard/operations")
    name: Mapped[str] = mapped_column(String(60), nullable=False, comment="套餐显示名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="套餐说明")
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False,
                                       comment="套餐状态：active/retired")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="展示排序，小在前")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    entitlements: Mapped[list["PlanEntitlement"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["SchoolSubscription"]] = relationship(
        back_populates="plan"
    )

    __table_args__ = (
        Index("idx_product_plan_status_sort", "status", "sort_order"),
    )

    def __repr__(self) -> str:
        return f"<ProductPlan(code='{self.code}', name='{self.name}')>"
