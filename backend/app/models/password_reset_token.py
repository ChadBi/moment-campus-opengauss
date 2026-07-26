from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PasswordResetToken(Base):
    """ACC-01.3: 找回密码 Token

    限时单次使用：30 分钟过期，使用后标记 used_at。
    重置密码成功后，对该用户的旧刷新令牌批量失效（user.refresh_tokens_invalid_before = now）。
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="Token 的 SHA-256 哈希；不存明文",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="过期时间（默认 30 分钟）"
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="使用时间；NULL 表示未使用"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="请求发起 IP（审计用）"
    )

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")

    __table_args__ = (
        Index("idx_prt_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PasswordResetToken(user_id={self.user_id}, used={self.used_at is not None})>"
