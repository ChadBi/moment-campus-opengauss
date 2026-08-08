from fastapi import APIRouter, Depends, UploadFile, File, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional
from pydantic import BaseModel, Field
import os
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.category import Category
from app.models.location import Location
# PRF-01.3: 浏览历史按学校隔离
from app.models.browse_history import BrowseHistory
# PRF-01.2: 真实统计需要协同验证记录
from app.models.validation_record import ValidationRecord
# B-01: 校园身份认证
from app.models.campus_verify_token import CampusVerifyToken
from app.models.school_domain import SchoolDomain
from app.models.school import School
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.user import (
    CampusVerifySendRequest, CampusVerifySendResponse,
    CampusVerifyConfirmRequest, CampusVerifyConfirmResponse,
)
from app.schemas.post import PostListResponse
from app.schemas.common import MessageResponse, PaginatedResponse
from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException
from app.core.campus import get_registration_school_id, is_registration_school
from app.core.tenant import TenantContext, get_tenant_context
from app.config import settings
# B-01 注册/认证共用的教育邮箱域名校验（含全局测试域 qq.com 放行）
from app.services.school_domain import ensure_email_matches_school_domains

router = APIRouter(prefix="/users", tags=["用户"])

# B-01: 校园身份认证验证码有效期（分钟）
CAMPUS_VERIFY_CODE_EXPIRE_MINUTES = 10


def _should_return_campus_verify_code() -> bool:
    """本地开发环境在响应中返回 6 位验证码（无邮件服务），便于测试与演示闭环。"""
    env = (settings.APP_ENV or "").lower()
    return env in ("opengauss", "demo", "test") or settings.DEBUG


def _hash_token(token: str) -> str:
    """对明文凭证（验证码/token）取 SHA-256 哈希；DB 仅存哈希，避免明文泄露。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_verification_code() -> str:
    """生成一次性 6 位数字验证码。"""
    return f"{secrets.randbelow(1_000_000):06d}"


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.put("/me", response_model=UserResponse, summary="更新用户信息")
async def update_user_info(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 更新用户信息
    if data.nickname is not None:
        current_user.nickname = data.nickname
    if data.bio is not None:
        current_user.bio = data.bio
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url

    current_user.updated_at = datetime.now()
    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.put("/me/onboarding", response_model=UserResponse, summary="ACC-01.4: 标记完成首次使用引导")
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记当前用户已完成首次使用引导。

    前端 FirstUseGuide 完成/跳过时调用，将 onboarding_completed 设为 True。
    后续登录不再弹出教程（即使换浏览器/清缓存）。
    """
    current_user.onboarding_completed = True
    current_user.updated_at = datetime.now()
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post(
    "/me/verify-campus/send",
    response_model=CampusVerifySendResponse,
    summary="B-01: 发起校园身份认证（使用登录邮箱发码）",
)
async def send_campus_verify(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """发起校园身份认证（统一教育邮箱）。

    业务规则：
    - 已认证用户不能再发起（返回 400）
    - 域名校验与注册阶段保持完全一致：调用 ensure_email_matches_school_domains，
      因而运营豁免域（momentcampus.com）+ 全局测试邮箱域（qq.com 等）+ 学校
      允许域均放行；qq.com 用户和教育邮箱用户走相同流程，无需额外输入框
    - 生成一次性 6 位数字验证码（10 分钟有效），DB 仅存 SHA-256 哈希
    - 通过 SMTP 发送只包含验证码的验证邮件
    - SMTP 未配置或本地开发环境（APP_ENV in opengauss/demo/test 或 DEBUG=true）：
      响应中携带 code 供测试链路打通（无邮件服务）
    """
    registration_school_id = get_registration_school_id(current_user)
    if current_user.role != "super_admin" and not is_registration_school(current_user, tenant.school_id):
        raise ForbiddenException(detail="校园身份认证仅适用于注册时选择的学校")

    if current_user.campus_verified:
        raise BadRequestException(detail="您已完成校园身份认证，无需重复认证")

    # 注册/认证共用域名校验——qq.com（全局测试域）/ momentcampus.com / 学校允许域均放行
    await ensure_email_matches_school_domains(
        db, registration_school_id, current_user.email, require_email=True
    )

    # 生成一次性 6 位验证码
    code = _generate_verification_code()
    token_hash = _hash_token(code)
    expires_at = datetime.now() + timedelta(minutes=CAMPUS_VERIFY_CODE_EXPIRE_MINUTES)

    client_ip = request.client.host if request.client else None
    db.add(CampusVerifyToken(
        user_id=current_user.id,
        school_id=registration_school_id,
        target_email=current_user.email,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=None,
        created_at=datetime.now(),
        ip_address=client_ip,
    ))
    await db.commit()

    # 尝试通过 SMTP 发送验证邮件；失败/未配置时回退 dev 展示
    from app.services import email_service
    school_row = await db.scalar(
        select(School.name).where(School.id == registration_school_id)
    )
    school_name = school_row or ""
    sent = email_service.send_verification_email(
        to_email=current_user.email,
        school_name=school_name,
        code=code,
    )
    if sent:
        message = (
            f"6 位验证码已发送至 {current_user.email}，请查收邮件并在页面输入"
            f"（{CAMPUS_VERIFY_CODE_EXPIRE_MINUTES} 分钟内有效）"
        )
    else:
        message = (
            f"6 位验证码已生成（{CAMPUS_VERIFY_CODE_EXPIRE_MINUTES} 分钟内有效）；"
            f"当前环境未配置邮件服务，请使用页面显示的验证码完成认证"
        )

    if _should_return_campus_verify_code() or not email_service.smtp_configured():
        return CampusVerifySendResponse(
            message=message,
            code=code,
        )
    return CampusVerifySendResponse(message=message)


@router.post(
    "/me/verify-campus/confirm",
    response_model=CampusVerifyConfirmResponse,
    summary="B-01: 确认校园身份认证（提交 6 位验证码）",
)
async def confirm_campus_verify(
    data: CampusVerifyConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """确认校园身份认证（统一教育邮箱）。

    业务规则：
    - 校验 6 位数字验证码：哈希后查 DB，必须存在 + 未过期 + 未使用 + 属于当前用户
    - 校验通过 → campus_verified=true，记录 campus_verified_at
    - 一次性：标记 used_at = now，防止重复使用
    """
    registration_school_id = get_registration_school_id(current_user)
    if current_user.role != "super_admin" and not is_registration_school(current_user, tenant.school_id):
        raise ForbiddenException(detail="校园身份认证仅适用于注册时选择的学校")

    if current_user.campus_verified:
        raise BadRequestException(detail="您已完成校园身份认证，无需重复认证")

    if not data.code:
        raise BadRequestException(detail="请提供 6 位数字验证码")

    token_hash = _hash_token(data.code)
    result = await db.execute(
        select(CampusVerifyToken).where(
            CampusVerifyToken.user_id == current_user.id,
            CampusVerifyToken.school_id == registration_school_id,
            CampusVerifyToken.token_hash == token_hash,
        ).order_by(CampusVerifyToken.created_at.desc())
    )
    token = result.scalars().first()
    if token is None:
        raise BadRequestException(detail="验证凭证无效，请重新发起认证")
    if token.used_at is not None:
        raise BadRequestException(detail="验证凭证已使用，请重新发起认证")
    if token.expires_at < datetime.now():
        raise BadRequestException(detail="验证凭证已过期，请重新发起认证")

    # 标记使用 + 记录认证信息
    token.used_at = datetime.now()
    current_user.campus_verified = True
    current_user.campus_verified_at = datetime.now()
    current_user.updated_at = datetime.now()
    await db.commit()
    await db.refresh(current_user)

    return CampusVerifyConfirmResponse(message="校园身份认证成功", campus_verified=True)


@router.post("/me/avatar", response_model=MessageResponse, summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证文件格式
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise BadRequestException(detail="不支持的图片格式，仅支持 JPG、PNG、GIF、WEBP")

    # 验证文件大小
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise BadRequestException(detail=f"图片大小不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 生成唯一文件名
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{file_extension}"

    # 确保上传目录存在
    upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    # 保存文件
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # 生成访问 URL
    avatar_url = f"/uploads/avatars/{filename}"

    # 更新用户头像
    current_user.avatar_url = avatar_url
    current_user.updated_at = datetime.now()
    await db.commit()

    return MessageResponse(
        message="头像上传成功",
        data={"avatar_url": avatar_url}
    )


@router.get("/me/posts", response_model=PaginatedResponse[PostListResponse], summary="获取我的信息列表")
async def get_my_posts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = Query(
        default=None,
        pattern="^(draft|pending|published|expired|conflict|archived)$",
        description="PUB-02: 按状态筛选（draft/pending/published/expired/conflict/archived），不传返回全部",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取我的信息列表

    PUB-02：支持按状态筛选（草稿/待审核/已发布/已过期/冲突中/已归档），
    用于"我的发布"按状态分组分页展示。
    TEN-02.3：按当前学校过滤，跨校帖子不会出现在我的列表中。
    """
    # 查询我的帖子（未删除），预加载关联数据（TEN-02.3: 强制按当前学校过滤）
    base_filter = [
        Post.user_id == current_user.id,
        Post.is_deleted == False,
        Post.school_id == tenant.school_id,
    ]
    if status is not None:
        base_filter.append(Post.status == status)

    query = select(Post).options(
        selectinload(Post.user),
        selectinload(Post.category),
        selectinload(Post.location),
    ).where(
        *base_filter,
    ).order_by(Post.created_at.desc())

    # 获取总数
    count_query = select(func.count()).select_from(Post).where(*base_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    posts_result = await db.execute(query.offset(offset).limit(page_size))
    posts = posts_result.scalars().all()

    return PaginatedResponse.create(
        items=posts,
        page=page,
        page_size=page_size,
        total=total
    )


# ============================================================
# PRF-01.2: /users/me/stats 真实统计接口
# ============================================================
class UserStatsResponse(BaseModel):
    """个人中心真实统计（按当前学校过滤）"""
    school_id: int = Field(..., description="当前学校 ID")
    published_count: int = Field(0, description="已发布数量")
    draft_count: int = Field(0, description="草稿数量")
    pending_count: int = Field(0, description="待审核数量")
    expired_count: int = Field(0, description="已过期数量")
    conflict_count: int = Field(0, description="冲突中数量")
    archived_count: int = Field(0, description="已归档数量")
    total_count: int = Field(0, description="全部帖子数量")
    # PRF-01.2: 贡献验证 = 当前用户在该校发布的已发布帖子收到的确认有效票数
    # （confirmation 类型 ValidationRecord 计数）
    confirmation_count: int = Field(0, description="贡献验证：已发布帖子收到的确认有效票数")


@router.get("/me/stats", response_model=UserStatsResponse, summary="我的真实统计（按当前学校过滤）")
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取当前用户在当前学校的真实统计

    PRF-01.2：替代前端用 6 次拉取计数拼凑的方式，一次性返回真实统计：
        - published_count / draft_count / pending_count / expired_count /
          conflict_count / archived_count / total_count：按状态分组的帖子数
        - confirmation_count：贡献验证 = 当前用户在该校已发布帖子收到的
          confirmation 类型协同验证票数（不含 refutation）

    TEN-02.3：所有计数均按 tenant.school_id 过滤，跨校帖子/验证不计入。
    """
    # 1. 按状态分组统计当前用户在该校的帖子数
    status_count_rows = (
        await db.execute(
            select(Post.status, func.count(Post.id))
            .where(
                Post.user_id == current_user.id,
                Post.is_deleted == False,
                Post.school_id == tenant.school_id,
            )
            .group_by(Post.status)
        )
    ).all()
    status_map = {row[0]: row[1] for row in status_count_rows}

    # 2. 贡献验证：当前用户在该校已发布帖子收到的 confirmation 票数
    # join posts 过滤作者 + 学校 + 状态，再 join validation_records 计票
    confirmation_count = (
        await db.execute(
            select(func.count(ValidationRecord.id))
            .select_from(ValidationRecord)
            .join(Post, Post.id == ValidationRecord.post_id)
            .where(
                Post.user_id == current_user.id,
                Post.school_id == tenant.school_id,
                Post.is_deleted == False,
                Post.status == "published",
                ValidationRecord.validation_type == "confirmation",
            )
        )
    ).scalar() or 0

    return UserStatsResponse(
        school_id=tenant.school_id,
        published_count=status_map.get("published", 0),
        draft_count=status_map.get("draft", 0),
        pending_count=status_map.get("pending", 0),
        expired_count=status_map.get("expired", 0),
        conflict_count=status_map.get("conflict", 0),
        archived_count=status_map.get("archived", 0),
        total_count=sum(status_map.values()),
        confirmation_count=confirmation_count,
    )


# ============================================================
# PRF-01.3: /users/me/view-history 浏览历史（按当前学校过滤）
# ============================================================
class ViewHistoryItem(BaseModel):
    """浏览历史项"""
    id: int
    post_id: int
    title: str
    status: str
    cover_image: Optional[str] = None
    category_name: Optional[str] = None
    location_name: Optional[str] = None
    viewed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get(
    "/me/view-history",
    response_model=PaginatedResponse[ViewHistoryItem],
    summary="我的浏览历史（按当前学校过滤）",
)
async def get_my_view_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取当前用户在当前学校的浏览历史

    PRF-01.3：按 tenant.school_id 过滤，跨校浏览历史不会出现在当前学校下。
    同一帖子只保留最近一条浏览记录（由 BrowseHistory 唯一约束保证）。
    按 viewed_at DESC 排序。
    软删除的帖子不在浏览历史中展示（避免泄露存在性）。
    """
    try:
        base_filter = [
            BrowseHistory.user_id == current_user.id,
            BrowseHistory.school_id == tenant.school_id,
            Post.is_deleted == False,
        ]

        # 总数
        count_query = (
            select(func.count())
            .select_from(BrowseHistory)
            .join(Post, Post.id == BrowseHistory.post_id)
            .where(*base_filter)
        )
        total = (await db.execute(count_query)).scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = (
            select(BrowseHistory)
            .join(Post, Post.id == BrowseHistory.post_id)
            .options(
                joinedload(BrowseHistory.post).joinedload(Post.category),
                joinedload(BrowseHistory.post).joinedload(Post.location),
            )
            .where(*base_filter)
            .order_by(BrowseHistory.viewed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(query)
        histories = result.unique().scalars().all()

        items: list[ViewHistoryItem] = []
        for h in histories:
            post = h.post
            items.append(
                ViewHistoryItem(
                    id=h.id,
                    post_id=h.post_id,
                    title=post.title if post else "",
                    status=post.status if post else "",
                    category_name=post.category.name if post and post.category else None,
                    location_name=post.location.name if post and post.location else None,
                    viewed_at=h.viewed_at,
                    created_at=h.created_at,
                )
            )

        return PaginatedResponse.create(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
        )
    except Exception as e:
        # 添加日志记录，但返回空列表而不是 500 错误
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to get view history for user {current_user.id}: {str(e)}")
        
        # 返回空列表而不是 500 错误
        return PaginatedResponse.create(
            items=[],
            page=page,
            page_size=page_size,
            total=0,
        )


@router.delete(
    "/me/view-history",
    response_model=MessageResponse,
    summary="清除当前学校下的全部浏览历史",
)
async def clear_my_view_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """清除当前用户在当前学校的全部浏览历史

    PRF-01.3：仅清除当前学校下的记录，其它学校的历史保留。
    """
    result = await db.execute(
        delete(BrowseHistory).where(
            BrowseHistory.user_id == current_user.id,
            BrowseHistory.school_id == tenant.school_id,
        )
    )
    deleted_count = result.rowcount or 0
    await db.commit()
    return MessageResponse(
        message=f"已清除 {deleted_count} 条浏览历史",
        data={"deleted_count": deleted_count, "school_id": tenant.school_id},
    )


@router.delete(
    "/me/view-history/{post_id}",
    response_model=MessageResponse,
    summary="删除单条浏览历史",
)
async def delete_view_history_item(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """删除当前用户在当前学校下对指定帖子的浏览历史

    PRF-01.3：跨校访问其它学校的历史 → 404（不泄露存在性）。
    """
    result = await db.execute(
        delete(BrowseHistory).where(
            BrowseHistory.user_id == current_user.id,
            BrowseHistory.school_id == tenant.school_id,
            BrowseHistory.post_id == post_id,
        )
    )
    if (result.rowcount or 0) == 0:
        raise NotFoundException(detail="浏览历史不存在")
    await db.commit()
    return MessageResponse(message="已删除该条浏览历史")
