"""GOV-02: 自动过期独立任务与运行记录测试

覆盖 GOV-02.1 与 GOV-02.2：
- GOV-02.1: 独立 worker 批量扫描到期 published 转 expired
            - 获取锁/幂等键
            - 批量扫描 published 且 expire_at < now()
            - 状态机校验 published → expired
            - 每帖只通知一次
- GOV-02.2: 支持 dry-run 与手动重跑
            - dry-run 只报告不执行
            - 手动重跑通过 API 触发
            - 记录开始/成功/失败/处理数量/耗时
            - 重复执行不重复通知、不产生非法状态
"""
import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.core.security import get_password_hash
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.notification import Notification
from app.models.job_run_record import JobRunRecord
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.core.post_status import PostStatus
from app.jobs.expire_posts import (
    JOB_NAME,
    _try_acquire_advisory_lock,
    expire_posts_job,
)


# ============================================================
# 辅助函数
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    """为学校分配 operations 档订阅（COM-01 要求发布需 active 订阅）"""
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is None:
        return
    now = datetime.now()
    sub = SchoolSubscription(
        school_id=school_id,
        plan_id=plan.id,
        status="active",
        started_at=now,
        expires_at=None,
        assigned_at=now,
    )
    db.add(sub)
    await db.flush()


async def _create_user(
    db: AsyncSession, email: str, nickname: str, school_id: int, role: str = "user"
) -> User:
    user = User(
        email=email,
        nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id,
        role=role,
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession, user_id: int, school_id: int, role: str = "member"
) -> SchoolMembership:
    m = SchoolMembership(
        user_id=user_id,
        school_id=school_id,
        role=role,
        status="active",
        is_default=False,
    )
    db.add(m)
    await db.flush()
    return m


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    cat = Category(
        school_id=school_id,
        name=name,
        code=code,
        icon="🔍",
        default_validity_days=30,
        is_active=True,
    )
    db.add(cat)
    await db.flush()
    return cat


async def _create_published_post(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    title: str = "测试帖子",
    expire_at: datetime | None = None,
    content: str = "这是测试内容，至少十个字符",
) -> Post:
    """直接在数据库中创建 published 帖子（绕过审核流程，用于测试）"""
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        title=title,
        content=content,
        status=PostStatus.PUBLISHED,
        expire_at=expire_at,
        is_deleted=False,
        is_anonymous=False,
    )
    db.add(post)
    await db.flush()
    return post


@pytest_asyncio.fixture
async def gov_02_setup(db_session: AsyncSession) -> dict:
    """GOV-02 测试数据：1 校 + 1 管理员 + 1 普通用户 + 1 分类 + 1 类型

    创建多条 published 帖子：
    - expired_post: expire_at 已过期（应该被扫描并流转）
    - future_post: expire_at 未来（不应被扫描）
    - no_expire_post: expire_at=None（不应被扫描）
    - deleted_post: expire_at 已过期但 is_deleted=True（不应被扫描）
    """
    school = await _create_school(db_session, "GOV-02 测试大学", "gov02-uni")
    await _assign_operations_subscription(db_session, school.id)

    cat = await _create_category(db_session, school.id, "失物招领", "gov02-lost")

    user = await _create_user(
        db_session, "gov02user@example.com", "GOV-02 用户", school.id
    )
    admin = await _create_user(
        db_session, "gov02admin@example.com", "GOV-02 管理员", school.id, role="admin"
    )
    await _create_membership(db_session, user.id, school.id, "member")
    await _create_membership(db_session, admin.id, school.id, "admin")

    now = datetime.now()

    # 已过期帖子（expire_at 在过去）
    expired_post = await _create_published_post(
        db_session, user.id, school.id, cat.id,
        title="已过期帖子",
        expire_at=now - timedelta(hours=1),
    )

    # 未过期帖子（expire_at 在未来）
    future_post = await _create_published_post(
        db_session, user.id, school.id, cat.id,
        title="未过期帖子",
        expire_at=now + timedelta(days=7),
    )

    # 无 expire_at 帖子（不应被扫描）
    no_expire_post = await _create_published_post(
        db_session, user.id, school.id, cat.id,
        title="无过期时间帖子",
        expire_at=None,
    )

    # 已删除的过期帖子（不应被扫描）
    deleted_post = await _create_published_post(
        db_session, user.id, school.id, cat.id,
        title="已删除过期帖子",
        expire_at=now - timedelta(hours=2),
    )
    deleted_post.is_deleted = True
    deleted_post.deleted_at = now

    await db_session.commit()

    return {
        "school": {"id": school.id, "code": school.code},
        "category": {"id": cat.id},
        "user": {"id": user.id, "email": user.email},
        "admin": {"id": admin.id, "email": admin.email},
        "posts": {
            "expired": {"id": expired_post.id},
            "future": {"id": future_post.id},
            "no_expire": {"id": no_expire_post.id},
            "deleted": {"id": deleted_post.id},
        },
    }


# ============================================================
# GOV-02.1: 独立 worker 批量扫描到期 published 转 expired
# ============================================================

@pytest.mark.asyncio
async def test_expire_posts_normal_expiration(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.1: 正常过期 - published + expire_at 过去的帖子应转为 expired + 创建通知"""
    setup = gov_02_setup
    expired_post_id = setup["posts"]["expired"]["id"]
    user_id = setup["user"]["id"]

    # 运行 job
    record = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )

    # 验证任务记录
    assert record.status == "success"
    assert record.processed_count >= 1
    assert record.failed_count == 0
    assert record.finished_at is not None
    assert record.finished_at >= record.started_at

    # 验证帖子状态已变为 expired
    post = await db_session.get(Post, expired_post_id)
    assert post.status == PostStatus.EXPIRED

    # 验证通知已创建
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "post_expired",
            Notification.target_type == "post",
            Notification.target_id == expired_post_id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None
    assert "已过期" in notif.title
    assert notif.is_read is False


@pytest.mark.asyncio
async def test_expire_posts_skips_future_and_no_expire(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.1: 未过期帖子、无 expire_at 帖子、已删除帖子不应被扫描"""
    setup = gov_02_setup
    future_post_id = setup["posts"]["future"]["id"]
    no_expire_post_id = setup["posts"]["no_expire"]["id"]
    deleted_post_id = setup["posts"]["deleted"]["id"]

    await expire_posts_job(db_session, dry_run=False, triggered_by="system")

    # 未过期帖子状态保持 published
    future_post = await db_session.get(Post, future_post_id)
    assert future_post.status == PostStatus.PUBLISHED

    # 无 expire_at 帖子状态保持 published
    no_expire_post = await db_session.get(Post, no_expire_post_id)
    assert no_expire_post.status == PostStatus.PUBLISHED

    # 已删除帖子状态保持 published（虽然 expire_at 已过期，但 is_deleted=True）
    deleted_post = await db_session.get(Post, deleted_post_id)
    assert deleted_post.status == PostStatus.PUBLISHED
    assert deleted_post.is_deleted is True


@pytest.mark.asyncio
async def test_expire_posts_idempotent_notifications(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.1 / GOV-02.2: 幂等性 - 重复运行不重复通知、不产生非法状态"""
    setup = gov_02_setup
    expired_post_id = setup["posts"]["expired"]["id"]
    user_id = setup["user"]["id"]

    # 第一次运行
    record1 = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )
    assert record1.status == "success"
    assert record1.processed_count >= 1

    # 第一次运行后通知数量应为 1
    count_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "post_expired",
            Notification.target_id == expired_post_id,
        )
    )
    notifications_after_first = count_result.scalars().all()
    assert len(notifications_after_first) == 1

    # 第二次运行（无新到期帖子，因为 expired_post 已转为 expired）
    record2 = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )
    assert record2.status == "success"
    # 第二次扫描应找不到 published 且过期的帖子（已被流转为 expired）
    assert record2.processed_count == 0

    # 通知数量仍为 1（不重复）
    count_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "post_expired",
            Notification.target_id == expired_post_id,
        )
    )
    notifications_after_second = count_result.scalars().all()
    assert len(notifications_after_second) == 1

    # 帖子状态仍为 expired（不产生非法状态）
    post = await db_session.get(Post, expired_post_id)
    assert post.status == PostStatus.EXPIRED


# ============================================================
# GOV-02.2: 支持 dry-run
# ============================================================

@pytest.mark.asyncio
async def test_expire_posts_dry_run(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.2: dry-run 模式 - 只报告不执行（不写库、不发通知）"""
    setup = gov_02_setup
    expired_post_id = setup["posts"]["expired"]["id"]
    user_id = setup["user"]["id"]

    # dry-run 运行
    record = await expire_posts_job(
        db_session, dry_run=True, triggered_by="system"
    )

    # 验证任务记录
    assert record.status == "success"
    assert record.dry_run is True
    assert record.processed_count >= 1  # 报告了 1 个待过期帖子

    # 帖子状态应保持 published（未实际执行）
    post = await db_session.get(Post, expired_post_id)
    assert post.status == PostStatus.PUBLISHED

    # 不应创建通知
    count_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "post_expired",
            Notification.target_id == expired_post_id,
        )
    )
    assert count_result.scalar_one_or_none() is None

    # 之后非 dry-run 运行应该能正常执行
    record2 = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )
    assert record2.status == "success"
    assert record2.dry_run is False

    post = await db_session.get(Post, expired_post_id)
    assert post.status == PostStatus.EXPIRED


# ============================================================
# GOV-02.2: 通过 API 手动触发
# ============================================================

@pytest_asyncio.fixture
async def gov_02_admin_token(gov_02_setup: dict) -> str:
    """为 GOV-02 管理员生成 access token"""
    from app.core.security import create_access_token
    admin_id = gov_02_setup["admin"]["id"]
    return create_access_token(data={"sub": str(admin_id)})


@pytest_asyncio.fixture
async def gov_02_super_admin_token(
    gov_02_setup: dict, db_session: AsyncSession
) -> str:
    """为 GOV-02 平台超级管理员生成 access token。"""
    from app.core.security import create_access_token

    super_admin = await _create_user(
        db_session,
        "gov02superadmin@example.com",
        "GOV-02 超级管理员",
        gov_02_setup["school"]["id"],
        role="super_admin",
    )
    await db_session.commit()
    return create_access_token(data={"sub": str(super_admin.id)})


@pytest.mark.asyncio
async def test_manual_trigger_expire_posts_api(
    client: AsyncClient, gov_02_setup: dict, gov_02_super_admin_token: str
):
    """GOV-02.2: 通过管理 API 手动触发过期任务"""
    setup = gov_02_setup
    expired_post_id = setup["posts"]["expired"]["id"]
    headers = {"Authorization": f"Bearer {gov_02_super_admin_token}"}

    # 通过 API 触发
    response = await client.post(
        "/api/v1/admin/jobs/expire-posts",
        json={"dry_run": False},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    # 验证返回的任务记录
    assert data["job_name"] == "expire_posts"
    assert data["status"] == "success"
    assert data["triggered_by"] == "manual"
    assert data["triggered_user_id"] is not None
    assert data["processed_count"] >= 1
    assert data["finished_at"] is not None
    assert data["duration_seconds"] is not None
    assert data["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_manual_trigger_expire_posts_api_dry_run(
    client: AsyncClient, gov_02_setup: dict, gov_02_super_admin_token: str
):
    """GOV-02.2: 通过 API 手动触发 dry-run 模式"""
    headers = {"Authorization": f"Bearer {gov_02_super_admin_token}"}

    response = await client.post(
        "/api/v1/admin/jobs/expire-posts",
        json={"dry_run": True},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["status"] == "success"
    assert data["processed_count"] >= 1


@pytest.mark.asyncio
async def test_list_expire_posts_job_records_api(
    client: AsyncClient, gov_02_setup: dict, gov_02_super_admin_token: str,
    db_session: AsyncSession
):
    """GOV-02.2: 查询任务运行记录列表"""
    headers = {"Authorization": f"Bearer {gov_02_super_admin_token}"}

    # 先运行一次任务
    await expire_posts_job(db_session, dry_run=False, triggered_by="system")

    # 查询记录
    response = await client.get(
        "/api/v1/admin/jobs/expire-posts/records",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["job_name"] == "expire_posts"


@pytest.mark.asyncio
async def test_manual_trigger_forbidden_for_normal_user(
    client: AsyncClient, gov_02_setup: dict, db_session: AsyncSession
):
    """GOV-02.2: 普通用户不能触发过期任务（403）"""
    from app.core.security import create_access_token
    user_id = gov_02_setup["user"]["id"]
    token = create_access_token(data={"sub": str(user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/admin/jobs/expire-posts",
        json={"dry_run": True},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["post", "get"])
async def test_expire_posts_admin_apis_forbidden_for_school_admin(
    client: AsyncClient, gov_02_setup: dict, gov_02_admin_token: str, method: str
):
    """平台级跨校任务只允许 super_admin 管理。"""
    headers = {"Authorization": f"Bearer {gov_02_admin_token}"}
    if method == "post":
        response = await client.post(
            "/api/v1/admin/jobs/expire-posts",
            json={"dry_run": True},
            headers=headers,
        )
    else:
        response = await client.get(
            "/api/v1/admin/jobs/expire-posts/records",
            headers=headers,
        )

    assert response.status_code == 403


# ============================================================
# GOV-02.2: 任务运行记录
# ============================================================

@pytest.mark.asyncio
async def test_job_run_record_persisted(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.2: 任务运行记录应持久化到 job_run_records 表"""
    setup = gov_02_setup

    record = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )

    # 从数据库重新查询
    db_record = await db_session.get(JobRunRecord, record.id)
    assert db_record is not None
    assert db_record.job_name == JOB_NAME
    assert db_record.status == "success"
    assert db_record.processed_count >= 1
    assert db_record.failed_count == 0
    assert db_record.finished_at is not None
    assert db_record.started_at <= db_record.finished_at

    # 验证 metadata 包含 duration_ms
    if db_record.metadata_:
        meta = json.loads(db_record.metadata_)
        assert "scanned_count" in meta
        assert "duration_ms" in meta
        assert meta["dry_run"] is False


@pytest.mark.asyncio
async def test_job_run_record_dry_run_flag(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.2: dry-run 模式应在记录中标记 dry_run=True"""
    # 使用 gov_02_setup 中真实存在的 admin 用户 ID，避免外键约束冲突
    admin_id = gov_02_setup["admin"]["id"]
    record = await expire_posts_job(
        db_session, dry_run=True, triggered_by="manual", triggered_user_id=admin_id
    )

    assert record.dry_run is True
    assert record.triggered_by == "manual"
    assert record.triggered_user_id == admin_id


# ============================================================
# GOV-02.1: 锁机制（应用层幂等键）
# ============================================================

@pytest.mark.asyncio
async def test_advisory_lock_failure_is_fail_closed():
    """数据库锁调用异常时必须视为未获锁，不能继续执行任务。"""
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = RuntimeError("advisory lock unavailable")

    assert await _try_acquire_advisory_lock(db) is False


@pytest.mark.asyncio
async def test_job_does_not_process_posts_when_lock_is_not_acquired(
    db_session: AsyncSession, gov_02_setup: dict, monkeypatch: pytest.MonkeyPatch
):
    """锁被占用或获取失败时任务必须 fail-closed，不处理到期帖子。"""
    monkeypatch.setattr(
        "app.jobs.expire_posts._try_acquire_advisory_lock",
        AsyncMock(return_value=False),
    )
    expired_post_id = gov_02_setup["posts"]["expired"]["id"]

    record = await expire_posts_job(db_session, triggered_by="system")

    assert record.status == "failed"
    assert "锁" in record.error_message
    post = await db_session.get(Post, expired_post_id)
    assert post.status == PostStatus.PUBLISHED

@pytest.mark.asyncio
async def test_job_lock_skip_when_running(
    db_session: AsyncSession, gov_02_setup: dict
):
    """GOV-02.1: 锁机制 - 已有 running 任务时应跳过（返回 running 记录）

    模拟：先插入一条 status='running' 的记录，再调用 job，
    应返回该 running 记录而非重复执行。
    """
    # 手动插入一条 running 状态的记录
    running_record = JobRunRecord(
        job_name=JOB_NAME,
        status="running",
        started_at=datetime.now() - timedelta(minutes=1),
        triggered_by="system",
        dry_run=False,
        processed_count=0,
        failed_count=0,
    )
    db_session.add(running_record)
    await db_session.commit()
    await db_session.refresh(running_record)
    running_id = running_record.id

    # 调用 job（应跳过并返回 running 记录）
    record = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )

    # 应返回已存在的 running 记录
    assert record.id == running_id
    assert record.status == "running"

    # 清理：重新查询记录后更新，避免 ORM 对象状态不一致
    # job 内部可能已修改 session 事务状态，需 expire 后重新加载
    db_session.expire_all()
    cleanup_record = await db_session.get(JobRunRecord, running_id)
    if cleanup_record is not None:
        cleanup_record.status = "failed"
        cleanup_record.finished_at = datetime.now()
        cleanup_record.error_message = "test cleanup"
        await db_session.commit()


@pytest.mark.asyncio
async def test_stale_running_job_is_failed_and_new_run_continues(
    db_session: AsyncSession, gov_02_setup: dict
):
    """超过 60 分钟租约的 running 记录应失败收口，且不阻塞新任务。"""
    stale_record = JobRunRecord(
        job_name=JOB_NAME,
        status="running",
        started_at=datetime.now() - timedelta(minutes=60, seconds=1),
        triggered_by="system",
        dry_run=False,
        processed_count=0,
        failed_count=0,
    )
    db_session.add(stale_record)
    await db_session.commit()
    await db_session.refresh(stale_record)
    stale_id = stale_record.id

    record = await expire_posts_job(
        db_session, dry_run=False, triggered_by="system"
    )

    assert record.id != stale_id
    assert record.status == "success"
    db_session.expire_all()
    recovered = await db_session.get(JobRunRecord, stale_id)
    assert recovered.status == "failed"
    assert recovered.finished_at is not None
    assert "租约" in recovered.error_message
