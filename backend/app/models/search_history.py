from sqlalchemy import BigInteger, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class SearchHistory(Base):
    __tablename__ = "search_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    user: Mapped["User"] = relationship(back_populates="search_histories")

    __table_args__ = (
        Index("idx_search_user", "user_id", "created_at"),
        Index("idx_search_keyword", "keyword"),
    )

    def __repr__(self) -> str:
        return f"<SearchHistory(user_id={self.user_id}, keyword='{self.keyword}')>"
