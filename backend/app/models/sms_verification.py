from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SmsVerification(Base):
    """短信验证码发送记录。

    只保存验证码的哈希，不保存明文验证码。out_id 是一次短信业务流水号，
    既用于阿里云 Send/Check 接口关联，也用于本地 Mock provider 的记录关联。
    """

    __tablename__ = "sms_verifications"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    phone: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment="用途：register / login / set_password / education_unbind",
    )
    out_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="验证码 SHA-256 哈希，不保存明文"
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="mock")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        Index("idx_sms_verification_phone_purpose_sent", "phone", "purpose", "sent_at"),
    )
