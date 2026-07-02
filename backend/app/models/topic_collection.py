from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class TopicCollection(Base):
    __tablename__ = "topic_collections"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    school: Mapped["School"] = relationship(back_populates="topic_collections")
    creator: Mapped["User"] = relationship(back_populates="topic_collections")
    topic_collection_posts: Mapped[list["TopicCollectionPost"]] = relationship(back_populates="topic_collection")

    __table_args__ = (
        Index("idx_topic_school", "school_id", "status"),
        Index("idx_topic_sort", "sort_order"),
        Index("idx_topic_creator", "creator_id"),
    )

    def __repr__(self) -> str:
        return f"<TopicCollection(id={self.id}, title='{self.title}')>"
