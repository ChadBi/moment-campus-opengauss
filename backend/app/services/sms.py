"""短信验证码服务。

生产使用阿里云 DypnsApi 的 SendSmsVerifyCode/CheckSmsVerifyCode；本地和测试
使用 Mock provider。无论 provider 类型，数据库只保存验证码哈希，不保存明文。
"""

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestException
from app.models.sms_verification import SmsVerification

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if not phone.isdigit() or len(phone) != 11 or not phone.startswith("1"):
        raise BadRequestException(detail="请输入有效的国内 11 位手机号")
    return phone


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class SmsProvider(Protocol):
    name: str

    async def send(self, phone: str, out_id: str, code: str | None, purpose: str = "") -> None: ...

    async def check(self, phone: str, out_id: str, code: str) -> bool: ...


class MockSmsProvider:
    name = "mock"

    async def send(self, phone: str, out_id: str, code: str | None, purpose: str = "") -> None:
        logger.info("Mock SMS sent phone=%s out_id=%s", phone[-4:], out_id)

    async def check(self, phone: str, out_id: str, code: str) -> bool:
        expected = settings.SMS_MOCK_CODE
        return secrets.compare_digest(code, expected)


class AliyunSmsProvider:
    name = "aliyun"

    @staticmethod
    def _template_code(purpose: str) -> str:
        """按短信用途选择阿里云模板，兼容旧版通用模板配置。"""
        purpose_settings = {
            "register": "ALIYUN_SMS_REGISTER_TEMPLATE_CODE",
            "login": "ALIYUN_SMS_LOGIN_TEMPLATE_CODE",
            "set_password": "ALIYUN_SMS_SET_PASSWORD_TEMPLATE_CODE",
            "education_unbind": "ALIYUN_SMS_EDUCATION_UNBIND_TEMPLATE_CODE",
        }
        setting_name = purpose_settings.get(purpose)
        template_code = getattr(settings, setting_name, "") if setting_name else ""
        template_code = template_code or settings.ALIYUN_SMS_TEMPLATE_CODE
        if not template_code:
            raise RuntimeError(f"未配置短信用途 {purpose} 的阿里云模板 CODE")
        return template_code

    def _client(self):
        try:
            from alibabacloud_dypnsapi20170525.client import Client
            from alibabacloud_tea_openapi import models as open_api_models
        except ImportError as exc:
            raise RuntimeError("未安装阿里云短信 SDK，请安装 alibabacloud_dypnsapi20170525") from exc
        config = open_api_models.Config(
            access_key_id=settings.ALIYUN_SMS_ACCESS_KEY_ID,
            access_key_secret=settings.ALIYUN_SMS_ACCESS_KEY_SECRET,
            endpoint=settings.ALIYUN_SMS_ENDPOINT,
        )
        return Client(config)

    async def send(self, phone: str, out_id: str, code: str | None, purpose: str = "") -> None:
        if not settings.ALIYUN_SMS_ACCESS_KEY_ID or not settings.ALIYUN_SMS_ACCESS_KEY_SECRET:
            raise RuntimeError("生产短信 Provider 未配置阿里云密钥")
        from alibabacloud_dypnsapi20170525 import models as dypns_models

        template_code = self._template_code(purpose)

        # 不传明文 code，使用阿里云动态验证码机制，由 CheckSmsVerifyCode 核验。
        request = dypns_models.SendSmsVerifyCodeRequest(
            country_code="86",
            phone_number=phone,
            sign_name=settings.ALIYUN_SMS_SIGN_NAME,
            template_code=template_code,
            template_param=json.dumps({"code": "##code##", "min": "5"}),
            out_id=out_id,
            code_length=6,
            valid_time=settings.SMS_CODE_EXPIRE_SECONDS,
            interval=settings.SMS_SEND_INTERVAL_SECONDS,
            code_type=1,
            duplicate_policy=1,
        )
        response = await asyncio.to_thread(self._client().send_sms_verify_code, request)
        body = getattr(response, "body", None)
        if not body or getattr(body, "code", None) != "OK" or not getattr(body, "success", False):
            raise RuntimeError(f"阿里云短信发送失败：{getattr(body, 'message', 'unknown')}")

    async def check(self, phone: str, out_id: str, code: str) -> bool:
        from alibabacloud_dypnsapi20170525 import models as dypns_models

        request = dypns_models.CheckSmsVerifyCodeRequest(
            country_code="86",
            phone_number=phone,
            verify_code=code,
            out_id=out_id,
        )
        response = await asyncio.to_thread(self._client().check_sms_verify_code, request)
        body = getattr(response, "body", None)
        model = getattr(body, "model", None) if body else None
        return bool(
            body
            and getattr(body, "code", None) == "OK"
            and getattr(body, "success", False)
            and getattr(model, "verify_result", None) == "PASS"
        )


def get_sms_provider() -> SmsProvider:
    provider = (settings.SMS_PROVIDER or "mock").lower()
    if (settings.APP_ENV or "").lower() == "production" and provider != "aliyun":
        raise RuntimeError("生产环境必须使用 SMS_PROVIDER=aliyun")
    if provider == "aliyun":
        return AliyunSmsProvider()
    return MockSmsProvider()


async def send_sms_code(db: AsyncSession, phone: str, purpose: str) -> tuple[str, str | None]:
    phone = normalize_phone(phone)
    now = datetime.now()
    latest_result = await db.execute(
        select(SmsVerification)
        .where(
            SmsVerification.phone == phone,
            SmsVerification.purpose == purpose,
            SmsVerification.is_deleted.is_(False),
        )
        .order_by(SmsVerification.sent_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    if latest and (now - latest.sent_at).total_seconds() < settings.SMS_SEND_INTERVAL_SECONDS:
        raise BadRequestException(detail="验证码发送过于频繁，请 60 秒后再试")

    try:
        provider = get_sms_provider()
    except Exception as exc:
        logger.error("短信 Provider 配置无效")
        raise BadRequestException(detail="短信服务配置无效，请联系管理员") from exc
    out_id = f"mc-{uuid.uuid4().hex}"
    mock_code = settings.SMS_MOCK_CODE if provider.name == "mock" else None
    record = SmsVerification(
        phone=phone,
        purpose=purpose,
        out_id=out_id,
        code_hash=_hash_code(mock_code or secrets.token_urlsafe(24)),
        sent_at=now,
        expires_at=now + timedelta(seconds=settings.SMS_CODE_EXPIRE_SECONDS),
        provider=provider.name,
    )
    db.add(record)
    try:
        await provider.send(phone, out_id, mock_code, purpose)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("短信发送失败 phone=%s purpose=%s", phone[-4:], purpose)
        raise BadRequestException(detail="短信服务暂时不可用，请稍后重试") from exc

    expose_code = mock_code if provider.name == "mock" and settings.APP_ENV != "production" else None
    return out_id, expose_code


async def verify_sms_code(
    db: AsyncSession, phone: str, purpose: str, code: str,
) -> SmsVerification:
    phone = normalize_phone(phone)
    now = datetime.now()
    result = await db.execute(
        select(SmsVerification)
        .where(
            SmsVerification.phone == phone,
            SmsVerification.purpose == purpose,
            SmsVerification.used_at.is_(None),
            SmsVerification.is_deleted.is_(False),
        )
        .order_by(SmsVerification.sent_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None or record.expires_at < now:
        raise BadRequestException(detail="验证码无效或已过期")

    provider = get_sms_provider()
    valid = await provider.check(phone, record.out_id, code)
    if not valid:
        raise BadRequestException(detail="验证码错误")

    record.used_at = now
    await db.flush()
    return record
