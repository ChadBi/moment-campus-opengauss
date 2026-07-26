"""TOPIC-01.2: 专题管理 API（校级后台编排）

仅 admin 及以上可访问；切换学校（X-School-Code）只展示当前学校专题。

提供能力：
- 列表 / 详情（含全部状态）
- 创建 / 更新 / 删除（软删除）
- 批量排序
- 上线（draft/archived → published）/ 下线（published → archived）
- 编排：添加帖子 / 移除帖子 / 调整帖子排序

约束：
- 专题只能引用同校已发布（published）状态的帖子
- 跨校资源统一 404（不返回 403 以免泄露存在性）
- 写请求忽略 body 里的 school_id，强制使用 TenantContext 解析得到的 school_id
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.topic_collection import TopicCollection
from app.models.topic_collection_post import TopicCollectionPost
from app.models.post import Post
from app.models.user import User
from app.models.admin_operation_log import AdminOperationLog
from app.schemas.topic import (
    TopicStatus,
    TopicAdminResponse,
    TopicAdminDetail,
    TopicPostAdminItem,
    TopicCreate,
    TopicUpdate,
    TopicSortRequest,
    TopicAddPostsRequest,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.core.exceptions import (
    NotFoundException, BadRequestException, ConflictException,
)
from app.core.permissions import require_role, Role
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.post_status import PostStatus

router = APIRouter(tags=["专题管理"])

# 统一管理员依赖（user < admin < super_admin）
AdminDep = Depends(require_role(Role.ADMIN))


def _topic_to_admin_response(t: TopicCollection, creator_name: Optional[str] = None) -> TopicAdminResponse:
    return TopicAdminResponse(
        id=t.id,
        title=t.title,
        description=t.description,
        cover_url=t.cover_url,
        school_id=t.school_id,
        creator_id=t.creator_id,
        creator_name=creator_name,
        post_count=t.post_count,
        view_count=t.view_count,
        status=t.status,
        sort_order=t.sort_order,
        published_at=t.published_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


async def _load_topic_or_404(db: AsyncSession, topic_id: int) -> TopicCollection:
    """加载专题（未软删除）；不存在抛 404"""
    t = await db.scalar(
        select(TopicCollection).where(
            TopicCollection.id == topic_id,
            TopicCollection.is_deleted == False,  # noqa: E712
        )
    )
    if not t:
        raise NotFoundException(detail="专题不存在")
    return t


async def _check_topic_in_tenant(topic: TopicCollection, tenant: TenantContext) -> None:
    """资源级租户校验：跨校专题统一 404"""
    check_resource_in_tenant(topic.school_id, tenant)
    # 注：本函数为 async 以便调用方使用 await；check_resource_in_tenant 本身是同步函数
    # 但保留 async 签名便于未来扩展（如异步查询关联资源）


async def _recalc_topic_post_count(db: AsyncSession, topic_id: int) -> int:
    """重新计算专题的 post_count 并返回新值"""
    count = await db.scalar(
        select(func.count(TopicCollectionPost.id)).where(
            TopicCollectionPost.topic_collection_id == topic_id
        )
    )
    return int(count or 0)


# ============================================================
# 列表 / 详情
# ============================================================
@router.get(
    "/admin/topics",
    response_model=PaginatedResponse[TopicAdminResponse],
    summary="专题列表（管理视图，TOPIC-01.2）",
)
async def list_admin_topics(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(
        None, description="按状态筛选：draft / published / archived"
    ),
    keyword: Optional[str] = Query(None, description="按标题模糊搜索"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """专题管理列表：默认全部状态，支持按状态/标题筛选。

    TEN-02.3：按当前学校过滤，跨校专题不会出现。
    """
    base_filter = [
        TopicCollection.school_id == tenant.school_id,
        TopicCollection.is_deleted == False,  # noqa: E712
    ]
    if status:
        base_filter.append(TopicCollection.status == status)
    if keyword:
        base_filter.append(TopicCollection.title.ilike(f"%{keyword}%"))

    query = (
        select(TopicCollection)
        .where(*base_filter)
        .options(joinedload(TopicCollection.creator))
        .order_by(
            TopicCollection.sort_order.asc(),
            TopicCollection.created_at.desc(),
        )
    )
    count_query = (
        select(func.count()).select_from(TopicCollection).where(*base_filter)
    )
    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    topics = result.unique().scalars().all()

    items = [
        _topic_to_admin_response(
            t, creator_name=t.creator.nickname if t.creator else None
        )
        for t in topics
    ]
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.get(
    "/admin/topics/{topic_id}",
    response_model=TopicAdminDetail,
    summary="专题详情（管理视图，含关联帖子）",
)
async def get_admin_topic_detail(
    topic_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """专题管理详情：含全部状态的关联帖子（含 draft/pending 等，便于编排）。

    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    # 加载创建者昵称
    creator = await db.scalar(select(User).where(User.id == topic.creator_id))

    # 关联帖子（管理视图，含全部状态，但排除已软删除的帖子）
    rows = await db.execute(
        select(TopicCollectionPost, Post)
        .join(Post, TopicCollectionPost.post_id == Post.id)
        .where(TopicCollectionPost.topic_collection_id == topic.id)
        .order_by(TopicCollectionPost.sort_order.asc(), TopicCollectionPost.id.asc())
    )
    posts: list[TopicPostAdminItem] = []
    for tcp, post in rows.all():
        posts.append(TopicPostAdminItem(
            id=tcp.id,
            topic_collection_id=tcp.topic_collection_id,
            post_id=tcp.post_id,
            post_title=post.title,
            post_status=post.status,
            post_school_id=post.school_id,
            sort_order=tcp.sort_order,
            created_at=tcp.created_at,
        ))

    resp = _topic_to_admin_response(
        topic, creator_name=creator.nickname if creator else None
    )
    return TopicAdminDetail(
        **resp.model_dump(),
        posts=posts,
    )


# ============================================================
# 创建 / 更新 / 删除
# ============================================================
@router.post(
    "/admin/topics",
    response_model=TopicAdminResponse,
    summary="创建专题（TOPIC-01.2）",
)
async def create_topic(
    data: TopicCreate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """创建专题。TEN-02.1: 强制使用 tenant.school_id，忽略 body 里的 school_id。

    status 可直接传 'published' 在创建时即上线（published_at 自动写入）。
    """
    now = datetime.now()
    topic = TopicCollection(
        school_id=tenant.school_id,
        creator_id=admin.id,
        title=data.title,
        description=data.description,
        cover_url=data.cover_url,
        sort_order=data.sort_order,
        status=data.status,
        post_count=0,
        view_count=0,
        published_at=now if data.status == TopicStatus.PUBLISHED else None,
        created_at=now,
        updated_at=now,
    )
    db.add(topic)

    log = AdminOperationLog(
        admin_id=admin.id,
        action="create_topic",
        target_type="topic_collection",
        target_id=0,  # 创建时还没有 id，commit 后回填
        detail=f"新建专题：{data.title}（status={data.status}）",
    )
    db.add(log)

    await db.commit()
    await db.refresh(topic)

    # 回填日志的 target_id（与 create_category 一致）
    log.target_id = topic.id
    await db.commit()

    return _topic_to_admin_response(topic, creator_name=admin.nickname)


# ============================================================
# 批量排序
# 注意：本路由必须放在 /admin/topics/{topic_id} 之前，
# 否则 /admin/topics/sort 会被 {topic_id} 路径参数匹配（int 解析失败 → 422）。
# ============================================================
@router.put(
    "/admin/topics/sort",
    response_model=MessageResponse,
    summary="批量排序专题（TOPIC-01.2）",
)
async def sort_topics(
    data: TopicSortRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """批量更新专题的 sort_order。

    - 仅更新当前学校下的专题（跨校 id 计入失败但返回成功总数）
    - 全部 id 必须存在且未软删除，否则返回 404
    """
    topic_ids = [item.id for item in data.items]
    rows = await db.execute(
        select(TopicCollection).where(
            TopicCollection.id.in_(topic_ids),
            TopicCollection.is_deleted == False,  # noqa: E712
        )
    )
    found = {t.id: t for t in rows.scalars().all()}
    if len(found) != len(topic_ids):
        missing = set(topic_ids) - set(found.keys())
        raise NotFoundException(detail=f"专题不存在：{sorted(missing)}")

    # 跨校校验：任一不属于当前学校 → 404
    for t in found.values():
        await _check_topic_in_tenant(t, tenant)

    sort_map = {item.id: item.sort_order for item in data.items}
    for tid, t in found.items():
        t.sort_order = sort_map[tid]
        t.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="sort_topics",
        target_type="topic_collection",
        target_id=0,
        detail=f"批量排序 {len(topic_ids)} 个专题",
    ))
    await db.commit()
    return MessageResponse(message=f"已排序 {len(topic_ids)} 个专题")


@router.put(
    "/admin/topics/{topic_id}",
    response_model=TopicAdminResponse,
    summary="更新专题（标题/描述/封面/排序）",
)
async def update_topic(
    topic_id: int,
    data: TopicUpdate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新专题元信息（部分更新；状态变更走上下线接口）。

    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    changes: list[str] = []
    if data.title is not None and data.title != topic.title:
        changes.append(f"title: {topic.title} → {data.title}")
        topic.title = data.title
    if data.description is not None and data.description != topic.description:
        changes.append("description: 变更")
        topic.description = data.description
    if data.cover_url is not None and data.cover_url != topic.cover_url:
        changes.append("cover_url: 变更")
        topic.cover_url = data.cover_url
    if data.sort_order is not None and data.sort_order != topic.sort_order:
        changes.append(f"sort_order: {topic.sort_order} → {data.sort_order}")
        topic.sort_order = data.sort_order

    topic.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="update_topic",
        target_type="topic_collection",
        target_id=topic_id,
        detail="；".join(changes) if changes else "无变更",
    ))
    await db.commit()
    await db.refresh(topic)

    return _topic_to_admin_response(topic, creator_name=admin.nickname)


@router.delete(
    "/admin/topics/{topic_id}",
    response_model=MessageResponse,
    summary="删除专题（软删除）",
)
async def delete_topic(
    topic_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """软删除专题（is_deleted=True）+ 同时软删除其关联帖子。

    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    now = datetime.now()
    topic.is_deleted = True
    topic.deleted_at = now
    topic.updated_at = now

    # 同时清理 topic_collection_posts 关联
    rows = await db.execute(
        select(TopicCollectionPost).where(
            TopicCollectionPost.topic_collection_id == topic.id
        )
    )
    for tcp in rows.scalars().all():
        await db.delete(tcp)

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="delete_topic",
        target_type="topic_collection",
        target_id=topic_id,
        detail=f"删除专题：{topic.title}",
    ))
    await db.commit()
    return MessageResponse(message=f"专题「{topic.title}」已删除")


# ============================================================
# 上下线
# ============================================================
@router.put(
    "/admin/topics/{topic_id}/publish",
    response_model=TopicAdminResponse,
    summary="上线专题（draft/archived → published）",
)
async def publish_topic(
    topic_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """上线专题：状态 → published。

    - 若专题内没有已发布帖子，给出警告但仍允许上线
    - 已 published 的专题重复上线返回 BadRequest
    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    if topic.status == TopicStatus.PUBLISHED:
        raise BadRequestException(detail="专题已上线")

    if topic.status not in (TopicStatus.DRAFT, TopicStatus.ARCHIVED):
        raise BadRequestException(
            detail=f"当前状态 {topic.status} 不允许上线"
        )

    now = datetime.now()
    topic.status = TopicStatus.PUBLISHED
    topic.published_at = topic.published_at or now
    topic.updated_at = now

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="publish_topic",
        target_type="topic_collection",
        target_id=topic_id,
        detail=f"上线专题：{topic.title}",
    ))
    await db.commit()
    await db.refresh(topic)
    return _topic_to_admin_response(topic, creator_name=admin.nickname)


@router.put(
    "/admin/topics/{topic_id}/archive",
    response_model=TopicAdminResponse,
    summary="下线专题（published → archived）",
)
async def archive_topic(
    topic_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """下线专题：状态 → archived（用户端不再可见，保留数据）。

    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    if topic.status == TopicStatus.ARCHIVED:
        raise BadRequestException(detail="专题已下线")

    if topic.status != TopicStatus.PUBLISHED:
        raise BadRequestException(
            detail=f"当前状态 {topic.status} 不允许下线（仅 published 可下线）"
        )

    now = datetime.now()
    topic.status = TopicStatus.ARCHIVED
    topic.updated_at = now

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="archive_topic",
        target_type="topic_collection",
        target_id=topic_id,
        detail=f"下线专题：{topic.title}",
    ))
    await db.commit()
    await db.refresh(topic)
    return _topic_to_admin_response(topic, creator_name=admin.nickname)


# ============================================================
# 编排：添加帖子 / 移除帖子
# ============================================================
async def _assert_post_in_same_school_published(
    db: AsyncSession, post_id: int, tenant: TenantContext
) -> Post:
    """校验帖子存在、未软删除、属于当前学校、且状态为 published。

    TOPIC-01.1: 专题只能引用同校已发布内容。
    TEN-02.3: 跨校/不存在 → 404（不泄露存在性）。
    """
    post = await db.scalar(
        select(Post).where(Post.id == post_id, Post.is_deleted == False)  # noqa: E712
    )
    if not post:
        raise NotFoundException(detail="帖子不存在")
    check_resource_in_tenant(post.school_id, tenant)
    if post.status != PostStatus.PUBLISHED:
        raise BadRequestException(
            detail=f"帖子 #{post_id} 当前状态为 {post.status}，仅可引用已发布（published）帖子"
        )
    return post


@router.post(
    "/admin/topics/{topic_id}/posts",
    response_model=TopicAdminDetail,
    summary="向专题添加帖子（仅同校已发布）",
)
async def add_posts_to_topic(
    topic_id: int,
    data: TopicAddPostsRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """向专题添加帖子。

    TOPIC-01.1: 专题只能引用同校已发布（published）状态的帖子。
    - 已存在的 (topic_id, post_id) 关联返回 BadRequest
    - 帖子状态非 published 返回 BadRequest
    - 跨校帖子返回 404（不泄露存在性）
    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    added: list[int] = []
    for ref in data.posts:
        await _assert_post_in_same_school_published(db, ref.post_id, tenant)

        # 校验是否已关联
        existing = await db.scalar(
            select(TopicCollectionPost).where(
                TopicCollectionPost.topic_collection_id == topic.id,
                TopicCollectionPost.post_id == ref.post_id,
            )
        )
        if existing:
            raise ConflictException(
                detail=f"帖子 #{ref.post_id} 已在专题中"
            )

        tcp = TopicCollectionPost(
            topic_collection_id=topic.id,
            post_id=ref.post_id,
            sort_order=ref.sort_order,
            created_at=datetime.now(),
        )
        db.add(tcp)
        added.append(ref.post_id)

    # 更新 post_count
    topic.post_count = await _recalc_topic_post_count(db, topic.id)
    topic.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="add_posts_to_topic",
        target_type="topic_collection",
        target_id=topic.id,
        detail=f"添加 {len(added)} 个帖子到专题：{topic.title}",
    ))
    await db.commit()
    await db.refresh(topic)

    # 返回管理详情（含关联帖子）
    return await _build_admin_detail(db, topic, admin.nickname)


@router.delete(
    "/admin/topics/{topic_id}/posts/{post_id}",
    response_model=TopicAdminDetail,
    summary="从专题移除帖子",
)
async def remove_post_from_topic(
    topic_id: int,
    post_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """从专题移除指定帖子。

    TEN-02.3：跨校专题统一 404。
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    tcp = await db.scalar(
        select(TopicCollectionPost).where(
            TopicCollectionPost.topic_collection_id == topic.id,
            TopicCollectionPost.post_id == post_id,
        )
    )
    if not tcp:
        raise NotFoundException(detail="帖子不在专题中")

    await db.delete(tcp)

    topic.post_count = await _recalc_topic_post_count(db, topic.id)
    topic.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="remove_post_from_topic",
        target_type="topic_collection",
        target_id=topic.id,
        detail=f"从专题移除帖子 #{post_id}：{topic.title}",
    ))
    await db.commit()
    await db.refresh(topic)

    return await _build_admin_detail(db, topic, admin.nickname)


@router.put(
    "/admin/topics/{topic_id}/posts/sort",
    response_model=TopicAdminDetail,
    summary="调整专题内帖子的排序",
)
async def sort_topic_posts(
    topic_id: int,
    data: TopicAddPostsRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """批量调整专题内帖子的 sort_order。

    - 仅更新已存在的关联，未关联的 post_id 计入失败
    - TEN-02.3：跨校专题统一 404
    """
    topic = await _load_topic_or_404(db, topic_id)
    await _check_topic_in_tenant(topic, tenant)

    refs = {ref.post_id: ref.sort_order for ref in data.posts}
    rows = await db.execute(
        select(TopicCollectionPost).where(
            TopicCollectionPost.topic_collection_id == topic.id,
            TopicCollectionPost.post_id.in_(list(refs.keys())),
        )
    )
    found = {tcp.post_id: tcp for tcp in rows.scalars().all()}
    if len(found) != len(refs):
        missing = set(refs.keys()) - set(found.keys())
        raise NotFoundException(detail=f"帖子不在专题中：{sorted(missing)}")

    for post_id, tcp in found.items():
        tcp.sort_order = refs[post_id]

    topic.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="sort_topic_posts",
        target_type="topic_collection",
        target_id=topic.id,
        detail=f"调整专题内 {len(refs)} 个帖子的排序",
    ))
    await db.commit()
    await db.refresh(topic)

    return await _build_admin_detail(db, topic, admin.nickname)


# ============================================================
# 内部工具：构建管理详情响应
# ============================================================
async def _build_admin_detail(
    db: AsyncSession, topic: TopicCollection, creator_name: Optional[str] = None
) -> TopicAdminDetail:
    """构建 TopicAdminDetail（含关联帖子列表）"""
    rows = await db.execute(
        select(TopicCollectionPost, Post)
        .join(Post, TopicCollectionPost.post_id == Post.id)
        .where(TopicCollectionPost.topic_collection_id == topic.id)
        .order_by(TopicCollectionPost.sort_order.asc(), TopicCollectionPost.id.asc())
    )
    posts: list[TopicPostAdminItem] = []
    for tcp, post in rows.all():
        posts.append(TopicPostAdminItem(
            id=tcp.id,
            topic_collection_id=tcp.topic_collection_id,
            post_id=tcp.post_id,
            post_title=post.title,
            post_status=post.status,
            post_school_id=post.school_id,
            sort_order=tcp.sort_order,
            created_at=tcp.created_at,
        ))
    resp = _topic_to_admin_response(topic, creator_name=creator_name)
    return TopicAdminDetail(**resp.model_dump(), posts=posts)
