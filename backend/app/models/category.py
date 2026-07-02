from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    default_validity_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    posts: Mapped[list["Post"]] = relationship(back_populates="category")

    __table_args__ = (
        Index("idx_category_code", "code", unique=True),
        Index("idx_category_sort", "sort_order"),
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"
