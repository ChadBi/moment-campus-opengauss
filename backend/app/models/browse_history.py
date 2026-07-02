from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class BrowseHistory(Base):
    __tablename__ = "browse_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    user: Mapped["User"] = relationship(back_populates="browse_histories")
    post: Mapped["Post"] = relationship()

    __table_args__ = (
        Index("idx_browse_user", "user_id", "created_at"),
        Index("idx_browse_post", "post_id"),
    )

    def __repr__(self) -> str:
        return f"<BrowseHistory(user_id={self.user_id}, post_id={self.post_id})>"
