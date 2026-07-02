from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PostType(Base):
    __tablename__ = "post_types"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    posts: Mapped[list["Post"]] = relationship(back_populates="post_type")

    __table_args__ = (
        Index("idx_posttype_code", "code", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PostType(id={self.id}, name='{self.name}')>"
