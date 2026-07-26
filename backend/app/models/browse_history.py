from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class BrowseHistory(Base):
    __tablename__ = "browse_histories"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    # PRF-01.3: 按学校隔离浏览历史，跨校历史不会出现在当前学校下
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    # PRF-01.3: viewed_at 为最近一次浏览时间（同帖再次浏览更新此字段）
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    user: Mapped["User"] = relationship(back_populates="browse_histories")
    post: Mapped["Post"] = relationship()

    __table_args__ = (
        Index("idx_browse_user", "user_id", "viewed_at"),
        Index("idx_browse_post", "post_id"),
        # PRF-01.3: 同一用户在同一学校对同一帖子只保留一条记录（upsert 依据）
        Index("idx_browse_user_school_post", "user_id", "school_id", "post_id", unique=True),
        Index("idx_browse_school_viewed", "school_id", "viewed_at"),
    )

    def __repr__(self) -> str:
        return f"<BrowseHistory(user_id={self.user_id}, school_id={self.school_id}, post_id={self.post_id})>"
