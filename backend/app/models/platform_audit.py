"""TEN-04.3 平台审计日志模型。

记录 super_admin 跨校动作（创建学校/暂停/恢复/分配套餐等），
与 admin_operation_logs（校内管理员动作）解耦，便于平台级审计查询。

字段：操作者 / 目标学校 / 动作类型 / 旧值 / 新值 / 原因 / 时间。
"""
from sqlalchemy import BigInteger, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class PlatformAuditLog(Base):
    """平台审计日志（super_admin 跨校动作）。"""

    __tablename__ = "platform_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    operator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
        comment="操作者 user_id（super_admin）",
    )
    target_school_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True,
        comment="目标学校 ID（创建学校动作可能为 NULL）",
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="动作类型：school.create / school.suspend / school.reactivate / subscription.assign / subscription.update",
    )
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="旧值（JSON 文本）")
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="新值（JSON 文本）")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="操作原因/备注")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)

    # 关系
    operator: Mapped["User | None"] = relationship(foreign_keys=[operator_id])
    target_school: Mapped["School | None"] = relationship(foreign_keys=[target_school_id])

    __table_args__ = (
        Index("idx_platform_audit_operator", "operator_id", "created_at"),
        Index("idx_platform_audit_action", "action"),
        Index("idx_platform_audit_target", "target_school_id", "action"),
        Index("idx_platform_audit_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PlatformAuditLog(id={self.id}, action='{self.action}', target_school_id={self.target_school_id})>"
