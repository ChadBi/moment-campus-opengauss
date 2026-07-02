from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    post: Mapped["Post"] = relationship(back_populates="favorites")
    user: Mapped["User"] = relationship(back_populates="favorites")

    __table_args__ = (
        Index("idx_favorite_post_user", "post_id", "user_id", unique=True),
        Index("idx_favorite_user", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Favorite(post_id={self.post_id}, user_id={self.user_id})>"
