from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(10), nullable=True)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    school: Mapped["School"] = relationship(back_populates="locations")
    posts: Mapped[list["Post"]] = relationship(back_populates="location")

    __table_args__ = (
        Index("idx_location_school", "school_id"),
        Index("idx_location_coords", "latitude", "longitude"),
        Index("idx_location_school_name", "school_id", "name"),
        Index("idx_location_verified", "is_verified"),
    )

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}')>"
