from sqlalchemy import BigInteger, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class AdminOperationLog(Base):
    __tablename__ = "admin_operation_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)

    # 关系
    admin: Mapped["User"] = relationship(back_populates="admin_operation_logs")

    __table_args__ = (
        Index("idx_adminlog_admin", "admin_id", "created_at"),
        Index("idx_adminlog_action", "action"),
        Index("idx_adminlog_target", "target_type", "target_id"),
        Index("idx_adminlog_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AdminOperationLog(id={self.id}, action='{self.action}')>"
