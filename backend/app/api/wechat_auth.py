"""微信小程序手机号登录与会话管理。"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _issue_login
from app.config import settings
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException, UnauthorizedException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth_session import AuthSession
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.schemas.wechat_auth import (
    IdentityListResponse,
    IdentityResponse,
    LogoutAllResponse,
    SessionListResponse,
    SessionResponse,
    WechatPhoneLoginRequest,
    WechatPhoneLoginResponse,
)
from app.services.sms import normalize_phone
from app.services.wechat import exchange_wechat_code, exchange_wechat_phone_code

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/wechat", tags=["微信认证"])


async def _resolve_school(db: AsyncSession, school_code: Optional[str]) -> School:
    code = (school_code or settings.SCHOOL_CODE or "jiangnan").strip()
    result = await db.execute(select(School).where(School.code == code, School.is_active.is_(True)))
    school = result.scalar_one_or_none()
    if school is None:
        result = await db.execute(select(School).where(School.code == "jiangnan", School.is_active.is_(True)))
        school = result.scalar_one_or_none()
    if school is None:
        raise BadRequestException(detail="暂时无法确定当前学校")
    return school


@router.post("/phone-login", response_model=WechatPhoneLoginResponse, summary="微信授权手机号登录")
async def phone_login(
    data: WechatPhoneLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    wx_result = await exchange_wechat_code(data.code)
    openid = wx_result["openid"]
    phone = normalize_phone(await exchange_wechat_phone_code(data.phone_code))

    identity_result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.identity_type == "wechat_miniprogram",
            UserAuthIdentity.identity_key == openid,
            UserAuthIdentity.is_deleted.is_(False),
        )
    )
    identity = identity_result.scalar_one_or_none()

    phone_result = await db.execute(select(User).where(User.phone == phone))
    phone_user = phone_result.scalar_one_or_none()
    identity_user = None
    if identity is not None:
        identity_user_result = await db.execute(select(User).where(User.id == identity.user_id))
        identity_user = identity_user_result.scalar_one_or_none()

    # 手机号是唯一业务身份：已有手机号优先。若历史微信身份指向另一条旧账号，
    # 将微信身份迁移到手机号账号并停用旧壳账号，避免一手机号多账号。
    user = phone_user or identity_user
    if phone_user is not None and identity_user is not None and phone_user.id != identity_user.id:
        identity.user_id = phone_user.id
        identity_user.is_active = False
        identity_user.is_deleted = True
        identity_user.deleted_at = datetime.now()
        user = phone_user

    if user is None:
        school = await _resolve_school(db, data.school_code)
        user = User(
            phone=phone,
            email=None,
            education_email=None,
            nickname="此刻用户",
            password_hash=None,
            school_id=school.id,
            registration_school_id=school.id,
            campus_verified=False,
        )
        db.add(user)
        await db.flush()
        db.add(
            SchoolMembership(
                user_id=user.id,
                school_id=school.id,
                role="member",
                status="active",
                is_default=True,
                joined_at=datetime.now(),
            )
        )
    elif user.phone is None:
        user.phone = phone

    if identity is None:
        identity = UserAuthIdentity(
            user_id=user.id,
            identity_type="wechat_miniprogram",
            identity_key=openid,
            openid=openid,
            unionid=wx_result.get("unionid"),
            last_used_at=datetime.now(),
        )
        db.add(identity)
    else:
        identity.user_id = user.id
        identity.last_used_at = datetime.now()
    user.last_login_at = datetime.now()
    result = await _issue_login(db, user, "miniprogram")
    return WechatPhoneLoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=result.user.model_dump(),
    )


@router.api_route("/exchange", methods=["POST"], summary="已废弃：微信邮箱绑定交换")
async def legacy_exchange():
    raise BadRequestException(detail="旧微信邮箱绑定流程已下线，请使用微信手机号授权登录")


@router.api_route("/bind-existing", methods=["POST"], summary="已废弃：微信绑定邮箱账号")
async def legacy_bind_existing():
    raise BadRequestException(detail="旧微信邮箱绑定流程已下线，请使用微信手机号授权登录")


@router.api_route("/register", methods=["POST"], summary="已废弃：微信邮箱注册")
async def legacy_register():
    raise BadRequestException(detail="旧微信邮箱注册流程已下线，请使用微信手机号授权登录")


@router.get("/identities", response_model=IdentityListResponse, summary="查看微信身份")
async def list_identities(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.is_deleted.is_(False),
        )
    )
    return IdentityListResponse(identities=[IdentityResponse.model_validate(i) for i in result.scalars().all()])


@router.get("/sessions", response_model=SessionListResponse, summary="查看登录设备列表")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.is_revoked.is_(False),
            AuthSession.expires_at > datetime.now(),
        )
        .order_by(AuthSession.created_at.desc())
    )
    return SessionListResponse(sessions=[SessionResponse.model_validate(s) for s in result.scalars().all()])


@router.delete("/sessions/{session_id}", response_model=MessageResponse, summary="撤销指定设备会话")
async def revoke_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id))
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundException(detail="会话不存在")
    session.is_revoked = True
    session.revoked_at = datetime.now()
    await db.commit()
    return MessageResponse(message="会话已撤销")


@router.post("/logout-all", response_model=LogoutAllResponse, summary="退出全部设备")
async def logout_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.is_revoked.is_(False))
    )
    sessions = result.scalars().all()
    for session in sessions:
        session.is_revoked = True
        session.revoked_at = datetime.now()
    await db.commit()
    return LogoutAllResponse(message="已退出所有设备", revoked_count=len(sessions))
