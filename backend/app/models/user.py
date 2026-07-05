from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 历史物理模型字段：当前主应用不再维护信誉分，仅保留以兼容既有数据库结构。
    reputation_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="历史字段：用户信誉分（当前主应用不再维护）",
    )

    # 关系
    school: Mapped["School"] = relationship(back_populates="users")
    posts: Mapped[list["Post"]] = relationship(back_populates="user")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user", foreign_keys="Comment.user_id")
    likes: Mapped[list["Like"]] = relationship(back_populates="user")
    validation_records: Mapped[list["ValidationRecord"]] = relationship(back_populates="user")
    reports: Mapped[list["Report"]] = relationship(back_populates="reporter", foreign_keys="Report.reporter_id")
    handled_reports: Mapped[list["Report"]] = relationship(back_populates="handler", foreign_keys="Report.handler_id")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", foreign_keys="Notification.user_id")
    actor_notifications: Mapped[list["Notification"]] = relationship(back_populates="actor", foreign_keys="Notification.actor_id")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="user")
    browse_histories: Mapped[list["BrowseHistory"]] = relationship(back_populates="user")
    search_histories: Mapped[list["SearchHistory"]] = relationship(back_populates="user")
    admin_operation_logs: Mapped[list["AdminOperationLog"]] = relationship(back_populates="admin")
    topic_collections: Mapped[list["TopicCollection"]] = relationship(back_populates="creator")

    __table_args__ = (
        Index("idx_user_school", "school_id"),
        Index("idx_user_role", "role"),
        Index("idx_user_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
