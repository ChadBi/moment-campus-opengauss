"""GOV-02.2: 任务运行记录模型。

记录后台批量任务（如自动过期 published → expired）的执行情况：
- job_name: 任务名（如 'expire_posts'）
- status: running / success / failed
- started_at / finished_at: 开始与结束时间
- processed_count / failed_count: 处理与失败数量
- error_message: 失败原因（JSON 文本，含 failed_ids 等）
- triggered_by: 触发者标识（'system' / 'manual' / user_id 字符串）
- triggered_user_id: 手动触发时的 user_id（NULL 表示系统定时触发）
- dry_run: 是否为 dry-run 模式（只报告不执行）
- metadata_: JSON 文本，存放额外元数据（如 failed_ids 列表）

幂等键约束：同一 job_name 同时只允许一条 status='running' 记录
（应用层先 SELECT 再 INSERT 校验，避免多实例并发执行）。
"""
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class JobRunRecord(Base):
    """任务运行记录。"""

    __tablename__ = "job_run_records"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    job_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="任务名：expire_posts / summarize_usage 等",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="运行状态：running / success / failed",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="任务开始时间",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="任务结束时间（running 时为 NULL）",
    )
    processed_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="成功处理数量",
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="失败数量",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败原因或 JSON 文本（含 failed_ids 等）",
    )
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="system",
        comment="触发者：system / manual / 手动触发的 user_id",
    )
    triggered_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="手动触发时的 user_id；NULL 表示系统定时触发",
    )
    dry_run: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="是否为 dry-run（只报告不执行）",
    )
    metadata_: Mapped[str | None] = mapped_column(
        "metadata",
        Text,
        nullable=True,
        comment="JSON 文本，存放额外元数据（如 failed_ids 列表）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False,
    )

    # 关系
    triggered_user: Mapped["User | None"] = relationship(
        foreign_keys=[triggered_user_id],
    )

    __table_args__ = (
        Index("idx_job_run_name_status", "job_name", "status"),
        Index("idx_job_run_started", "started_at"),
        Index("idx_job_run_triggered", "triggered_by", "started_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<JobRunRecord(id={self.id}, job_name='{self.job_name}', "
            f"status='{self.status}', dry_run={self.dry_run})>"
        )
