"""手机号主账号认证接口。"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestException, ConflictException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth_session import AuthSession
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    LoginResponse,
    PasswordSetRequest,
    RefreshTokenRequest,
    SmsSendRequest,
    SmsSendResponse,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.sms import normalize_phone, send_sms_code, verify_sms_code

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


async def _resolve_school_id_from_header(db: AsyncSession, x_school_code: Optional[str]) -> Optional[int]:
    if not x_school_code or not x_school_code.strip():
        return None
    result = await db.execute(
        select(School).where(School.code == x_school_code.strip(), School.is_active.is_(True))
    )
    school = result.scalar_one_or_none()
    return school.id if school else None


async def _issue_login(db: AsyncSession, user: User, session_type: str = "web") -> LoginResponse:
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    db.add(
        AuthSession(
            user_id=user.id,
            refresh_token_hash=hashlib.sha256(refresh_token.encode("utf-8")).hexdigest(),
            session_type=session_type,
            expires_at=datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            last_active_at=datetime.now(),
        )
    )
    await db.commit()
    await db.refresh(user)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/sms/send", response_model=SmsSendResponse, summary="发送短信验证码")
async def send_sms(
    data: SmsSendRequest,
    db: AsyncSession = Depends(get_db),
):
    phone = normalize_phone(data.phone)
    out_id, code = await send_sms_code(db, phone, data.purpose)
    return SmsSendResponse(message="验证码已发送", out_id=out_id, code=code)


@router.post("/register", response_model=LoginResponse, summary="手机号注册")
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
    x_school_code: Optional[str] = Header(default=None, alias="X-School-Code"),
):
    phone = normalize_phone(data.phone)
    school_id = data.school_id or await _resolve_school_id_from_header(db, x_school_code)
    if school_id is None:
        raise BadRequestException(detail="无法确定注册学校，请选择学校")

    existing = await db.execute(select(User).where(User.phone == phone))
    if existing.scalar_one_or_none() is not None:
        raise ConflictException(detail="该手机号已注册，请直接登录")

    await verify_sms_code(db, phone, "register", data.sms_code)
    password_hash = get_password_hash(data.password)
    user = User(
        phone=phone,
        email=None,
        education_email=None,
        nickname="此刻用户",
        password_hash=password_hash,
        school_id=school_id,
        registration_school_id=school_id,
        campus_verified=False,
    )
    db.add(user)
    await db.flush()
    db.add(
        SchoolMembership(
            user_id=user.id,
            school_id=school_id,
            role="member",
            status="active",
            is_default=True,
            joined_at=datetime.now(),
        )
    )
    user.last_login_at = datetime.now()
    await db.commit()
    await db.refresh(user)
    return await _issue_login(db, user, "web")


@router.post("/login", response_model=LoginResponse, summary="手机号登录")
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    phone = normalize_phone(data.phone)
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedException(detail="该手机号未注册，请先注册")
    if not user.is_active or user.is_deleted:
        raise UnauthorizedException(detail="账号已被禁用或删除")

    if data.sms_code:
        await verify_sms_code(db, phone, "login", data.sms_code)
    elif not user.password_hash or not verify_password(data.password or "", user.password_hash):
        raise UnauthorizedException(detail="手机号或密码错误")

    user.last_login_at = datetime.now()
    return await _issue_login(db, user, "web")


@router.post("/password/set", response_model=MessageResponse, summary="设置密码")
async def set_password(
    data: PasswordSetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.password_hash:
        raise ConflictException(detail="密码已设置，不能重复设置")
    current_user.password_hash = get_password_hash(data.password)
    current_user.updated_at = datetime.now()
    await db.commit()
    return MessageResponse(message="密码设置成功")


@router.post("/refresh", response_model=Token, summary="刷新 Token")
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if payload is None or payload.get("type") != "refresh" or payload.get("sub") is None:
        raise UnauthorizedException(detail="无效的 refresh_token")

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.is_deleted:
        raise UnauthorizedException(detail="用户不存在或已被禁用")
    if user.refresh_tokens_invalid_before is not None:
        try:
            if float(payload.get("iat", 0)) < user.refresh_tokens_invalid_before.timestamp():
                raise UnauthorizedException(detail="登录已过期，请重新登录")
        except (TypeError, ValueError):
            raise UnauthorizedException(detail="登录已过期，请重新登录")

    return Token(
        access_token=create_access_token(data={"sub": str(user.id)}),
        refresh_token=create_refresh_token(data={"sub": str(user.id)}),
    )


@router.post("/logout", response_model=MessageResponse, summary="用户登出")
async def logout():
    return MessageResponse(message="登出成功")


@router.api_route(
    "/forgot-password",
    methods=["POST"],
    status_code=status.HTTP_410_GONE,
    summary="已废弃：找回密码",
)
async def forgot_password_removed():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="邮箱找回密码已下线，请使用手机号短信登录后设置密码")


@router.api_route(
    "/reset-password",
    methods=["POST"],
    status_code=status.HTTP_410_GONE,
    summary="已废弃：重置密码",
)
async def reset_password_removed():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="邮箱重置密码已下线，请使用手机号短信登录后设置密码")
