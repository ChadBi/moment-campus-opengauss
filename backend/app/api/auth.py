import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.user import (
    UserRegister,
    UserLogin,
    Token,
    UserResponse,
    RefreshTokenRequest,
    LoginResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.schemas.common import MessageResponse
from app.models.user import User
from app.models.school import School
from app.models.school_invitation import SchoolInvitation
from app.models.school_membership import SchoolMembership
from app.models.password_reset_token import PasswordResetToken
from app.core.exceptions import (
    BadRequestException,
    UnauthorizedException,
    ConflictException,
    NotFoundException,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

# ACC-01.3: 找回密码 Token 配置
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30
# 本地开发环境下，无邮件服务，将 Token 通过响应返回供测试链路打通。
# 判定条件：APP_ENV != production 且 DEBUG=true，或显式配置 LOCAL_DEV_RETURN_RESET_TOKEN。
def _should_return_reset_token_in_response() -> bool:
    env = (settings.APP_ENV or "").lower()
    return env in ("opengauss", "demo", "test") or settings.DEBUG


async def _resolve_school_id_from_header(
    db: AsyncSession,
    x_school_code: Optional[str],
) -> Optional[int]:
    """ACC-01.2: 从 X-School-Code 头解析 school_id。

    TEN-02: 写请求忽略 body 里的 school_id，强制使用上下文解析得到的 school_id。
    本函数不抛异常：若未提供 header 或学校不存在，返回 None（由调用方决定回退策略）。
    """
    if not x_school_code:
        return None
    code = x_school_code.strip()
    if not code:
        return None
    result = await db.execute(select(School).where(School.code == code))
    school = result.scalar_one_or_none()
    if school is None or not school.is_active:
        return None
    return school.id


@router.post("/register", response_model=LoginResponse, summary="用户注册")
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
    x_school_code: Optional[str] = Header(default=None, alias="X-School-Code"),
):
    """用户注册。

    ACC-01.2: 取消固定 school_id。
    - 优先使用 X-School-Code 头解析的 school_id（TEN-02: 写请求忽略 body 里的 school_id）
    - 未提供 X-School-Code 时回退到 body.school_id（兼容现有测试与未注入拦截器的调用方）
    - 两者都未提供时返回 400（防止创建无学校用户）

    ACC-01.2: 邀请码消费闭环
    - 若 body.invite_code 提供：先校验有效性（存在/未过期/未使用/邮箱匹配/学校匹配），
      注册成功后标记 invitation.status='accepted' / accepted_at / used_by，
      并为该用户在该学校创建 active membership（is_default=True，新用户首校默认）。
    - 若 invite_code 无效：返回 400，不创建用户。
    - 若 invite_code 缺省：仅创建用户，不创建 membership（保持原行为）。
    """
    # ACC-01.2: 从 X-School-Code 解析 school_id（优先），否则回退到 body
    school_id = await _resolve_school_id_from_header(db, x_school_code)
    if school_id is None:
        school_id = data.school_id

    if school_id is None:
        raise BadRequestException(
            detail="无法确定注册学校，请通过 X-School-Code 头或 school_id 字段提供"
        )

    # ACC-01.2: 邀请码预校验（注册前校验，避免无效邀请码导致脏用户）
    invitation: Optional[SchoolInvitation] = None
    if data.invite_code:
        invitation = await _validate_invitation_for_register(
            db=db,
            invite_code=data.invite_code,
            school_id=school_id,
            email=data.email,
        )

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
        school_id=school_id,
    )
    db.add(user)
    await db.flush()

    # ACC-01.2: 消费邀请码 + 创建 active membership
    if invitation is not None:
        now = datetime.now()
        invitation.status = "accepted"
        invitation.accepted_at = now
        invitation.used_by = user.id

        # 邀请码指定角色：admin 邀请 → admin 角色；否则 member
        membership_role = "admin" if invitation.role == "admin" else "member"
        membership = SchoolMembership(
            user_id=user.id,
            school_id=school_id,
            role=membership_role,
            status="active",
            is_default=True,  # 新用户首校默认
            joined_at=now,
            invited_by=invitation.invited_by,
        )
        db.add(membership)
        logger.info(
            "ACC-01.2 register: invite_code consumed user_id=%s school_id=%s role=%s",
            user.id, school_id, membership_role,
        )

    await db.commit()
    await db.refresh(user)

    # 生成 token
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_value = create_refresh_token(data={"sub": str(user.id)})

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        user=UserResponse.model_validate(user),
    )


async def _validate_invitation_for_register(
    db: AsyncSession,
    invite_code: str,
    school_id: int,
    email: str,
) -> SchoolInvitation:
    """ACC-01.2: 注册时校验邀请码有效性。

    校验项：
    1. 存在：邀请码必须存在于 school_invitations 表
    2. 学校匹配：invitation.school_id == 入参 school_id
    3. 邮箱匹配：invitation.email == 入参 email
    4. 未过期：invitation.expires_at 为 NULL 或 > now
    5. 未使用：invitation.status != 'accepted'

    任一项失败均抛 BadRequestException（统一安全失败提示，不区分具体原因）。
    """
    result = await db.execute(
        select(SchoolInvitation).where(
            SchoolInvitation.invitation_code == invite_code,
        )
    )
    invitation = result.scalar_one_or_none()

    # 统一安全失败提示（不区分 邀请码不存在/学校不匹配/邮箱不匹配/已过期/已使用）
    invalid_msg = "邀请码无效或已过期"

    if invitation is None:
        raise BadRequestException(detail=invalid_msg)

    if invitation.school_id != school_id:
        raise BadRequestException(detail=invalid_msg)

    if invitation.email and invitation.email != email:
        raise BadRequestException(detail=invalid_msg)

    if invitation.expires_at is not None and datetime.now() > invitation.expires_at:
        raise BadRequestException(detail=invalid_msg)

    if invitation.status == "accepted":
        raise BadRequestException(detail=invalid_msg)

    return invitation


@router.post("/login", response_model=LoginResponse, summary="用户登录")
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

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        user=UserResponse.model_validate(user),
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

    # ACC-01.3: 校验 token 是否在密码重置之前签发
    # refresh_tokens_invalid_before 为 NULL 时不限制（兼容历史用户与历史 token）
    if user.refresh_tokens_invalid_before is not None:
        iat = payload.get("iat")
        if iat is None:
            # 旧 token 没有 iat 字段，视为不安全，拒绝刷新
            raise UnauthorizedException(detail="登录已过期，请重新登录")
        # iat 与 invalid_before 都用 float timestamp（带微秒精度）比较
        try:
            iat_ts = float(iat)
        except (TypeError, ValueError):
            raise UnauthorizedException(detail="登录已过期，请重新登录")
        invalid_before_ts = user.refresh_tokens_invalid_before.timestamp()
        if iat_ts < invalid_before_ts:
            raise UnauthorizedException(detail="登录已过期，请重新登录")

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


# ============================================================
# ACC-01.3: 找回密码闭环
# ============================================================
def _hash_token(token: str) -> str:
    """对明文 token 取 SHA-256 哈希；DB 仅存哈希，避免明文泄露。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_reset_token() -> str:
    """生成 URL 安全的随机 Token（32 字节 = 43 字符 base64url）。"""
    return secrets.token_urlsafe(32)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="发起找回密码",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """发起找回密码。

    业务规则：
    - 无论邮箱是否存在，都返回相同 message，避免泄露账号存在性
    - 邮箱存在：生成限时（30 分钟）单次 Token，存哈希到 password_reset_tokens 表
    - 本地开发环境（APP_ENV in opengauss/demo/test 或 DEBUG=true）：
      响应中携带 reset_token 供测试链路打通（无邮件服务）
    - 生产环境：仅返回 message，Token 通过邮件发送（未实现邮件服务时记日志）

    Token 安全：
    - DB 仅存 SHA-256 哈希，不存明文
    - 同一邮箱多次申请：旧 Token 不主动失效（自然过期 30 分钟），但使用任一 Token 重置后
      user.refresh_tokens_invalid_before = now，使旧 refresh token 全部失效
    """
    # 查询用户（不抛异常，不泄露账号存在性）
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    reset_token_value: Optional[str] = None
    if user is not None and user.is_active and not user.is_deleted:
        # 生成 Token
        reset_token_value = _generate_reset_token()
        token_hash = _hash_token(reset_token_value)
        expires_at = datetime.now() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

        # 提取客户端 IP（审计用）
        client_ip = None
        if request.client:
            client_ip = request.client.host

        prt = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
            created_at=datetime.now(),
            ip_address=client_ip,
        )
        db.add(prt)
        await db.commit()

        # 本地开发：日志输出 Token 便于调试
        logger.info(
            "ACC-01.3 forgot-password: user_id=%s email=%s token=%s expires_at=%s",
            user.id, user.email, reset_token_value, expires_at,
        )

    # 统一返回 message（不泄露账号存在性）
    message = "如该邮箱已注册，重置链接已发送（30 分钟内有效）"

    # 本地开发环境：在响应中返回 Token 供测试
    if _should_return_reset_token_in_response() and reset_token_value:
        return ForgotPasswordResponse(message=message, reset_token=reset_token_value)

    return ForgotPasswordResponse(message=message)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="重置密码",
)
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """重置密码。

    业务规则：
    - 校验 token：哈希后查 DB，必须存在 + 未过期 + 未使用
    - 设新密码（bcrypt 重新哈希）
    - 失效旧刷新令牌：user.refresh_tokens_invalid_before = now
    - 标记 token 已使用（used_at = now），防止重复使用
    - 跨账号场景：token 与 user 强绑定（user_id），不会跨账号生效

    安全失败：Token 过期 / 已使用 / 不存在 统一返回相同提示，不泄露细节
    """
    token_hash = _hash_token(data.token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    )
    prt = result.scalar_one_or_none()

    # 统一安全失败提示（不区分 token 不存在 / 已使用 / 已过期）
    invalid_msg = "重置链接无效或已过期，请重新申请"

    if prt is None:
        raise BadRequestException(detail=invalid_msg)

    if prt.used_at is not None:
        # 已使用：拒绝（防止重复使用）
        raise BadRequestException(detail=invalid_msg)

    if datetime.now() > prt.expires_at:
        # 已过期：拒绝
        raise BadRequestException(detail=invalid_msg)

    # 查找用户
    user_result = await db.execute(select(User).where(User.id == prt.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active or user.is_deleted:
        # 用户已删除/禁用：仍返回 invalid_msg（不泄露账号状态）
        raise BadRequestException(detail=invalid_msg)

    # 设新密码
    user.password_hash = get_password_hash(data.new_password)
    user.updated_at = datetime.now()

    # ACC-01.3: 失效旧刷新令牌
    # 所有 iat < now 的 refresh token 在 refresh 端点都会被拒绝。
    # JWT iat 是 float timestamp（带微秒），此处 invalid_before 也保留微秒精度，
    # 确保同秒内 reset + 新 token 签发能正确区分（新 token iat > reset 时刻）。
    user.refresh_tokens_invalid_before = datetime.utcnow()

    # 标记 token 已使用
    prt.used_at = datetime.now()

    await db.commit()

    logger.info(
        "ACC-01.3 reset-password: user_id=%s token_id=%s password changed, "
        "old refresh tokens invalidated",
        user.id, prt.id,
    )

    return ResetPasswordResponse(message="密码已重置，请使用新密码登录")
