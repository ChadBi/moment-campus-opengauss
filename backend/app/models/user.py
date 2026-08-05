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
    # ACC-01.3: 重置密码后将此字段设为 now()，refresh 端点校验 token iat >= 此时间，
    # 实现"旧刷新令牌失效"。NULL 表示不限制（兼容历史用户与历史 token）。
    refresh_tokens_invalid_before: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="ACC-01.3: 此时间之前签发的 refresh token 全部失效（重置密码时设置）",
    )
    # 历史物理模型字段：当前主应用不再维护信誉分，仅保留以兼容既有数据库结构。
    reputation_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="历史字段：用户信誉分（当前主应用不再维护）",
    )
    # ACC-01.4: 首次使用引导标记。注册时默认 False，完成引导后设为 True。
    # 教程只在 onboarding_completed=False 时显示（新注册用户首次登录），
    # 登录不再触发教程（已注册用户已为 True）。
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
        comment="ACC-01.4: 是否已完成首次使用引导（注册后默认 False）",
    )
    # B-01: 校园身份认证。同学通过「学号 + 校园邮箱验证码」验证后置为 True，
    # 昵称旁可显示「已认证」徽标，提升内容真实性与信任感（轻量方案，不接人脸/公安）。
    campus_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
        comment="B-01: 是否已完成校园身份认证（默认 False）",
    )
    student_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="B-01: 校园学号（认证通过后记录）",
    )
    campus_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="B-01: 用于认证的校园邮箱（认证通过后记录）",
    )
    campus_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="B-01: 校园身份认证通过时间（NULL 表示未认证）",
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
    # ACC-01.3: 找回密码 Token（一对多）
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")
    # UX-01.5: 通知偏好（一对一）
    notification_preference: Mapped["NotificationPreference | None"] = relationship(back_populates="user", uselist=False)
    # REC-01.2: 推荐隐私偏好（一对一）
    recommendation_preference: Mapped["UserRecommendationPreference | None"] = relationship(back_populates="user", uselist=False)
    # 统一身份（一对多）
    auth_identities: Mapped[list["UserAuthIdentity"]] = relationship(back_populates="user")
    # 服务端会话（一对多）
    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")
    # REV-01: 地点评分/评价
    location_reviews: Mapped[list["LocationReview"]] = relationship(back_populates="user")
    # B-01: 校园身份认证（一对一，可空）
    campus_verify_tokens: Mapped[list["CampusVerifyToken"]] = relationship(
        back_populates="user", foreign_keys="CampusVerifyToken.user_id"
    )

    __table_args__ = (
        Index("idx_user_school", "school_id"),
        Index("idx_user_role", "role"),
        Index("idx_user_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
