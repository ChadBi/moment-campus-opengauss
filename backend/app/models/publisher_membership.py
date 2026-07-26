"""ORG-01: 发布主体成员关系模型"""
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PublisherMembership(Base):
    __tablename__ = "publisher_memberships"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    publisher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("publisher_profiles.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(20), default="member", nullable=False,
        comment="成员角色：owner/admin/member",
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    publisher: Mapped["PublisherProfile"] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("publisher_id", "user_id", name="uq_publisher_membership"),
        Index("idx_pm_user", "user_id", "role"),
    )

    def __repr__(self) -> str:
        return f"<PublisherMembership(publisher_id={self.publisher_id}, user_id={self.user_id}, role='{self.role}')>"
