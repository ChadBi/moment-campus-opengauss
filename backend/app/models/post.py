from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Text, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=False, index=True)
    post_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("post_types.id"), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    activity_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activity_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lost_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_top: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recommend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    user: Mapped["User"] = relationship(back_populates="posts")
    school: Mapped["School"] = relationship(back_populates="posts")
    category: Mapped["Category"] = relationship(back_populates="posts")
    post_type: Mapped["PostType"] = relationship(back_populates="posts")
    location: Mapped["Location | None"] = relationship(back_populates="posts")
    post_tags: Mapped[list["PostTag"]] = relationship(back_populates="post")
    post_images: Mapped[list["PostImage"]] = relationship(back_populates="post")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    likes: Mapped[list["Like"]] = relationship(back_populates="post")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="post")
    validation_records: Mapped[list["ValidationRecord"]] = relationship(back_populates="post")
    reports: Mapped[list["Report"]] = relationship(back_populates="post")
    topic_collection_posts: Mapped[list["TopicCollectionPost"]] = relationship(back_populates="post")

    __table_args__ = (
        Index("idx_post_user", "user_id"),
        Index("idx_post_school_status", "school_id", "status"),
        Index("idx_post_category", "category_id"),
        Index("idx_post_type", "post_type_id"),
        Index("idx_post_location", "location_id"),
        Index("idx_post_status_created", "status", "created_at"),
        Index("idx_post_status_recommend", "status", "is_recommend", "created_at"),
        Index("idx_post_expire", "expire_at"),
        Index("idx_post_school_category", "school_id", "category_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, title='{self.title}')>"
