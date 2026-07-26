"""ORG-01: 官方发布主体认证主页模型

业务规则：
- verified_status 仅由 admin 通过审核接口流转（pending → verified/rejected，verified → revoked）
- 创建时默认 pending（用户不可自行设置 verified）
- 认证不等于内容免审：发布主体关联的帖子仍走原 post_status 状态机审核流程
- 三校隔离：所有查询按 school_id 过滤，跨校访问统一 404
"""
from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PublisherProfile(Base):
    __tablename__ = "publisher_profiles"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="主体类型：department/club/service_org",
    )
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id"), nullable=True)
    service_hours: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True,
        comment="认证状态：pending/verified/revoked/rejected（仅 admin 可流转）",
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    verify_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 聚合效果统计（ORG-01.4）
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscribe_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    share_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    zero_result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    memberships: Mapped[list["PublisherMembership"]] = relationship(
        back_populates="publisher", cascade="all, delete-orphan",
    )
    templates: Mapped[list["PostTemplate"]] = relationship(
        back_populates="publisher", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_publisher_school_status", "school_id", "verified_status"),
        Index("idx_publisher_type", "school_id", "type"),
    )

    def __repr__(self) -> str:
        return f"<PublisherProfile(id={self.id}, name='{self.name}', status='{self.verified_status}')>"
