from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PostChangeReport(Base):
    """GOV-01.1: 帖子变更/问题报告（3 类）

    承载 5 类协同验证中的 3 类"问题报告"：
    - update: 更新建议（提供更新信息）
    - expiration_report: 过期报告（报告信息已过期）
    - conflict_report: 冲突报告（报告与其他信息冲突）

    另外 2 类互斥投票（confirmation/refutation）仍由 validation_records 表承载，保持不变。

    处理状态机：open（待处理）→ in_review（处理中）→ resolved（已解决）/ dismissed（驳回）。
    作者可标记已更新/已处理（resolved）；管理员可执行全部状态流转。
    """
    __tablename__ = "post_change_reports"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="问题报告类型：update/expiration_report/conflict_report（3 类）",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="报告说明")
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="证据链接")
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        index=True,
        comment="处理状态：open/in_review/resolved/dismissed",
    )
    handler_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    handler_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="处理说明/原因")
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系（不反向绑定到 Post/User，避免侵入既有模型；API 层按 post_id 直接查询）
    post: Mapped["Post"] = relationship(foreign_keys=[post_id])
    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_id])
    handler: Mapped["User | None"] = relationship(foreign_keys=[handler_id])

    __table_args__ = (
        Index("idx_pcr_post_status", "post_id", "status"),
        Index("idx_pcr_post_type", "post_id", "report_type"),
        Index("idx_pcr_reporter", "reporter_id"),
        Index("idx_pcr_handler", "handler_id"),
        Index("idx_pcr_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PostChangeReport(id={self.id}, post_id={self.post_id}, type='{self.report_type}')>"
