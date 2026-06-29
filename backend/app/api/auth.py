from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.user import UserRegister, UserLogin, Token, UserResponse, RefreshTokenRequest
from app.schemas.common import MessageResponse
from app.models.user import User
from app.core.exceptions import BadRequestException, UnauthorizedException, ConflictException

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=Token, summary="用户注册")
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise ConflictException(detail="该邮箱已被注册")

    # 创建用户
    password_hash = get_password_hash(data.password)
    user = User(
        email=data.email,
        nickname=data.nickname,
        password_hash=password_hash,
        school_id=data.school_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 生成 token
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_value = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token_value,
    )


@router.post("/login", response_model=Token, summary="用户登录")
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    # 查找用户
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedException(detail="邮箱或密码错误")

    # 验证密码
    if not verify_password(data.password, user.password_hash):
        raise UnauthorizedException(detail="邮箱或密码错误")

    # 检查用户状态
    if not user.is_active or user.is_deleted:
        raise UnauthorizedException(detail="账号已被禁用或删除")

    # 更新最后登录时间
    user.last_login_at = datetime.now()
    await db.commit()

    # 生成 token
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_value = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token_value,
    )


@router.post("/refresh", response_model=Token, summary="刷新 Token")
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    refresh_token_str = data.refresh_token
    if not refresh_token_str:
        raise BadRequestException(detail="缺少 refresh_token")

    # 解析 token
    payload = decode_token(refresh_token_str)
    if payload is None:
        raise UnauthorizedException(detail="无效的 refresh_token")

    # 验证 token 类型
    if payload.get("type") != "refresh":
        raise UnauthorizedException(detail="无效的 token 类型")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedException(detail="无效的 token")

    # 查询用户
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.is_deleted:
        raise UnauthorizedException(detail="用户不存在或已被禁用")

    # 生成新的 token 对
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout", response_model=MessageResponse, summary="用户登出")
async def logout():
    # 前端清除 token，后端可选黑名单
    return MessageResponse(message="登出成功")
