"""地点 AI 摘要版本模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LocationSummaryVersion(Base):
    __tablename__ = "location_summary_versions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending_review", nullable=False, index=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_level: Mapped[str] = mapped_column(String(20), default="insufficient", nullable=False)
    claims_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    conflicts_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_refs_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    stale_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_log_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_invocation_logs.id", ondelete="SET NULL"), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    location: Mapped["Location"] = relationship(
        back_populates="summary_versions", foreign_keys=[location_id]
    )
    reviewer: Mapped["User | None"] = relationship(
        foreign_keys=[reviewer_id], back_populates="location_summary_reviews"
    )

    __table_args__ = (
        Index("idx_location_summary_queue", "school_id", "status", "generated_at"),
        Index("idx_location_summary_location_version", "location_id", "version"),
        Index("idx_location_summary_source_hash", "location_id", "source_hash"),
    )
