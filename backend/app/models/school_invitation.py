from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class SchoolInvitation(Base):
    """学校邀请表：管理员邀请邮箱加入某校。

    ACC-01.2: invite_code 消费闭环
    - invitation_code: 邀请码（全局唯一）
    - status: expires（未使用，等待接受）/ accepted（已使用）/ declined
    - expires_at: 邀请码过期时间（NULL 表示不限时）
    - accepted_at: 接受时间（即 used_at 语义）
    - used_by: 接受者用户 ID（即注册或加入时使用该邀请码的用户）
    """

    __tablename__ = "school_invitations"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    invitation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    invited_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="expires",
        nullable=False,
        comment="邀请状态：expires/accepted/declined",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # ACC-01.2: 邀请码过期时间；NULL 表示不限时
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="ACC-01.2: 邀请码过期时间，NULL 表示不限时",
    )
    # ACC-01.2: 邀请码使用者（接受邀请的用户 ID）；NULL 表示尚未被使用
    used_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ACC-01.2: 实际使用该邀请码的用户 ID",
    )

    # 关系
    school: Mapped["School"] = relationship(back_populates="invitations")
    inviter: Mapped["User | None"] = relationship(foreign_keys=[invited_by])
    used_by_user: Mapped["User | None"] = relationship(foreign_keys=[used_by])

    __table_args__ = (
        Index("idx_invitation_school_status", "school_id", "status"),
        Index("idx_invitation_email_status", "email", "status"),
        Index("idx_invitation_code", "invitation_code", unique=True),
    )

    def __repr__(self) -> str:
        return f"<SchoolInvitation(school_id={self.school_id}, email='{self.email}', status='{self.status}')>"
