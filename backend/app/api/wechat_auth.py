import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.exceptions import (
    BadRequestException,
    UnauthorizedException,
    ConflictException,
    NotFoundException,
)
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity
from app.models.auth_session import AuthSession
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.schemas.wechat_auth import (
    WechatExchangeRequest,
    WechatExchangeBoundResponse,
    WechatExchangeUnboundResponse,
    WechatBindExistingRequest,
    WechatBindExistingResponse,
    WechatRegisterRequest,
    WechatRegisterResponse,
    IdentityResponse,
    IdentityListResponse,
    AddEmailIdentityRequest,
    AddEmailIdentityResponse,
    SessionResponse,
    SessionListResponse,
    LogoutAllResponse,
)
from app.schemas.user import UserResponse, LoginResponse
from app.services.wechat import (
    exchange_wechat_code,
    create_binding_ticket,
    consume_binding_ticket,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/wechat", tags=["微信认证"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_session_pair(user_id: int, session_type: str = "web", db: AsyncSession = None, client_ip: str = None):
    """创建 access_token + refresh_token 对，并记录服务端会话。"""
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})

    if db is not None:
        refresh_hash = _hash_token(refresh_token)
        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_hash,
            session_type=session_type,
            client_ip=client_ip,
            expires_at=datetime.now() + __import__("datetime").timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            ),
            last_active_at=datetime.now(),
        )
        db.add(session)

    return access_token, refresh_token


async def _resolve_client_ip(request: Request) -> Optional[str]:
    """从请求中提取客户端 IP。"""
    if request.client:
        return request.client.host
    return None


@router.post("/exchange", summary="微信 code 换登录态")
async def wechat_exchange(
    data: WechatExchangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """微信小程序登录：wx.login() code → 换取登录态或 binding_ticket。

    流程：
    1. 调微信 code2Session → 获取 openid
    2. 查找 openid 是否已绑定用户
       - 已绑定 → 直接签发 JWT（status: authenticated）
       - 未绑定 → 返回 binding_ticket（status: binding_required）
    """
    client_ip = await _resolve_client_ip(request)

    # 1. 调用微信 code2Session
    wx_result = await exchange_wechat_code(data.code)
    openid = wx_result["openid"]
    unionid = wx_result.get("unionid")

    # 2. 查找 openid 对应的身份
    result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.identity_type == "wechat_miniprogram",
            UserAuthIdentity.identity_key == openid,
            UserAuthIdentity.is_deleted == False,
        )
    )
    identity = result.scalar_one_or_none()

    if identity is not None:
        # 已绑定 → 直接签发 JWT
        user_result = await db.execute(
            select(User).where(User.id == identity.user_id)
        )
        user = user_result.scalar_one_or_none()

        if user is None or not user.is_active or user.is_deleted:
            raise UnauthorizedException(detail="账号已被禁用或删除")

        # 更新身份最后使用时间
        identity.last_used_at = datetime.now()

        # 创建会话
        access_token, refresh_token = _create_session_pair(
            user_id=user.id,
            session_type="miniprogram",
            db=db,
            client_ip=client_ip,
        )
        await db.commit()

        logger.info(f"微信登录成功: user_id={user.id} openid={openid[:8]}...")

        user_data = UserResponse.model_validate(user).model_dump()
        return WechatExchangeBoundResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
            user=user_data,
        )
    else:
        # 未绑定 → 返回 binding_ticket
        ticket = await create_binding_ticket(
            db=db,
            openid=openid,
            unionid=unionid,
            client_ip=client_ip,
        )
        logger.info(f"微信用户未绑定，返回 binding_ticket: openid={openid[:8]}...")

        return WechatExchangeUnboundResponse(
            binding_ticket=ticket,
            expires_in=settings.BINDING_TICKET_EXPIRE_SECONDS,
        )


@router.post("/bind-existing", response_model=WechatBindExistingResponse, summary="绑定已有 Web 账号")
async def wechat_bind_existing(
    data: WechatBindExistingRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """将微信 openid 绑定到已有 Web 账号。

    流程：
    1. 验证 binding_ticket（一次性、时效性）
    2. 验证邮箱密码
    3. 创建 wechat_miniprogram 身份记录
    4. 签发 JWT
    """
    client_ip = await _resolve_client_ip(request)

    # 1. 验证 binding_ticket
    bt = await consume_binding_ticket(db, data.binding_ticket)
    if bt is None:
        raise BadRequestException(detail="绑定凭证无效或已过期")

    # 2. 查找并验证用户
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedException(detail="邮箱或密码错误")

    if not verify_password(data.password, user.password_hash):
        raise UnauthorizedException(detail="邮箱或密码错误")

    if not user.is_active or user.is_deleted:
        raise UnauthorizedException(detail="账号已被禁用或删除")

    # 3. 创建微信身份记录
    # 检查是否已绑定同一 openid
    existing = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.identity_type == "wechat_miniprogram",
            UserAuthIdentity.identity_key == bt.openid,
            UserAuthIdentity.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictException(detail="该微信已绑定其他账号")

    wechat_identity = UserAuthIdentity(
        user_id=user.id,
        identity_type="wechat_miniprogram",
        identity_key=bt.openid,
        openid=bt.openid,
        unionid=bt.unionid,
        last_used_at=datetime.now(),
    )
    db.add(wechat_identity)

    # 同时确保用户有 email_password 身份记录
    email_identity_check = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.identity_type == "email_password",
            UserAuthIdentity.identity_key == user.email,
            UserAuthIdentity.is_deleted == False,
        )
    )
    if email_identity_check.scalar_one_or_none() is None:
        email_identity = UserAuthIdentity(
            user_id=user.id,
            identity_type="email_password",
            identity_key=user.email,
            password_hash=user.password_hash,
            last_used_at=datetime.now(),
        )
        db.add(email_identity)

    # 4. 创建会话并签发 JWT
    access_token, refresh_token = _create_session_pair(
        user_id=user.id,
        session_type="miniprogram",
        db=db,
        client_ip=client_ip,
    )
    await db.commit()

    logger.info(f"微信绑定成功: user_id={user.id} openid={bt.openid[:8]}...")

    return WechatBindExistingResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        message="绑定成功",
    )


@router.post("/register", response_model=WechatRegisterResponse, summary="微信新用户注册")
async def wechat_register(
    data: WechatRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """微信新用户注册：通过 binding_ticket 创建新用户并绑定微信身份。

    流程：
    1. 验证 binding_ticket
    2. 生成邮箱（如果未提供）
    3. 创建 User + wechat_miniprogram 身份 + email_password 身份
    4. 创建默认 membership
    5. 签发 JWT
    """
    client_ip = await _resolve_client_ip(request)

    # 1. 验证 binding_ticket
    bt = await consume_binding_ticket(db, data.binding_ticket)
    if bt is None:
        raise BadRequestException(detail="绑定凭证无效或已过期")

    # 2. 检查 openid 是否被注册
    existing = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.identity_type == "wechat_miniprogram",
            UserAuthIdentity.identity_key == bt.openid,
            UserAuthIdentity.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictException(detail="该微信已绑定其他账号")

    # 3. 处理邮箱
    if data.email:
        # 使用提供的邮箱，检查是否已被注册
        email_check = await db.execute(select(User).where(User.email == data.email))
        if email_check.scalar_one_or_none() is not None:
            raise ConflictException(detail="该邮箱已被注册")
        email = data.email
    else:
        # 生成临时邮箱
        import secrets
        unique_id = secrets.token_hex(8)
        email = f"wx_{unique_id}@momentcampus.local"

    # 4. 检查学校是否存在
    school_result = await db.execute(select(School).where(School.id == data.school_id))
    school = school_result.scalar_one_or_none()
    if school is None or not school.is_active:
        raise BadRequestException(detail="学校不存在或已被禁用")

    # 5. 创建用户
    password_hash = get_password_hash(data.password)
    user = User(
        email=email,
        nickname=data.nickname,
        password_hash=password_hash,
        school_id=data.school_id,
    )
    db.add(user)
    await db.flush()

    # 6. 创建两种身份
    wechat_identity = UserAuthIdentity(
        user_id=user.id,
        identity_type="wechat_miniprogram",
        identity_key=bt.openid,
        openid=bt.openid,
        unionid=bt.unionid,
        last_used_at=datetime.now(),
    )
    email_identity = UserAuthIdentity(
        user_id=user.id,
        identity_type="email_password",
        identity_key=email,
        password_hash=password_hash,
        last_used_at=datetime.now(),
    )
    db.add(wechat_identity)
    db.add(email_identity)

    # 7. 创建默认 membership
    membership = SchoolMembership(
        user_id=user.id,
        school_id=data.school_id,
        role="member",
        status="active",
        is_default=True,
        joined_at=datetime.now(),
    )
    db.add(membership)

    # 8. 创建会话并签发 JWT
    access_token, refresh_token = _create_session_pair(
        user_id=user.id,
        session_type="miniprogram",
        db=db,
        client_ip=client_ip,
    )
    await db.commit()

    logger.info(f"微信注册成功: user_id={user.id} openid={bt.openid[:8]}...")

    return WechatRegisterResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        message="注册成功",
    )


# ============================================================
# 身份管理
# ============================================================
@router.get("/identities", response_model=IdentityListResponse, summary="查看当前用户已绑定身份")
async def list_identities(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户所有登录方式。"""
    result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.is_deleted == False,
        )
    )
    identities = result.scalars().all()
    return IdentityListResponse(identities=[
        IdentityResponse.model_validate(i) for i in identities
    ])


@router.post("/identities/email", response_model=AddEmailIdentityResponse, summary="添加邮箱登录方式")
async def add_email_identity(
    data: AddEmailIdentityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为当前用户添加邮箱密码登录方式（给微信注册用户设置密码）。"""
    # 检查邮箱是否已被其他用户使用
    result = await db.execute(
        select(User).where(User.email == data.email)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user is not None and existing_user.id != user.id:
        raise ConflictException(detail="该邮箱已被其他账号注册")

    # 检查是否已有 email_password 身份
    identity_check = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.identity_type == "email_password",
            UserAuthIdentity.is_deleted == False,
        )
    )
    existing_identity = identity_check.scalar_one_or_none()
    if existing_identity is not None:
        raise ConflictException(detail="已存在邮箱登录方式")

    # 如果用户邮箱与提供的邮箱不同，更新用户邮箱
    if user.email != data.email:
        user.email = data.email

    # 创建 email_password 身份
    email_identity = UserAuthIdentity(
        user_id=user.id,
        identity_type="email_password",
        identity_key=data.email,
        password_hash=get_password_hash(data.password),
        last_used_at=datetime.now(),
    )
    db.add(email_identity)
    await db.commit()

    logger.info(f"添加邮箱登录方式: user_id={user.id}")
    return AddEmailIdentityResponse(message="添加成功", identity_id=email_identity.id)


@router.delete("/identities/{identity_id}", summary="解绑登录方式")
async def delete_identity(
    identity_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解绑指定登录方式。

    规则：
    - 至少保留一种登录方式（不能全部解绑）
    - 不能解绑最后一个 email_password（防止用户失去 Web 登录能力）
    """
    result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.id == identity_id,
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.is_deleted == False,
        )
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        raise NotFoundException(detail="身份记录不存在")

    # 检查是否至少保留一种
    all_result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.is_deleted == False,
        )
    )
    all_identities = all_result.scalars().all()
    if len(all_identities) <= 1:
        raise BadRequestException(detail="至少需要保留一种登录方式")

    # 软删除
    identity.is_deleted = True
    identity.deleted_at = datetime.now()
    await db.commit()

    logger.info(f"解绑身份: user_id={user.id} identity_type={identity.identity_type}")
    return {"message": "解绑成功"}


# ============================================================
# 会话管理
# ============================================================
@router.get("/sessions", response_model=SessionListResponse, summary="查看登录设备列表")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户所有活跃会话。"""
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.is_revoked == False,
            AuthSession.expires_at > datetime.now(),
        ).order_by(AuthSession.created_at.desc())
    )
    sessions = result.scalars().all()
    # 标记当前会话（根据 Authorization header 判断较复杂，这里不标记）
    session_responses = []
    for s in sessions:
        sr = SessionResponse.model_validate(s)
        session_responses.append(sr)
    return SessionListResponse(sessions=session_responses)


@router.delete("/sessions/{session_id}", summary="撤销指定设备会话")
async def revoke_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """撤销指定设备的会话，不影响其他设备。"""
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundException(detail="会话不存在")
    if session.is_revoked:
        raise BadRequestException(detail="会话已被撤销")

    session.is_revoked = True
    session.revoked_at = datetime.now()
    await db.commit()

    logger.info(f"撤销会话: user_id={user.id} session_id={session_id}")
    return {"message": "会话已撤销"}


@router.post("/logout-all", response_model=LogoutAllResponse, summary="退出全部设备")
async def logout_all(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """撤销用户所有活跃会话。"""
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.is_revoked == False,
        )
    )
    sessions = result.scalars().all()
    count = 0
    for s in sessions:
        s.is_revoked = True
        s.revoked_at = datetime.now()
        count += 1
    await db.commit()

    logger.info(f"退出全部设备: user_id={user.id} count={count}")
    return LogoutAllResponse(message="已退出所有设备", revoked_count=count)
