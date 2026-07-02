from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=True, index=True)
    comment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("comments.id"), nullable=True, index=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    handler_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    handle_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    post: Mapped["Post | None"] = relationship(back_populates="reports")
    comment: Mapped["Comment | None"] = relationship()
    reporter: Mapped["User"] = relationship(back_populates="reports", foreign_keys=[reporter_id])
    handler: Mapped["User | None"] = relationship(back_populates="handled_reports", foreign_keys=[handler_id])

    __table_args__ = (
        Index("idx_report_post_reporter", "post_id", "reporter_id", unique=True),
        Index("idx_report_status", "status", "created_at"),
        Index("idx_report_handler", "handler_id"),
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, status='{self.status}')>"
