from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class Feedback(Base):
    """用户反馈（建议/问题/投诉/其他）

    - user_id / school_id：记录提交者与其所属学校（TEN-02 三校隔离）
    - feedback_type：suggestion / bug / complaint / other
    - status：open / in_review / resolved（默认 open）
    - remark：管理员处理备注（可空）
    - resolved_at：进入 resolved 状态时写入
    """
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schools.id"), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="反馈类型：suggestion / bug / complaint / other")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="反馈内容")
    contact: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="联系方式（可空）")
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True, comment="状态：open / in_review / resolved")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="管理员处理备注")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="处理完成时间（进入 resolved 时写入）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 关系
    user: Mapped["User"] = relationship(back_populates="feedbacks")

    __table_args__ = (
        Index("idx_feedback_school_status", "school_id", "status", "created_at"),
        Index("idx_feedback_user_school", "user_id", "school_id"),
    )

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, feedback_type='{self.feedback_type}', status='{self.status}')>"