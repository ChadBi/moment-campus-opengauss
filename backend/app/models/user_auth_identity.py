from sqlalchemy import BigInteger, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class UserAuthIdentity(Base):
    """用户身份表 —— 支持多种登录方式统一账号。

    身份类型 (identity_type):
    - email_password: 历史身份类型（已废弃，不再作为有效登录入口）
    - wechat_miniprogram: 微信小程序登录（openid 标识）

    设计原则：
    - 一个 User 可拥有多个 Identity（当前保留微信小程序身份）
    - 同一 identity_type + identity_key 全局唯一（防止重复绑定）
    - 新增身份不影响现有登录流程（双读兼容）
    """

    __tablename__ = "user_auth_identities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    identity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="身份类型: 历史 email_password / wechat_miniprogram",
    )
    identity_key: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="身份标识: 邮箱地址 / 微信 openid",
    )
    # 历史 email_password 类型曾使用；当前微信身份为 NULL
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 微信相关字段
    openid: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    unionid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 身份创建/最后使用时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 软删除
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    user: Mapped["User"] = relationship(back_populates="auth_identities")

    __table_args__ = (
        # 同一类型 + 标识全局唯一（含 is_deleted 过滤由应用层保证）
        Index("uq_identity_type_key", "identity_type", "identity_key", unique=True),
        Index("idx_identity_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserAuthIdentity(id={self.id}, type={self.identity_type}, key={self.identity_key})>"
