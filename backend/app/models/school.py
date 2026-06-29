from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    center_lat: Mapped[float | None] = mapped_column(nullable=True)
    center_lng: Mapped[float | None] = mapped_column(nullable=True)
    map_zoom: Mapped[int | None] = mapped_column(default=15, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    users: Mapped[list["User"]] = relationship(back_populates="school")
    posts: Mapped[list["Post"]] = relationship(back_populates="school")
    locations: Mapped[list["Location"]] = relationship(back_populates="school")
    topic_collections: Mapped[list["TopicCollection"]] = relationship(back_populates="school")

    __table_args__ = (
        Index("idx_school_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<School(id={self.id}, name='{self.name}')>"
