from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class LocationReview(Base):
    """REV-01: 地点评分/评价

    每地点每用户一条（唯一约束 location_id+user_id），重新提交=更新，可撤回。
    评分统计（locations.avg_score / rating_count / review_count）由应用服务写入时重算，
    遵循「应用服务为唯一写入口」约定，不引入触发器。
    """

    __tablename__ = "location_reviews"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    school_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分 1-5")
    content: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="评价内容")
    status: Mapped[str] = mapped_column(String(20), default="published", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    location: Mapped["Location"] = relationship(back_populates="reviews")
    user: Mapped["User"] = relationship(back_populates="location_reviews")

    __table_args__ = (
        # 每地点每用户一条评价
        Index("uq_location_reviews_location_user", "location_id", "user_id", unique=True),
        Index("idx_location_reviews_location_created", "location_id", "created_at"),
        Index("idx_location_reviews_school", "school_id"),
        Index("idx_location_reviews_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<LocationReview(location_id={self.location_id}, user_id={self.user_id}, score={self.score})>"