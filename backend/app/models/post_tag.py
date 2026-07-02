from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PostTag(Base):
    __tablename__ = "post_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tags.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系
    post: Mapped["Post"] = relationship(back_populates="post_tags")
    tag: Mapped["Tag"] = relationship(back_populates="post_tags")

    __table_args__ = (
        Index("idx_posttag_post_tag", "post_id", "tag_id", unique=True),
        Index("idx_posttag_tag", "tag_id"),
    )

    def __repr__(self) -> str:
        return f"<PostTag(post_id={self.post_id}, tag_id={self.tag_id})>"
