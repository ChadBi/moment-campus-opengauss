from sqlalchemy import BigInteger, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class TopicCollectionPost(Base):
    __tablename__ = "topic_collection_posts"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    topic_collection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topic_collections.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    topic_collection: Mapped["TopicCollection"] = relationship(back_populates="topic_collection_posts")
    post: Mapped["Post"] = relationship(back_populates="topic_collection_posts")

    __table_args__ = (
        Index("idx_tcp_topic_post", "topic_collection_id", "post_id", unique=True),
        Index("idx_tcp_post", "post_id"),
    )

    def __repr__(self) -> str:
        return f"<TopicCollectionPost(topic_id={self.topic_collection_id}, post_id={self.post_id})>"
