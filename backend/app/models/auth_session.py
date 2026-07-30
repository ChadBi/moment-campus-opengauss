from sqlalchemy import BigInteger, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class AuthSession(Base):
    """服务端会话表 —— 支持多设备会话管理与单端撤销。

    会话特性：
    - 每个 refresh_token 对应一条会话记录
    - 支持按设备/客户端信息标识，便于用户查看登录设备
    - 支持单设备撤销（不影响其他设备）和全部撤销
    - refresh_token_hash 存储 SHA-256 哈希，不存明文
    - binding_ticket 一次性绑定凭证，5 分钟有效
    """

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # refresh_token 哈希（SHA-256），不存明文
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # 会话类型: web / miniprogram / wechat
    session_type: Mapped[str] = mapped_column(String(30), nullable=False, default="web")
    # 客户端信息
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 设备标识（小程序端可用 wx.getSystemInfoSync 获取）
    device_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 会话有效期
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 最后活动时间
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 撤销状态
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    user: Mapped["User"] = relationship(back_populates="auth_sessions")

    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_hash", "refresh_token_hash"),
        Index("idx_session_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<AuthSession(id={self.id}, user_id={self.user_id}, type={self.session_type})>"


class BindingTicket(Base):
    """微信绑定凭证 —— 一次性、短时有效。

    流程：
    1. 微信 code2Session 成功但 openid 未绑定 → 生成 binding_ticket
    2. 客户端带 binding_ticket + 邮箱密码 → 绑定已有账号
    3. 或 binding_ticket + 新用户信息 → 创建新账号并绑定

    安全：
    - ticket 存 SHA-256 哈希，不存明文
    - 5 分钟有效，一次性使用
    """

    __tablename__ = "binding_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # ticket 哈希
    ticket_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # 微信 openid
    openid: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    unionid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 票据状态
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 客户端 IP（审计）
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        Index("idx_binding_openid", "openid"),
    )

    def __repr__(self) -> str:
        return f"<BindingTicket(id={self.id}, openid={self.openid[:8]}...)>"
