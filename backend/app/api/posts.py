from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional, List
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import logging

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.like import Like
from app.models.user import User
from app.models.category import Category
from app.models.location import Location
from app.models.validation_record import ValidationRecord
# PRF-01.3: 浏览历史按学校隔离，详情访问时写入
from app.models.browse_history import BrowseHistory
from app.schemas.post import (
    PostCreate, PostUpdate, PostResponse, PostListResponse,
    PostImageBrief,
    PostTransitionCreate, PostTransitionResponse,
)
from app.schemas.ai import AIPublishSuggestRequest, AIPublishSuggestionResponse
from app.schemas.post import GovernanceSummary
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.post_status import (
    can_transition, normalize_status, get_allowed_transitions, PostStatus,
    is_substantial_change,
)
from app.core.permissions import is_admin
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.services.ai_publish import execute_publish_suggestion
from app.services.embedding_service import generate_post_embedding

router = APIRouter(prefix="/posts", tags=["信息"])

logger = logging.getLogger(__name__)


# ============================================================
# FND-03.1 + TEN-02.3: 帖子可见性策略 + 租户可见性
# ============================================================
# 公开访问（游客/非作者）：
#   - published：可见
#   - expired：默认可见（保留展示，便于历史回溯；如需隐藏由后续配置控制）
#   - draft / pending / archived / conflict：不可见 → 404
# 作者：可看自己所有状态
# 管理员：可看本校所有状态（TEN-02.3：跨校对象 → 404）
_PUBLIC_VISIBLE_STATUSES = {PostStatus.PUBLISHED, PostStatus.EXPIRED}


def can_view_post(post: Post, current_user: User | None) -> bool:
    """集中判断 current_user 是否可查看指定 post（FND-03.1 + TEN-02.3）

    策略：
        1. 已软删除的帖子：任何人都不可见（应在外层先过滤，本函数保守返回 False）
        2. 公开可见状态（published / expired）：任何人都可见
        3. 作者本人：可见自己所有状态
        4. 管理员（admin/super_admin）：可见所有状态
           注：跨校对象的访问由 TenantContext + check_resource_in_tenant 在路由层拦截，
           本函数只负责状态/作者可见性，不再做本校校验（避免双重判断）。

    Args:
        post: 帖子对象
        current_user: 当前用户（None 表示游客）

    Returns:
        True 表示可见
    """
    if post is None or post.is_deleted:
        return False

    if post.status in _PUBLIC_VISIBLE_STATUSES:
        return True

    if current_user is None:
        return False

    # 作者本人可见自己所有状态
    if post.user_id == current_user.id:
        return True

    # 管理员可见所有状态（含 draft/pending/archived/conflict）
    if is_admin(current_user):
        return True

    return False


@router.get("", response_model=PaginatedResponse[PostListResponse], summary="获取信息列表")
async def get_posts(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    category_id: Optional[int] = Query(default=None, description="分类ID"),
    location_id: Optional[int] = Query(default=None, description="地点ID"),
    status: Optional[str] = Query(
        default=None,
        pattern="^(published|expired|valid)$",
        description="有效状态筛选：published（仅已发布）/ expired（仅已过期）/ valid（两者皆显示，默认）",
    ),
    date_from: Optional[datetime] = Query(default=None, description="起始时间（created_at >=）"),
    date_to: Optional[datetime] = Query(default=None, description="截止时间（created_at <=）"),
    sort: str = Query(
        default="latest",
        pattern="^(latest|hottest|nearest|active)$",
        description="排序方式: latest（最新）/ hottest（最热）/ nearest（最近活动）/ active（综合活动）",
    ),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取信息列表，支持分页、筛选和排序

    DSC-01.1: 普通搜索/列表支持分类/地点/有效状态/时间/排序。
    TEN-02.3：按当前学校过滤，跨校帖子不会出现在列表中。

    Task 1.2 调整：移除 post_type_id 筛选（PostType 已删除，统一使用 category）

    有效状态筛选：
        - published: 仅显示已发布（status=published）
        - expired: 仅显示已过期（status=expired，仍可对外展示便于历史回溯）
        - valid 或不传：显示 published + expired（默认对外可见集合）
    """
    # 基础查询：当前学校 + 未删除 + 对外可见状态（published + expired）
    # DSC-01.1: status 参数决定具体可见集合
    if status == "published":
        visible_statuses = ["published"]
    elif status == "expired":
        visible_statuses = ["expired"]
    else:
        # valid 或默认：published + expired
        visible_statuses = ["published", "expired"]

    query = select(Post).where(
        Post.is_deleted == False,
        Post.status.in_(visible_statuses),
        Post.school_id == tenant.school_id,
    )

    # 筛选
    if category_id is not None:
        query = query.where(Post.category_id == category_id)
    if location_id is not None:
        query = query.where(Post.location_id == location_id)
    if date_from is not None:
        query = query.where(Post.created_at >= date_from)
    if date_to is not None:
        query = query.where(Post.created_at <= date_to)

    # 排序
    if sort == "latest":
        query = query.order_by(Post.created_at.desc())
    elif sort == "hottest":
        query = query.order_by(Post.like_count.desc(), Post.created_at.desc())
    elif sort == "active":
        # DSC-01.1: 最近活动 = 评论+点赞+浏览综合活跃度，按 updated_at 优先
        query = query.order_by(Post.updated_at.desc(), Post.created_at.desc())
    elif sort == "nearest":
        # DSC-01.1: nearest 简化为按 updated_at 排序（真正地理距离排序需 location_id 参数走专用端点）
        query = query.order_by(Post.updated_at.desc())
    else:
        query = query.order_by(Post.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 预加载关联数据（DSC-01.2: 消除 N+1）
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    posts = result.unique().scalars().all()

    # 转换为响应格式
    items = []
    for post in posts:
        post_data = PostListResponse.model_validate(post)
        # 设置作者信息（is_anonymous 时隐藏真实身份）
        if post.is_anonymous:
            post_data.author = None
        elif post.user:
            post_data.author = {"id": post.user.id, "nickname": post.user.nickname, "avatar_url": post.user.avatar_url, "is_verified": post.user.campus_verified}
        # 设置封面图片
        if post.post_images:
            post_data.cover_image = post.post_images[0].image_url if post.post_images else None
        items.append(post_data)

    return PaginatedResponse.create(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{post_id}", response_model=PostResponse, summary="获取信息详情")
async def get_post(
    post_id: int,
    increment_view: bool = Query(default=True, description="是否增加浏览次数（操作类刷新传 false）"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取信息详情，支持可选增加浏览次数

    FND-03.1 可见性策略（由 can_view_post 集中判断）：
        - 公开访问（游客/非作者）：仅 published / expired 可见
        - 作者：可见自己所有状态
        - 管理员：可见所有状态
        - 草稿/待审/归档/冲突 帖子对无权限用户返回 404（不泄露存在性）

    TEN-02.3：跨校对象统一返回 404（不返回 403 以免泄露存在性）

    increment_view=False 用于点赞/评论/验证等操作后的刷新，避免虚增浏览量。
    """
    # 查询信息（含已软删除，由 can_view_post 统一判断）
    query = select(Post).where(Post.id == post_id)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    post = result.unique().scalar_one_or_none()

    if post is None:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

    # FND-03.1: 可见性校验——不通过则返回 404（不泄露存在性）
    if not can_view_post(post, current_user):
        raise NotFoundException(detail="信息不存在")

    # 增加浏览次数（仅在可见时才计入；操作类刷新传 increment_view=False 以避免虚增）
    if increment_view:
        post.view_count += 1

    # PRF-01.3: 登录用户记录浏览历史（按当前学校隔离）
    # 同一用户在同一学校对同一帖子只保留一条记录，更新 viewed_at
    if current_user is not None and increment_view:
        now_ts = datetime.now()
        existing = (
            await db.execute(
                select(BrowseHistory).where(
                    BrowseHistory.user_id == current_user.id,
                    BrowseHistory.school_id == tenant.school_id,
                    BrowseHistory.post_id == post.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.viewed_at = now_ts
        else:
            db.add(
                BrowseHistory(
                    user_id=current_user.id,
                    school_id=tenant.school_id,
                    post_id=post.id,
                    viewed_at=now_ts,
                    created_at=now_ts,
                )
            )

    await db.commit()
    if increment_view:
        await db.refresh(post, attribute_names=["view_count"])

    # 检查当前用户是否点赞
    is_liked = False
    if current_user:
        like_result = await db.execute(
            select(Like).where(Like.post_id == post_id, Like.user_id == current_user.id)
        )
        is_liked = like_result.scalar_one_or_none() is not None

    # 构建响应
    response = PostResponse.model_validate(post)
    response.is_liked = is_liked

    # DSC-02.1: 游客不返回联系方式（敏感字段按权限脱敏）
    # 游客只能看到公开字段；登录用户（含作者/管理员）可见完整 contact_info
    if tenant.is_guest:
        response.contact_info = None

    # 设置作者信息（匿名时隐藏）
    if post.is_anonymous:
        response.author = None
    elif post.user:
        response.author = {"id": post.user.id, "nickname": post.user.nickname, "avatar_url": post.user.avatar_url, "is_verified": post.user.campus_verified}

    # DSC-02.1: 设置图片列表（按 sort_order 排序，前端轮播依赖）
    # post_images 关系已通过 selectinload 预加载
    if post.post_images:
        response.images = [
            PostImageBrief.model_validate(img)
            for img in sorted(post.post_images, key=lambda i: i.sort_order)
        ]
    else:
        response.images = []

    # 协同验证聚合（两类互斥投票）
    # DSC-02.1: 登录用户额外返回 user_validation_type，游客恒为 None
    response.governance = await _build_governance_summary(db, post_id, current_user)

    return response


async def _build_governance_summary(
    db: AsyncSession,
    post_id: int,
    current_user: Optional[User] = None,
) -> GovernanceSummary:
    """GOV-01.4: 构造帖子详情的协同治理聚合

    调整后：仅保留 2 类互斥投票（confirmation/refutation）
    原 3 类问题报告（update/expiration_report/conflict_report）已移除。

    - DSC-02.1: 登录用户额外返回 user_validation_type；游客恒为 None
    """
    # 投票按类型分组计数
    val_result = await db.execute(
        select(
            ValidationRecord.validation_type,
            func.count(ValidationRecord.id).label("cnt"),
        )
        .where(ValidationRecord.post_id == post_id)
        .group_by(ValidationRecord.validation_type)
    )
    val_counts = {row[0]: row[1] for row in val_result.all()}
    confirmation_count = val_counts.get("confirmation", 0)
    refutation_count = val_counts.get("refutation", 0)
    total_validation_count = confirmation_count + refutation_count
    if confirmation_count > refutation_count:
        validity_status = "valid"
    elif refutation_count > confirmation_count:
        validity_status = "invalid"
    elif total_validation_count > 0:
        validity_status = "uncertain"
    else:
        validity_status = "valid"

    # DSC-02.1: 登录用户返回其投票类型（用于前端高亮"已证实/已证伪"按钮）
    # 游客（current_user is None）恒为 None，前端据此隐藏投票按钮
    user_validation_type = None
    if current_user is not None:
        uvr = await db.execute(
            select(ValidationRecord.validation_type).where(
                ValidationRecord.post_id == post_id,
                ValidationRecord.user_id == current_user.id,
            )
        )
        row = uvr.scalar_one_or_none()
        if row:
            from app.core.validation_type import normalize_validation_type
            user_validation_type = normalize_validation_type(row)

    return GovernanceSummary(
        confirmation_count=confirmation_count,
        refutation_count=refutation_count,
        total_validation_count=total_validation_count,
        validity_status=validity_status,
        user_validation_type=user_validation_type,
    )


@router.post("", response_model=PostResponse, status_code=201, summary="创建信息")
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """创建信息，需要认证

    TEN-02.1: 写请求忽略 body 里的 school_id，强制使用 TenantContext 解析的学校。
    TEN-02.3: 校验 category / location 必须属于当前学校，否则 404。
    """
    # TEN-02.1: 强制使用 tenant.school_id（忽略 body 里的 school_id 字段）
    school_id = tenant.school_id

    # TEN-02.3: 校验分类属于当前学校（跨校分类 → 404，不泄露存在性）
    cat_result = await db.execute(
        select(Category).where(Category.id == post_data.category_id)
    )
    category = cat_result.scalar_one_or_none()
    if category is None:
        raise NotFoundException(detail="分类不存在")
    check_resource_in_tenant(category.school_id, tenant)

    # TEN-02.3: 校验 location_id（若提供）属于当前学校
    location_id = post_data.location_id
    if location_id is not None:
        loc_result = await db.execute(
            select(Location).where(Location.id == location_id, Location.is_deleted == False)
        )
        loc = loc_result.scalar_one_or_none()
        if loc is None:
            raise NotFoundException(detail="地点不存在")
        check_resource_in_tenant(loc.school_id, tenant)
        location_id = loc.id

    # 处理地点：若提供 location_name + lat + lng 则自动创建 Location（自动归入当前学校）
    if location_id is None and post_data.location_name and post_data.location_lat is not None and post_data.location_lng is not None:
        # 在同校同坐标范围内查找是否已有同名地点（避免重复创建）
        existing_loc = await db.execute(
            select(Location).where(
                Location.school_id == school_id,
                Location.name == post_data.location_name,
                Location.latitude == post_data.location_lat,
                Location.longitude == post_data.location_lng,
                Location.is_deleted == False,
            )
        )
        location = existing_loc.scalar_one_or_none()
        if location is None:
            location = Location(
                school_id=school_id,
                name=post_data.location_name,
                latitude=post_data.location_lat,
                longitude=post_data.location_lng,
                is_verified=False,
            )
            db.add(location)
            await db.flush()
        location_id = location.id

    # 创建信息（强制使用 tenant.school_id，不信任 body）
    post = Post(
        user_id=current_user.id,
        school_id=school_id,
        category_id=post_data.category_id,
        location_id=location_id,
        title=post_data.title,
        content=post_data.content,
        is_anonymous=post_data.is_anonymous,
        status=post_data.status or "pending",  # T-B-06: 支持 draft 草稿 / pending 提交审核
        expire_at=post_data.expire_at,
        lost_type=post_data.lost_type,
        contact_info=post_data.contact_info,
        embedding=await generate_post_embedding(post_data.title, post_data.content),
    )

    # 如果没有设置信息截止时间，使用分类的默认信息截止天数
    if post.expire_at is None:
        post.expire_at = datetime.now() + timedelta(days=category.default_validity_days)

    db.add(post)
    await db.flush()  # 获取 post.id

    # 处理图片
    if post_data.image_urls:
        for idx, image_url in enumerate(post_data.image_urls):
            post_image = PostImage(
                post_id=post.id,
                image_url=image_url,
                sort_order=idx,
            )
            db.add(post_image)

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("create_post commit failed: %s", exc)
        raise BadRequestException(detail=f"发布失败，请稍后重试或联系管理员") from exc
    await db.refresh(post)

    # 重新查询以获取关联数据
    query = select(Post).where(Post.id == post.id)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_images),
    )
    result = await db.execute(query)
    post = result.unique().scalar_one()

    response = PostResponse.model_validate(post)
    if post.is_anonymous:
        response.author = None
    elif post.user:
        response.author = {"id": post.user.id, "nickname": post.user.nickname, "avatar_url": post.user.avatar_url, "is_verified": post.user.campus_verified}

    return response


@router.put("/{post_id}", response_model=PostResponse, summary="更新信息")
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新信息，需要认证，验证所有权

    FND-03.2: 状态变化只走状态机服务。
        - 已 published 的帖子若被实质修改（title/content/category_id/
          location_*/lost_type），自动通过状态机 published → pending 回审
        - 非实质字段（expire_at/contact_info/is_anonymous/image_urls）
          修改不触发回审
        - 本接口不允许直接修改 status 字段（PostUpdate schema 已移除 status）

    TEN-02.3: 跨校对象 → 404；category_id 修改时校验新分类属于当前学校。
    """
    # 查询信息
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    post = result.unique().scalar_one_or_none()

    if post is None:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

    # TEN-02.3: 若修改 category_id，校验新分类属于当前学校
    update_data = post_data.model_dump(exclude_unset=True)
    if "category_id" in update_data and update_data["category_id"] is not None:
        cat_result = await db.execute(
            select(Category).where(Category.id == update_data["category_id"])
        )
        new_category = cat_result.scalar_one_or_none()
        if new_category is None:
            raise NotFoundException(detail="分类不存在")
        check_resource_in_tenant(new_category.school_id, tenant)

    # TEN-02.3: 若修改 location_id，校验新地点属于当前学校
    if "location_id" in update_data and update_data["location_id"] is not None:
        loc_result = await db.execute(
            select(Location).where(
                Location.id == update_data["location_id"],
                Location.is_deleted == False,
            )
        )
        new_loc = loc_result.scalar_one_or_none()
        if new_loc is None:
            raise NotFoundException(detail="地点不存在")
        check_resource_in_tenant(new_loc.school_id, tenant)

    # 验证所有权（管理员无权直接修改用户帖子正文，应走审核/状态机流程）
    if post.user_id != current_user.id:
        raise ForbiddenException(detail="没有权限修改此信息")

    # 已归档帖子不可修改（终态）
    if post.status == PostStatus.ARCHIVED:
        raise BadRequestException(detail="已归档的帖子不可修改")

    # update_data 已在前面租户校验阶段计算，此处直接复用
    # 收集实际发生变化的实质字段（用于判断是否触发回审）
    # 注意：location_name/lat/lng 是 PostUpdate 的字段，但 Post 模型上没有这些字段
    # 它们用于"自动创建 Location 并关联 location_id"，等价于修改 location_id，视为实质修改
    changed_substantial_fields: set = set()

    def _record_change(field_name: str, new_value) -> None:
        old_value = getattr(post, field_name, None)
        if old_value != new_value:
            changed_substantial_fields.add(field_name)

    # 处理图片更新（附属数据，不触发回审）
    if "image_urls" in update_data:
        image_urls = update_data.pop("image_urls")
        # 删除旧的图片
        old_images_result = await db.execute(
            select(PostImage).where(PostImage.post_id == post_id)
        )
        old_images = old_images_result.scalars().all()
        for img in old_images:
            await db.delete(img)

        # 添加新的图片
        if image_urls:
            for idx, image_url in enumerate(image_urls):
                post_image = PostImage(
                    post_id=post.id,
                    image_url=image_url,
                    sort_order=idx,
                )
                db.add(post_image)

    # 处理 location_name + lat + lng（自动创建/关联 Location，等价于修改 location_id）
    if "location_name" in update_data or "location_lat" in update_data or "location_lng" in update_data:
        loc_name = update_data.pop("location_name", None)
        loc_lat = update_data.pop("location_lat", None)
        loc_lng = update_data.pop("location_lng", None)
        if loc_name and loc_lat is not None and loc_lng is not None:
            # 同校同坐标范围内查找已有同名地点（TEN-02.1: 使用 tenant.school_id）
            existing_loc = await db.execute(
                select(Location).where(
                    Location.school_id == tenant.school_id,
                    Location.name == loc_name,
                    Location.latitude == loc_lat,
                    Location.longitude == loc_lng,
                    Location.is_deleted == False,
                )
            )
            location = existing_loc.scalar_one_or_none()
            if location is None:
                location = Location(
                    school_id=tenant.school_id,
                    name=loc_name,
                    latitude=loc_lat,
                    longitude=loc_lng,
                    is_verified=False,
                )
                db.add(location)
                await db.flush()
            # 视为修改了 location_id
            update_data["location_id"] = location.id

    # 更新其他字段（含 title/content/category_id/location_id/lost_type 等实质字段）
    for field, value in update_data.items():
        if hasattr(post, field):
            _record_change(field, value)
            setattr(post, field, value)
        else:
            # 未识别字段不视为实质修改
            changed_substantial_fields.discard(field)

    # FND-03.2: 已 published 的帖子若被实质修改，通过状态机走 published → pending 回审
    if post.status == PostStatus.PUBLISHED and is_substantial_change(changed_substantial_fields):
        if not can_transition(PostStatus.PUBLISHED, PostStatus.PENDING):
            raise BadRequestException(detail="状态机不允许 published → pending 流转")
        post.status = PostStatus.PENDING
        post.updated_at = datetime.now()
        # SUB-01.2: 重要更新订阅通知（published → pending 回审时触发，告知订阅者内容在更新中）
        # 与状态变更同事务提交；幂等保证同一订阅者对同一帖子只收到首条更新通知
        from app.services.subscription_notifier import notify_post_updated
        await notify_post_updated(db, post, actor_id=current_user.id)

    # T7: 仅正文语义变化时刷新向量；外部服务失败返回 None，不阻断更新。
    if {"title", "content"} & changed_substantial_fields:
        refreshed_embedding = await generate_post_embedding(post.title, post.content)
        if refreshed_embedding is not None:
            post.embedding = refreshed_embedding

    await db.commit()

    # 重新查询以获取更新后的关联数据
    query = select(Post).where(Post.id == post.id)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_images),
    )
    result = await db.execute(query)
    post = result.unique().scalar_one()

    response = PostResponse.model_validate(post)
    if post.is_anonymous:
        response.author = None
    elif post.user:
        response.author = {"id": post.user.id, "nickname": post.user.nickname, "avatar_url": post.user.avatar_url, "is_verified": post.user.campus_verified}

    return response


@router.delete("/{post_id}", summary="删除信息")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """删除信息（软删除 + 状态机归档），需要认证，验证所有权

    FND-03.2: 删除采用 is_deleted=True + 状态置 archived（通过状态机校验），
    不引入第 7 种 deleted 状态。
    - 已 archived 终态：仅设置 is_deleted，不再触发状态机
    - 其他非终态：通过状态机流转到 archived

    TEN-02.3: 跨校对象 → 404
    """
    # 查询信息
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if post is None:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

    # 验证所有权
    if post.user_id != current_user.id:
        raise ForbiddenException(detail="没有权限删除此信息")

    # 软删除标记
    post.is_deleted = True
    post.deleted_at = datetime.now()

    # FND-03.2: 通过状态机将非终态帖子流转到 archived（不写第 7 种 deleted 状态）
    if post.status != PostStatus.ARCHIVED:
        if not can_transition(post.status, PostStatus.ARCHIVED):
            # 状态机不允许直接归档（理论上不会发生：所有非终态都允许 → archived）
            raise BadRequestException(
                detail=f"当前状态 {post.status} 不允许归档"
            )
        post.status = PostStatus.ARCHIVED
        post.updated_at = datetime.now()

    await db.commit()

    return {"message": "删除成功"}


# ============================================================
# T-B-04: 状态流转接口
# ============================================================

def _is_admin(user: User) -> bool:
    """判断用户是否为管理员（T-X-01：使用统一权限系统）"""
    from app.core.permissions import is_admin
    return is_admin(user)


@router.get("/{post_id}/allowed-transitions", summary="获取可流转状态列表")
async def get_post_allowed_transitions(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取当前状态下可流转的目标状态列表（T-B-04）

    普通用户与管理员返回相同的可流转集合，但实际能否流转由 transition 接口按权限校验。

    TEN-02.3: 跨校对象 → 404
    """
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.is_deleted == False)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验
    check_resource_in_tenant(post.school_id, tenant)

    allowed = get_allowed_transitions(post.status)
    return {
        "post_id": post_id,
        "current_status": post.status,
        "allowed_transitions": sorted(allowed),
    }


@router.post(
    "/{post_id}/transition",
    response_model=PostTransitionResponse,
    summary="状态流转（T-B-04）",
)
async def transition_post_status(
    post_id: int,
    data: PostTransitionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """流转信息状态（6 态状态机）

    权限规则：
    - 普通用户仅可执行：draft → pending（提交审核）、draft → archived（放弃草稿）
    - 管理员可执行所有合法流转（审核通过/驳回/归档/过期/冲突标记等）
    - 已归档（archived）为终态，任何人都不可流转

    流转合法性由 app.core.post_status.can_transition 校验。

    TEN-02.3: 跨校对象 → 404；普通 admin 无权操作其他学校的帖子（resource校验拦截）
    """
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.is_deleted == False)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404（super_admin 已通过 tenant 跨校访问）
    check_resource_in_tenant(post.school_id, tenant)

    previous_status = post.status
    target = normalize_status(data.target_status)

    # 1. 校验目标状态合法性
    if not can_transition(previous_status, target):
        raise BadRequestException(
            detail=f"非法状态流转：{previous_status} → {target}。"
                   f"当前状态可流转至：{sorted(get_allowed_transitions(previous_status))}"
        )

    # 2. 权限校验
    is_admin = _is_admin(current_user)
    is_owner = post.user_id == current_user.id

    # 普通用户仅允许：draft → pending（提交审核）、draft → archived（放弃草稿）
    # 且仅限作者本人操作
    user_allowed = (
        is_owner
        and previous_status == PostStatus.DRAFT
        and target in {PostStatus.PENDING, PostStatus.ARCHIVED}
    )
    if not is_admin and not user_allowed:
        raise ForbiddenException(
            detail="无权限执行此状态流转。普通用户仅可将自己的草稿提交审核或归档。"
        )

    # 3. 执行流转
    post.status = target
    post.updated_at = datetime.now()

    # SUB-01.2: 订阅通知触发（与状态流转同事务提交，保证一致性）
    # - → published：新帖通知（首次发布或重新发布；幂等）
    # - → expired：过期通知（管理员手动标记过期；自动任务由 expire_posts_job 单独触发）
    # - → conflict：冲突通知（管理员通过状态机直接标记冲突）
    # 普通用户仅可 draft → pending/archived，不会触发上述任一分支
    from app.services.subscription_notifier import (
        notify_new_post, notify_post_expired, notify_post_conflict,
    )
    if target == PostStatus.PUBLISHED and previous_status != PostStatus.PUBLISHED:
        await notify_new_post(db, post, actor_id=current_user.id)
    elif target == PostStatus.EXPIRED and previous_status != PostStatus.EXPIRED:
        await notify_post_expired(db, post, actor_id=current_user.id)
    elif target == PostStatus.CONFLICT and previous_status != PostStatus.CONFLICT:
        await notify_post_conflict(db, post, actor_id=current_user.id)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise BadRequestException(detail="状态流转失败，请重试")

    await db.refresh(post)

    return PostTransitionResponse(
        post_id=post.id,
        previous_status=previous_status,
        current_status=post.status,
        transitioned_at=post.updated_at,
        transitioned_by=current_user.id,
    )


# ============================================================
# AI-03.1: AI 辅助发布建议
# ============================================================
@router.post(
    "/ai-suggest",
    response_model=AIPublishSuggestionResponse,
    summary="AI 辅助发布建议（AI-03）",
)
async def ai_suggest_post(
    payload: AIPublishSuggestRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """AI 辅助发布建议：草稿 → 结构化建议（不修改原文）

    流程：
    1. TenantContext 取校（三校隔离）
    2. 确定性敏感信息检测（手机/邮箱/身份证/银行卡/QQ）→ sensitive_warnings + findings
    3. 缺失字段检测（标题/正文/分类/地点/信息截止时间/联系方式）
    4. 加载当前学校分类与标签白名单
    5. 输入过短或无可建议内容 → fallback（仍返回敏感检测 + 缺失提示）
    6. 否则调用 invoke_ai（PUBLISH_SUGGESTION_SCHEMA 约束）解析建议
    7. 白名单校验分类/标签（非法值丢弃，不报错）
    8. 任一步失败 → fallback=true，仍返回敏感检测结果（确定性，不依赖模型）
    9. 记录 ai_invocation_logs（成功/失败均记录）

    安全约束：
    - **不修改原文**：返回的是"建议"，由前端逐项确认采纳
    - **不改坐标/状态**：本接口不修改 Post 任何字段
    - **不自动过审**：不调用状态机，不影响审核流程
    - **失败不阻塞**：fallback=true 时前端仍可继续手动发布
    - **三校隔离**：school_id 强制取自 TenantContext；分类/标签白名单只来自当前学校
    - **不引用其他学校数据**：提示词只含当前学校的分类/标签白名单

    限流：建议由 RateLimitMiddleware 配置 10 次/分钟（与 AI 搜索一致）。
    """
    trace_id = getattr(request.state, "request_id", "") or None
    response = await execute_publish_suggestion(
        request=payload,
        tenant=tenant,
        db=db,
        user=current_user,
        trace_id=trace_id,
    )
    return response
