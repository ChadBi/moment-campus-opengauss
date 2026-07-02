from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    user: Mapped["User"] = relationship(back_populates="notifications", foreign_keys=[user_id])
    actor: Mapped["User | None"] = relationship(back_populates="actor_notifications", foreign_keys=[actor_id])

    __table_args__ = (
        Index("idx_notification_user_read", "user_id", "is_read", "created_at"),
        Index("idx_notification_user_type", "user_id", "type"),
        Index("idx_notification_target", "target_type", "target_id"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type='{self.type}')>"
