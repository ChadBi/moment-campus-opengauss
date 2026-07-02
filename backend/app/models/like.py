from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    post: Mapped["Post"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship(back_populates="likes")

    __table_args__ = (
        Index("idx_like_post_user", "post_id", "user_id", unique=True),
        Index("idx_like_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Like(post_id={self.post_id}, user_id={self.user_id})>"
