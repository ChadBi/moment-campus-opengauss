from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class SchoolSettings(Base):
    """学校设置表（一对一）：站点名/说明/审核/匿名/评论/发布频率/图片上限/默认有效期/品牌色/Logo。

    其余扩展字段由 ADM-02 补充。
    """

    __tablename__ = "school_settings"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    site_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    require_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_comments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    publish_frequency: Mapped[int] = mapped_column(Integer, default=10, nullable=False, comment="每日发布上限（0 表示不限）")
    image_limit: Mapped[int] = mapped_column(Integer, default=9, nullable=False, comment="单帖图片上限")
    default_validity_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    brand_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系：一对一（School.settings 反向指向本类 school 属性）
    school: Mapped["School"] = relationship(back_populates="settings")

    __table_args__ = (
        Index("idx_settings_school", "school_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<SchoolSettings(school_id={self.school_id})>"
