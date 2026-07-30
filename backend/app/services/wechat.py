import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.models.auth_session import BindingTicket

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    """对明文 token 取 SHA-256 哈希；DB 仅存哈希。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_binding_ticket() -> str:
    """生成 URL 安全的随机 binding_ticket（32 字节 = 43 字符 base64url）。"""
    return secrets.token_urlsafe(32)


async def exchange_wechat_code(code: str) -> dict:
    """调用微信 code2Session 接口换取 openid/session_key。

    文档: https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html
    如果 AppID/AppSecret 未配置，返回模拟数据（开发模式）。

    Returns:
        dict: {"openid": str, "session_key": str, "unionid": str|None}

    Raises:
        BadRequestException: 微信接口返回错误
    """
    if not settings.WECHAT_APPID or not settings.WECHAT_APPSECRET:
        logger.warning("微信 AppID/AppSecret 未配置，使用模拟模式")
        return {
            "openid": f"mock_openid_{code[:16]}",
            "session_key": f"mock_session_key_{secrets.token_hex(16)}",
            "unionid": None,
        }

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WECHAT_APPID,
        "secret": settings.WECHAT_APPSECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"微信 code2Session 请求失败: {e}")
        raise BadRequestException(detail="微信登录服务暂时不可用，请重试")

    if "openid" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "微信接口返回错误")
        logger.error(f"微信 code2Session 错误: errcode={errcode}, errmsg={errmsg}")
        raise BadRequestException(detail=f"微信登录失败：{errmsg}")

    return {
        "openid": data["openid"],
        "session_key": data.get("session_key", ""),
        "unionid": data.get("unionid"),
    }


async def create_binding_ticket(
    db: AsyncSession,
    openid: str,
    unionid: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> str:
    """创建 binding_ticket 并返回明文。

    安全：ticket 存 SHA-256 哈希，不存明文。
    有效期由 settings.BINDING_TICKET_EXPIRE_SECONDS 控制。
    """
    ticket = _generate_binding_ticket()
    ticket_hash = _hash_token(ticket)
    expires_at = datetime.now() + timedelta(seconds=settings.BINDING_TICKET_EXPIRE_SECONDS)

    bt = BindingTicket(
        ticket_hash=ticket_hash,
        openid=openid,
        unionid=unionid,
        expires_at=expires_at,
        client_ip=client_ip,
    )
    db.add(bt)
    await db.commit()

    logger.info(f"创建 binding_ticket: openid={openid[:8]}... expires_at={expires_at}")
    return ticket


async def consume_binding_ticket(
    db: AsyncSession,
    ticket: str,
) -> Optional[BindingTicket]:
    """验证并消费 binding_ticket（一次性使用）。

    Returns:
        BindingTicket: 验证通过的票据对象
        None: 票据不存在、已使用或已过期
    """
    ticket_hash = _hash_token(ticket)
    result = await db.execute(
        select(BindingTicket).where(BindingTicket.ticket_hash == ticket_hash)
    )
    bt = result.scalar_one_or_none()

    if bt is None:
        logger.warning("binding_ticket 不存在")
        return None

    if bt.used_at is not None:
        logger.warning("binding_ticket 已使用")
        return None

    if datetime.now() > bt.expires_at:
        logger.warning("binding_ticket 已过期")
        return None

    # 标记已使用
    bt.used_at = datetime.now()
    await db.commit()

    logger.info(f"binding_ticket 已消费: openid={bt.openid[:8]}...")
    return bt


async def revoke_expired_binding_tickets(db: AsyncSession) -> int:
    """清理过期且已使用的 binding_ticket。

    Returns:
        int: 清理数量
    """
    result = await db.execute(
        select(BindingTicket).where(
            BindingTicket.expires_at < datetime.now(),
            BindingTicket.used_at.isnot(None),
        )
    )
    old_tickets = result.scalars().all()
    count = len(old_tickets)
    if count > 0:
        for t in old_tickets:
            await db.delete(t)
        await db.commit()
        logger.info(f"清理过期 binding_ticket: {count} 条")
    return count
