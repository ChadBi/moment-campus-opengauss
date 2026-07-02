from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class ValidationRecord(Base):
    __tablename__ = "validation_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    validation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    post: Mapped["Post"] = relationship(back_populates="validation_records")
    user: Mapped["User"] = relationship(back_populates="validation_records")

    __table_args__ = (
        Index("idx_validation_post", "post_id", "created_at"),
        Index("idx_validation_user", "user_id"),
        Index("idx_validation_post_type", "post_id", "validation_type"),
    )

    def __repr__(self) -> str:
        return f"<ValidationRecord(post_id={self.post_id}, type='{self.validation_type}')>"
