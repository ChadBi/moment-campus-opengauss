from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user_optional
from app.models.user import User
from app.models.post import Post
from app.models.category import Category
from app.models.location import Location
from app.models.post_image import PostImage
from app.models.search_history import SearchHistory
from app.schemas.post import PostListResponse
from app.schemas.common import PaginatedResponse
from app.schemas.search import AISearchRequest, AISearchResponse
from app.core.exceptions import NotFoundException
from app.core.tenant import TenantContext, get_tenant_context
from app.services.ai_search import execute_ai_search

router = APIRouter(tags=["搜索"])


@router.get("/search", response_model=PaginatedResponse[PostListResponse])
async def search_posts(
    keyword: Optional[str] = Query(None, max_length=100, description="搜索关键词"),
    category_id: Optional[int] = Query(None, description="分类ID"),
    location_id: Optional[int] = Query(None, description="地点ID"),
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
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    搜索信息

    DSC-01.1: 支持关键词搜索 + 多字段筛选（分类/地点/有效状态/时间范围）+ 多种排序。
    DSC-01.2: 使用 selectinload/joinedload 预加载关联，消除 N+1 查询。
    TEN-02.3：按当前学校过滤，跨校帖子不会出现在搜索结果中。

    Task 1.2 调整：移除 post_type_id 筛选参数（PostType 已删除，统一使用 category）
    Task 1.3 调整：移除 tag 筛选参数（Tag 已删除，统一使用 category）

    有效状态筛选：
        - published: 仅显示已发布
        - expired: 仅显示已过期
        - valid 或不传：显示 published + expired（默认对外可见集合）
    """
    # 构建基础查询（TEN-02.3: 强制按当前学校过滤）
    # DSC-01.1: 默认返回 published + expired 集合（与 posts 列表一致）
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

    # 关键词搜索（多字段模糊匹配）
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.where(
            or_(
                Post.title.ilike(keyword_pattern),
                Post.content.ilike(keyword_pattern),
                Post.contact_info.ilike(keyword_pattern),
            )
        )

    # 筛选条件
    if category_id:
        query = query.where(Post.category_id == category_id)
    if location_id:
        query = query.where(Post.location_id == location_id)
    if date_from is not None:
        query = query.where(Post.created_at >= date_from)
    if date_to is not None:
        query = query.where(Post.created_at <= date_to)

    # 排序（DSC-01.1: 统一排序语义）
    if sort == "latest":
        query = query.order_by(Post.created_at.desc())
    elif sort == "hottest":
        query = query.order_by(Post.like_count.desc(), Post.created_at.desc())
    elif sort == "active":
        query = query.order_by(Post.updated_at.desc(), Post.created_at.desc())
    elif sort == "nearest":
        # 最近活动 = 按 updated_at 降序
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

    # DSC-01.2: 预加载关联数据，消除 N+1
    # 一次查询预加载：author / category / location / images
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    posts = result.unique().scalars().all()

    # 转换为响应格式（所有关联数据已预加载，无额外查询）
    items = []
    for post in posts:
        post_data = PostListResponse.model_validate(post)
        # 设置作者信息（is_anonymous 时隐藏真实身份）
        if post.is_anonymous:
            post_data.author = None
        elif post.user:
            post_data.author = {
                "id": post.user.id,
                "nickname": post.user.nickname,
                "avatar_url": post.user.avatar_url,
            }
        # 设置封面图片（取第一张）
        if post.post_images:
            post_data.cover_image = post.post_images[0].image_url
        items.append(post_data)

    # 记录搜索历史（如果有用户登录且有关键词）
    if current_user and keyword:
        search_history = SearchHistory(
            user_id=current_user.id,
            keyword=keyword,
            result_count=total,
        )
        db.add(search_history)
        await db.commit()

    return PaginatedResponse.create(items, page, page_size, total)


# ============================================================
# AI-02.1: AI 结构化搜索
# ============================================================
@router.post("/search/ai", response_model=AISearchResponse, summary="AI 结构化搜索")
async def ai_search_posts(
    payload: AISearchRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """AI 结构化搜索：自然语言 → 意图 → 检索 → 排序 → 理由

    流程：
    1. TenantContext 取校（三校隔离）
    2. 输入校验（schema 已强制长度；中间件限流；服务内敏感词检查）
    3. 模型解析意图（严格 JSON Schema + 超时 + 有限重试，由 AI-01 Provider 层负责）
    4. 白名单校验分类/排序/时间/地图范围（非法值丢弃，不向用户报错）
    5. 查询当前学校 published 且未过期未删除的帖子
    6. 确定性分数排序（时间新鲜度 + 验证数 + 相关度）
    7. 模板生成简短理由
    8. 记录 ai_invocation_logs（成功/失败均记录）
    9. 任一步失败 → 降级普通搜索，返回 fallback=true 与降级原因

    租户隔离：
    - school_id 强制取自 TenantContext，不接受外部传入
    - 模型提示词只包含当前学校的分类/地点白名单，不泄露其他学校数据
    - 查询强制按 school_id 过滤

    限流：RateLimitMiddleware 已对 POST /api/v1/search/ai 配置 10 次/分钟。
    """
    trace_id = getattr(request.state, "request_id", "") or None
    response = await execute_ai_search(
        request=payload,
        tenant=tenant,
        db=db,
        user=current_user,
        trace_id=trace_id,
    )

    # 记录搜索历史（登录用户 + 有意图关键词）
    if current_user and response.intent and response.intent.filters.keyword:
        try:
            search_history = SearchHistory(
                user_id=current_user.id,
                keyword=response.intent.filters.keyword,
                result_count=response.total,
            )
            db.add(search_history)
            await db.commit()
        except Exception:  # noqa: BLE001  历史记录失败不影响主流程
            await db.rollback()

    return response
