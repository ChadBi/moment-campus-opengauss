"""地点稳定资料与用户提议模型。

稳定资料不由 AI 直接改写。认证用户可以提交整批变更，管理员审核后才会
写入当前事实表，并触发地点摘要刷新。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LocationFact(Base):
    __tablename__ = "location_facts"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_key: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    location: Mapped["Location"] = relationship(back_populates="facts")
    approver: Mapped["User | None"] = relationship(foreign_keys=[approved_by])

    __table_args__ = (
        Index("idx_location_facts_location_active", "location_id", "is_active", "sort_order"),
        Index("idx_location_facts_school_key", "school_id", "fact_key"),
    )


class LocationFactProposal(Base):
    __tablename__ = "location_fact_proposals"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    proposer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    changes_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    location: Mapped["Location"] = relationship(back_populates="fact_proposals")
    proposer: Mapped["User"] = relationship(
        foreign_keys=[proposer_id], back_populates="location_fact_proposals"
    )
    reviewer: Mapped["User | None"] = relationship(
        foreign_keys=[reviewer_id], back_populates="reviewed_location_fact_proposals"
    )

    __table_args__ = (
        Index("idx_location_fact_proposals_queue", "school_id", "status", "created_at"),
        Index("idx_location_fact_proposals_user_status", "proposer_id", "status"),
    )
