from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    post_tags: Mapped[list["PostTag"]] = relationship(back_populates="tag")

    __table_args__ = (
        Index("idx_tag_name", "name", unique=True),
        Index("idx_tag_slug", "slug", unique=True),
        Index("idx_tag_usage", "usage_count"),
        Index("idx_tag_official", "is_official"),
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name='{self.name}')>"
