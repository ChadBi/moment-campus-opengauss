from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class CampusVerifyToken(Base):
    """B-01: 校园身份认证验证码 Token

    同学提交教育邮箱后，系统生成一次性验证码并存储于此表。
    验证码限时（默认 10 分钟）单次使用，确认后标记 used_at，使用即失效。
    dev 模式可在 send 响应中直接返回验证码，保证演示闭环。
    """

    __tablename__ = "campus_verify_tokens"

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
    school_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="认证所属学校（多租户隔离）",
    )
    target_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="用于认证的校园邮箱",
    )
    token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="验证码的 SHA-256 哈希；不存明文",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="过期时间（默认 10 分钟）"
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

    user: Mapped["User"] = relationship(
        back_populates="campus_verify_tokens", foreign_keys="CampusVerifyToken.user_id"
    )
    school: Mapped["School"] = relationship()

    __table_args__ = (
        Index("idx_cvt_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CampusVerifyToken(user_id={self.user_id}, used={self.used_at is not None})>"
