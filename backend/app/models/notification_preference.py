from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


# UX-01.5: 通知偏好类别（与前端 6 类映射）
# Task 2.2 调整：移除 site_digest（每日摘要）类别，邮件通知同步移除。
# - instant:       站内即时通知（默认开）
# - subscription:  订阅类（订阅主体更新等，默认开）
# - interaction:   互动类（点赞/评论/回复，默认开）
# - audit:         审核类（帖子审核结果，默认开；安全账号通知不可全关）
# - governance:    治理类（协同验证/问题报告，默认开）
# - system:        系统类（账号安全、产品公告，默认开；安全账号通知不可全关）
NOTIFICATION_CATEGORIES = (
    "instant",
    "subscription",
    "interaction",
    "audit",
    "governance",
    "system",
)

# 安全类别：不可完全关闭（至少保留站内即时通知）
SECURITY_CATEGORIES = ("system", "audit")


class NotificationPreference(Base):
    """UX-01.5: 用户通知偏好

    Task 2.2 调整：移除 site_digest_enabled / digest_time / email_enabled 三个字段，
    「每日摘要」「邮件通知」功能下线。仅保留 6 类站内通知开关。

    每用户一行（user_id 唯一），记录 6 类通知的开关。
    安全账号通知（system/audit）不可全关——通过 API 层校验保证至少 instant=true。
    """
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # 6 类开关：True=开启，False=关闭
    instant_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="站内即时通知")
    subscription_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="订阅类")
    interaction_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="互动类")
    audit_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="审核类（安全账号通知不可全关）")
    governance_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="治理类")
    system_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="系统类（安全账号通知不可全关）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    user: Mapped["User"] = relationship(back_populates="notification_preference")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id})>"
