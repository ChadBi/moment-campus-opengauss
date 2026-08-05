from sqlalchemy import BigInteger, String, Text, DateTime, Integer, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("comments.id"), nullable=True, index=True)
    reply_to_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false",
        comment="UC-01: 用户离校后原校评论匿名化标记",
    )

    # 关系
    post: Mapped["Post"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments", foreign_keys=[user_id])
    parent: Mapped["Comment | None"] = relationship(back_populates="replies", remote_side=[id])
    replies: Mapped[list["Comment"]] = relationship(back_populates="parent")
    reply_to_user: Mapped["User | None"] = relationship(foreign_keys=[reply_to_user_id])

    __table_args__ = (
        Index("idx_comment_post", "post_id", "created_at"),
        Index("idx_comment_parent", "parent_id"),
        Index("idx_comment_user", "user_id"),
        Index("idx_comment_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, post_id={self.post_id})>"
