from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class SchoolDomain(Base):
    """学校自有域名映射表：一个域名指向唯一学校。"""

    __tablename__ = "school_domains"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    school: Mapped["School"] = relationship(back_populates="domains")

    __table_args__ = (
        Index("idx_domain_school", "school_id"),
        Index("idx_domain_unique", "domain", unique=True),
    )

    def __repr__(self) -> str:
        return f"<SchoolDomain(school_id={self.school_id}, domain='{self.domain}')>"
