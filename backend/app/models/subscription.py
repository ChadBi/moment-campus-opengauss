from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class UserSubscription(Base):
    """SUB-01: 用户级内容订阅（分类/地点/专题）

    一个用户在同一学校对同一目标（target_type + target_id）只能订阅一次
    （由唯一约束 uq_subscription_user_school_target 保证）。

    target_type 取值：
    - category: 订阅分类（target_id = categories.id）
    - location: 订阅地点（target_id = locations.id）
    - topic:    订阅专题（target_id = topic_collections.id）

    订阅与通知严格按学校隔离：school_id 强制由 TenantContext 决定，
    跨校订阅不可见，跨校通知不触发。

    与 COM-01 SchoolSubscription（学校套餐订阅）无关联，二者命名空间独立。
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    school_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="订阅目标类型：category / location / topic",
    )
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    # 关系（不反向绑定到 User/School，避免侵入既有模型）
    user: Mapped["User"] = relationship()
    school: Mapped["School"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "school_id",
            "target_type",
            "target_id",
            name="uq_subscription_user_school_target",
        ),
        Index("idx_subscription_user_school", "user_id", "school_id"),
        Index("idx_subscription_target", "target_type", "target_id", "school_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserSubscription(id={self.id}, user_id={self.user_id}, "
            f"school_id={self.school_id}, target_type='{self.target_type}', "
            f"target_id={self.target_id})>"
        )
