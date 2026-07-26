"""ORG-01.3: 高频场景发布模板模型

场景（scene）：
- business_hours：营业时间
- lecture：讲座
- lost：失物
- notification：通知
- other：其它

设计要点：
- school_id 必填（三校隔离），publisher_id 可空（NULL 表示学校级公共模板）
- AI 只补全建议，发布者确认；模板本身是预设结构，不含 AI 生成内容
- 模板中的占位符（如 {{时间}} / {{地点}}）由前端 PostForm 渲染为输入框
"""
from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PostTemplate(Base):
    __tablename__ = "post_templates"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    publisher_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("publisher_profiles.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title_template: Mapped[str] = mapped_column(String(200), nullable=False)
    content_template: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    post_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("post_types.id"), nullable=True)
    scene: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="场景：business_hours/lecture/lost/notification/other",
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    publisher: Mapped["PublisherProfile | None"] = relationship(back_populates="templates")

    __table_args__ = (
        Index("idx_pt_school_scene", "school_id", "scene", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<PostTemplate(id={self.id}, name='{self.name}', scene='{self.scene}')>"
