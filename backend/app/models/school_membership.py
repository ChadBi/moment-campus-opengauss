from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class SchoolMembership(Base):
    """学校成员关系表（多租户成员模型）。

    user.role 仍保留平台角色（user/admin/super_admin）；
    本表 role 描述该用户在某学校内的角色（member/admin）。
    super_admin 在本表中按 admin 写入，平台权限仍由 user.role 决定。
    """

    __tablename__ = "school_memberships"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        default="member",
        nullable=False,
        comment="成员角色：member/admin（super_admin 仍是平台角色在 user 表）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        comment="成员状态：active/invited/suspended",
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系：不使用 back_populates 引用 User，避免修改 user.py（归属其他子代理）。
    # School 侧使用 back_populates 双向。
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    school: Mapped["School"] = relationship(back_populates="memberships")
    inviter: Mapped["User | None"] = relationship(foreign_keys=[invited_by])

    __table_args__ = (
        # UC-01: 严格一对一绑定——每个用户至多一条 active 成员关系；
        # 历史 left 行不受限制（部分唯一索引仅约束 status='active'）。
        Index(
            "idx_membership_user_active", "user_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("idx_membership_school_role", "school_id", "role"),
        Index("idx_membership_school_status", "school_id", "status"),
        Index("idx_membership_default", "user_id", "is_default"),
    )

    def __repr__(self) -> str:
        return f"<SchoolMembership(user_id={self.user_id}, school_id={self.school_id}, role='{self.role}')>"
