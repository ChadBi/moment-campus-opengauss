from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(10), nullable=True)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # REV-01: 地点评分汇总（由应用服务写入时重算）
    avg_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0, nullable=False, comment="平均评分（1-5，保留 2 位）")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="评分人数（有分评价数）")
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="评价条数")
    # 地点知识层：当前已批准摘要和待刷新标记
    current_summary_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "location_summary_versions.id",
            ondelete="SET NULL",
            name="fk_locations_current_summary",
            use_alter=True,
        ),
        nullable=True,
    )
    summary_dirty_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    school: Mapped["School"] = relationship(back_populates="locations")
    posts: Mapped[list["Post"]] = relationship(back_populates="location")
    reviews: Mapped[list["LocationReview"]] = relationship(back_populates="location")
    facts: Mapped[list["LocationFact"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    fact_proposals: Mapped[list["LocationFactProposal"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    summary_versions: Mapped[list["LocationSummaryVersion"]] = relationship(
        back_populates="location", foreign_keys="LocationSummaryVersion.location_id", cascade="all, delete-orphan"
    )
    current_summary: Mapped["LocationSummaryVersion | None"] = relationship(
        foreign_keys=[current_summary_id], post_update=True,
    )

    __table_args__ = (
        Index("idx_location_school", "school_id"),
        Index("idx_location_coords", "latitude", "longitude"),
        Index("idx_location_school_name", "school_id", "name"),
        Index("idx_location_verified", "is_verified"),
    )

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}')>"
