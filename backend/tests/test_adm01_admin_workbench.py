"""ADM-01: 双层后台、校级治理工作台与事务动作测试

覆盖：
- ADM-01.1：GET /admin/todos 校级待办统计（7 类卡片 + 跳转路径 + 租户隔离 + 权限）
- ADM-01.2：GET /admin/posts/{id} 审核详情（管理专用，pending 可见 + 作者历史 + 跨校 404）
- ADM-01.2：GET /platform/overview 平台首页跨校统计（仅 super_admin，普通 admin 403）
- ADM-01.3：GET /admin/review/templates 通过/驳回原因模板
- ADM-01.4：批量审核逐项返回成功/失败/原因（failed_items 不静默跳过）；
            审核动作/状态变化/通知同事务提交
- ADM-01.5：治理工作台（报告队列筛选 + 处理动作同事务：报告状态/帖子状态/通知/日志）
- ADM-01.6：地点核验队列与核验/取消核验（跨校 404）
"""
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.post_status import PostStatus
from app.core.security import create_access_token, get_password_hash
from app.models.admin_operation_log import AdminOperationLog
from app.models.job_run_record import JobRunRecord
from app.models.location import Location
from app.models.notification import Notification
from app.models.post import Post
from app.models.post_change_report import PostChangeReport
from app.models.report import Report
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User


# ============================================================
# 辅助函数与 fixtures
# ============================================================
def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


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


@pytest_asyncio.fixture
async def other_school_post(
    db_session: AsyncSession, test_category: dict, test_post_type: dict
) -> dict:
    """另一所学校 + 该校作者 + 一条待审核帖子（用于跨校 404 测试）。"""
    school_b = await _create_school(db_session, "B 校", "school-b-adm01")
    author_b = await _create_user(db_session, "b-author@example.com", "B 校作者", school_b.id)
    await _create_membership(db_session, author_b.id, school_b.id, "member")
    from app.models.category import Category
    cat_b = Category(
        school_id=school_b.id, name="B 校分类", code="b-cat", icon="📚",
        default_validity_days=30, is_active=True,
    )
    db_session.add(cat_b)
    await db_session.flush()
    post_b = Post(
        user_id=author_b.id,
        school_id=school_b.id,
        category_id=cat_b.id,
        post_type_id=test_post_type["id"],
        title="B 校待审核帖子",
        content="B 校待审核帖子内容，至少十个字符",
        status=PostStatus.PENDING,
    )
    db_session.add(post_b)
    await db_session.flush()
    loc_b = Location(
        school_id=school_b.id, name="B 校未核验地点",
        latitude=32.0, longitude=121.0, is_verified=False,
    )
    db_session.add(loc_b)
    await db_session.commit()
    return {
        "school_id": school_b.id,
        "post_id": post_b.id,
        "location_id": loc_b.id,
    }


@pytest_asyncio.fixture
async def super_admin(db_session: AsyncSession, test_school: dict) -> dict:
    """平台超管（直接 DB 创建）。"""
    sa = await _create_user(
        db_session, "sa-adm01@example.com", "平台超管", test_school["id"], role="super_admin"
    )
    await db_session.commit()
    return {"id": sa.id, "headers": {"Authorization": f"Bearer {_make_token(sa.id)}"}}


# ============================================================
# ADM-01.1: 校级待办统计
# ============================================================
@pytest.mark.asyncio
async def test_admin_todos_returns_seven_cards_with_counts(
    client: AsyncClient,
    admin_headers: dict,
    auth_headers: dict,
    second_auth_headers: dict,
    test_post: dict,
    db_session: AsyncSession,
    test_school: dict,
):
    """ADM-01.1: 待办统计返回 7 类卡片，计数正确且每项含跳转队列路径"""
    # 制造待办数据：1 待审核帖（fixture）+ 1 待处理举报 + 1 未核验地点 + 3 类问题报告 + 1 失败任务
    post_id = test_post["id"]
    # second_user 举报该帖（待处理）
    reporter = await db_session.execute(select(User).where(User.email == "seconduser@example.com"))
    reporter_id = reporter.scalar_one().id
    db_session.add(Report(
        post_id=post_id, reporter_id=reporter_id,
        report_type="spam", description="垃圾信息测试", status="pending",
    ))
    # 未核验地点
    db_session.add(Location(
        school_id=test_school["id"], name="未核验食堂",
        latitude=31.5, longitude=120.3, is_verified=False,
    ))
    # 3 类未结案问题报告
    for rtype in ("expiration_report", "conflict_report", "update"):
        db_session.add(PostChangeReport(
            post_id=post_id, reporter_id=reporter_id,
            report_type=rtype, description=f"{rtype} 测试", status="open",
        ))
    # 24h 内失败任务
    db_session.add(JobRunRecord(
        job_name="expire_posts", status="failed", started_at=datetime.now(),
        triggered_by="scheduler",
    ))
    await db_session.commit()

    response = await client.get("/api/v1/admin/todos", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["pending_posts"] == 1
    assert data["pending_reports"] == 1
    assert data["unverified_locations"] == 1
    assert data["expiration_reports"] == 1
    assert data["conflict_reports"] == 1
    assert data["update_suggestions"] == 1
    assert data["failed_jobs"] == 1
    assert data["total"] == 7

    # 7 张卡片均含 key/label/count/queue_url，路径带筛选参数
    assert len(data["items"]) == 7
    url_by_key = {item["key"]: item["queue_url"] for item in data["items"]}
    assert url_by_key["pending_posts"] == "/admin/review"
    assert "status=pending" in url_by_key["pending_reports"]
    assert "verified=false" in url_by_key["unverified_locations"]
    assert "type=expiration_report" in url_by_key["expiration_reports"]
    assert "type=conflict_report" in url_by_key["conflict_reports"]
    assert "type=update" in url_by_key["update_suggestions"]
    assert "status=failed" in url_by_key["failed_jobs"]


@pytest.mark.asyncio
async def test_admin_todos_tenant_isolation(
    client: AsyncClient,
    admin_headers: dict,
    other_school_post: dict,
):
    """ADM-01.1: 他校待办数据不计入本校统计（TEN-02.3）"""
    response = await client.get("/api/v1/admin/todos", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    # B 校有 1 待审核帖 + 1 未核验地点，但本校统计应为 0
    assert data["pending_posts"] == 0
    assert data["unverified_locations"] == 0


@pytest.mark.asyncio
async def test_admin_todos_forbidden_for_normal_user(
    client: AsyncClient, auth_headers: dict
):
    """ADM-01.1: 普通用户访问校级待办统计返回 403"""
    response = await client.get("/api/v1/admin/todos", headers=auth_headers)
    assert response.status_code == 403


# ============================================================
# ADM-01.2: 审核详情（管理专用接口）
# ============================================================
@pytest.mark.asyncio
async def test_admin_post_detail_visible_for_pending_with_author_history(
    client: AsyncClient,
    admin_headers: dict,
    test_post: dict,
):
    """ADM-01.2: 管理专用详情对 pending 帖子可见（公开详情不可见），含作者历史与治理概况"""
    response = await client.get(
        f"/api/v1/admin/posts/{test_post['id']}", headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_post["id"]
    assert data["status"] == "pending"
    assert data["title"] == test_post["title"]
    assert data["content"]
    assert data["author_name"] == "测试用户"
    assert data["category_name"] == "失物招领"
    # 作者历史统计
    assert data["author_history"]["total_posts"] >= 1
    # 治理概况字段存在
    assert "open_change_reports" in data
    assert "pending_user_reports" in data


@pytest.mark.asyncio
async def test_admin_post_detail_cross_school_returns_404(
    client: AsyncClient, admin_headers: dict, other_school_post: dict
):
    """ADM-01.2: 跨校帖子详情统一返回 404（不泄露存在性）"""
    response = await client.get(
        f"/api/v1/admin/posts/{other_school_post['post_id']}", headers=admin_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_post_detail_forbidden_for_normal_user(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """ADM-01.2: 普通用户访问管理专用详情返回 403"""
    response = await client.get(
        f"/api/v1/admin/posts/{test_post['id']}", headers=auth_headers
    )
    assert response.status_code == 403


# ============================================================
# ADM-01.2: 平台首页跨校统计（仅 super_admin）
# ============================================================
@pytest.mark.asyncio
async def test_platform_overview_super_admin_only(
    client: AsyncClient,
    super_admin: dict,
    admin_headers: dict,
    auth_headers: dict,
):
    """ADM-01.2: 平台首页仅 super_admin 可访问；普通 admin 与 user 均 403"""
    ok = await client.get("/api/v1/platform/overview", headers=super_admin["headers"])
    assert ok.status_code == 200

    by_admin = await client.get("/api/v1/platform/overview", headers=admin_headers)
    assert by_admin.status_code == 403

    by_user = await client.get("/api/v1/platform/overview", headers=auth_headers)
    assert by_user.status_code == 403


@pytest.mark.asyncio
async def test_platform_overview_aggregates_cross_school_stats(
    client: AsyncClient,
    super_admin: dict,
    test_post: dict,
    other_school_post: dict,
    test_school: dict,
):
    """ADM-01.2: 平台首页聚合学校数/活跃成员/内容治理量/AI 降级率/异常租户/开通记录"""
    response = await client.get("/api/v1/platform/overview", headers=super_admin["headers"])
    assert response.status_code == 200
    data = response.json()

    # 学校数：test_school + B 校
    assert data["school_total"] >= 2
    assert data["school_active"] >= 2
    # 活跃成员（注册用户默认 active membership）
    assert data["active_members"] >= 1
    # 内容治理量：本校 1 待审核 + B 校 1 待审核
    assert data["pending_posts"] >= 2
    assert data["governance_total"] >= data["pending_posts"]
    # AI 调用降级率结构（无调用时总量 0、比率 0）
    assert isinstance(data["ai_stats"], list)
    assert data["ai_calls_total"] >= 0
    assert 0.0 <= data["ai_fallback_rate"] <= 1.0
    # 异常租户/开通记录为列表结构
    assert isinstance(data["abnormal_tenants"], list)
    assert isinstance(data["activation_records"], list)


# ============================================================
# ADM-01.3: 审核原因模板
# ============================================================
@pytest.mark.asyncio
async def test_review_templates_returns_approve_and_reject(
    client: AsyncClient, admin_headers: dict
):
    """ADM-01.3: 原因模板含通过/驳回两组，每项含 code/label/text"""
    response = await client.get("/api/v1/admin/review/templates", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["approve"]) >= 1
    assert len(data["reject"]) >= 1
    for tpl in data["approve"] + data["reject"]:
        assert tpl["code"] and tpl["label"] and tpl["text"]


@pytest.mark.asyncio
async def test_review_templates_forbidden_for_normal_user(
    client: AsyncClient, auth_headers: dict
):
    """ADM-01.3: 普通用户访问原因模板返回 403"""
    response = await client.get("/api/v1/admin/review/templates", headers=auth_headers)
    assert response.status_code == 403


# ============================================================
# ADM-01.4: 批量操作逐项结果 + 审核事务
# ============================================================
@pytest.mark.asyncio
async def test_batch_approve_returns_failed_items_with_reasons(
    client: AsyncClient,
    admin_headers: dict,
    test_post: dict,
    db_session: AsyncSession,
    test_category: dict,
    test_post_type: dict,
    test_school: dict,
):
    """ADM-01.4: 批量通过逐项返回成功/失败/原因，不静默跳过"""
    # 一条已发布帖子（非 pending，应失败）+ 不存在 ID（应失败）+ fixture 待审核帖（应成功）
    author = (await db_session.execute(
        select(User).where(User.email == "testuser@example.com")
    )).scalar_one()
    published_post = Post(
        user_id=author.id,
        school_id=test_school["id"],
        category_id=test_category["id"],
        post_type_id=test_post_type["id"],
        title="已发布帖子",
        content="已发布帖子内容，至少十个字符",
        status=PostStatus.PUBLISHED,
    )
    db_session.add(published_post)
    await db_session.commit()

    response = await client.post(
        "/api/v1/admin/posts/batch-approve",
        json={"post_ids": [test_post["id"], published_post.id, 999999], "reason": "批量通过"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["success"] == 1
    assert data["failed"] == 2
    # failed_items 逐项含 id + 原因
    reasons = {item["id"]: item["reason"] for item in data["failed_items"]}
    assert 999999 in reasons and "不存在" in reasons[999999]
    assert published_post.id in reasons and "待审核" in reasons[published_post.id]


@pytest.mark.asyncio
async def test_approve_post_transaction_creates_status_log_and_notification(
    client: AsyncClient,
    admin_headers: dict,
    auth_headers: dict,
    test_post: dict,
    db_session: AsyncSession,
):
    """ADM-01.4: 审核通过 → 帖子状态 + 操作日志 + 作者通知在同一事务提交"""
    response = await client.put(
        f"/api/v1/admin/posts/{test_post['id']}/approve",
        json={"reason": "内容真实有效"},
        headers=admin_headers,
    )
    assert response.status_code == 200

    # 状态变化
    post = (await db_session.execute(
        select(Post).where(Post.id == test_post["id"])
    )).scalar_one()
    assert post.status == PostStatus.PUBLISHED

    # 操作日志（同事务）
    log = (await db_session.execute(
        select(AdminOperationLog).where(
            AdminOperationLog.action == "approve_post",
            AdminOperationLog.target_id == test_post["id"],
        )
    )).scalar_one_or_none()
    assert log is not None

    # 作者通知（同事务）
    notifications = await client.get("/api/v1/notifications", headers=auth_headers)
    items = notifications.json()["items"]
    audit = next(
        (n for n in items if n["type"] == "audit" and n["target_id"] == test_post["id"]),
        None,
    )
    assert audit is not None
    assert "审核" in audit["title"]


# ============================================================
# ADM-01.5: 治理工作台
# ============================================================
@pytest_asyncio.fixture
async def published_post_with_reports(
    db_session: AsyncSession,
    test_school: dict,
    test_category: dict,
    test_post_type: dict,
    test_post: dict,
    second_user: dict,
) -> dict:
    """一条已发布帖子 + second_user 提交的过期报告与更新建议（均 open）。"""
    author = (await db_session.execute(
        select(User).where(User.email == "testuser@example.com")
    )).scalar_one()
    reporter = (await db_session.execute(
        select(User).where(User.email == "seconduser@example.com")
    )).scalar_one()
    post = Post(
        user_id=author.id,
        school_id=test_school["id"],
        category_id=test_category["id"],
        post_type_id=test_post_type["id"],
        title="已发布的讲座信息",
        content="已发布的讲座信息内容，至少十个字符",
        status=PostStatus.PUBLISHED,
    )
    db_session.add(post)
    await db_session.flush()
    exp_report = PostChangeReport(
        post_id=post.id, reporter_id=reporter.id,
        report_type="expiration_report", description="讲座已结束", status="open",
    )
    upd_report = PostChangeReport(
        post_id=post.id, reporter_id=reporter.id,
        report_type="update", description="地点改到 2 教", status="open",
    )
    db_session.add_all([exp_report, upd_report])
    await db_session.commit()
    return {
        "post_id": post.id,
        "author_id": author.id,
        "reporter_id": reporter.id,
        "expiration_report_id": exp_report.id,
        "update_report_id": upd_report.id,
    }


@pytest.mark.asyncio
async def test_governance_reports_queue_filtered_by_type_and_status(
    client: AsyncClient,
    admin_headers: dict,
    published_post_with_reports: dict,
):
    """ADM-01.5: 治理报告队列支持按类型/状态筛选（待办卡片跳转入口）"""
    # 全部
    all_resp = await client.get("/api/v1/admin/governance/reports", headers=admin_headers)
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 2

    # 按类型筛选
    exp_resp = await client.get(
        "/api/v1/admin/governance/reports",
        params={"report_type": "expiration_report", "status": "open"},
        headers=admin_headers,
    )
    data = exp_resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["report_type"] == "expiration_report"
    assert item["post_id"] == published_post_with_reports["post_id"]
    assert item["post_title"] == "已发布的讲座信息"
    assert item["reporter_name"] == "第二用户"
    assert item["status"] == "open"


@pytest.mark.asyncio
async def test_handle_governance_report_mark_expired_same_transaction(
    client: AsyncClient,
    admin_headers: dict,
    auth_headers: dict,
    second_auth_headers: dict,
    published_post_with_reports: dict,
    db_session: AsyncSession,
):
    """ADM-01.5: 确认过期 → 报告状态 + 帖子状态 + 通知 + 日志同事务提交"""
    rid = published_post_with_reports["expiration_report_id"]
    pid = published_post_with_reports["post_id"]

    response = await client.put(
        f"/api/v1/admin/governance/reports/{rid}/handle",
        json={"action": "mark_expired", "reason": "核实讲座已结束"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["post_status"] == PostStatus.EXPIRED
    assert data["handler_name"] == "管理员"

    # 帖子状态变化
    post = (await db_session.execute(select(Post).where(Post.id == pid))).scalar_one()
    assert post.status == PostStatus.EXPIRED

    # 操作日志（同事务）
    log = (await db_session.execute(
        select(AdminOperationLog).where(
            AdminOperationLog.action == "governance_mark_expired",
            AdminOperationLog.target_id == rid,
        )
    )).scalar_one_or_none()
    assert log is not None

    # 报告人收到处理通知（同事务）
    reporter_notifs = await client.get("/api/v1/notifications", headers=second_auth_headers)
    r_items = reporter_notifs.json()["items"]
    r_notif = next(
        (n for n in r_items if n["target_id"] == pid and "已处理" in n["title"]), None
    )
    assert r_notif is not None

    # 作者收到状态变更通知（作者 ≠ 报告人，同事务）
    author_notifs = await client.get("/api/v1/notifications", headers=auth_headers)
    a_items = author_notifs.json()["items"]
    a_notif = next(
        (n for n in a_items if n["target_id"] == pid and "状态变更" in n["title"]), None
    )
    assert a_notif is not None
    assert "已过期" in a_notif["content"]


@pytest.mark.asyncio
async def test_handle_governance_report_dismiss_keeps_post_status(
    client: AsyncClient,
    admin_headers: dict,
    published_post_with_reports: dict,
    db_session: AsyncSession,
):
    """ADM-01.5: 驳回报告不改变帖子状态，报告转 dismissed"""
    rid = published_post_with_reports["update_report_id"]
    pid = published_post_with_reports["post_id"]

    response = await client.put(
        f"/api/v1/admin/governance/reports/{rid}/handle",
        json={"action": "dismiss", "reason": "信息不准确"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"

    post = (await db_session.execute(select(Post).where(Post.id == pid))).scalar_one()
    assert post.status == PostStatus.PUBLISHED

    # 已结案报告不能重复处理
    again = await client.put(
        f"/api/v1/admin/governance/reports/{rid}/handle",
        json={"action": "resolve", "reason": "重复处理"},
        headers=admin_headers,
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_governance_reports_cross_school_not_listed(
    client: AsyncClient,
    admin_headers: dict,
    other_school_post: dict,
    db_session: AsyncSession,
):
    """ADM-01.5: 他校报告不出现在本校队列；跨校处理返回 404"""
    # 在 B 校帖子上直接造一条报告
    db_session.add(PostChangeReport(
        post_id=other_school_post["post_id"], reporter_id=1,
        report_type="expiration_report", description="B 校报告", status="open",
    ))
    await db_session.commit()

    queue = await client.get("/api/v1/admin/governance/reports", headers=admin_headers)
    assert queue.json()["total"] == 0

    # 跨校处理 404
    cross_report = (await db_session.execute(
        select(PostChangeReport).where(
            PostChangeReport.post_id == other_school_post["post_id"]
        )
    )).scalar_one()
    resp = await client.put(
        f"/api/v1/admin/governance/reports/{cross_report.id}/handle",
        json={"action": "resolve", "reason": "跨校处理"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


# ============================================================
# ADM-01.6: 地点核验
# ============================================================
@pytest.mark.asyncio
async def test_admin_locations_list_filter_and_verify(
    client: AsyncClient,
    admin_headers: dict,
    test_school: dict,
    db_session: AsyncSession,
):
    """ADM-01.6: 地点管理列表按核验状态筛选；核验通过更新状态并记录日志"""
    loc = Location(
        school_id=test_school["id"], name="新南门",
        latitude=31.49, longitude=120.27, is_verified=False,
    )
    db_session.add(loc)
    await db_session.commit()

    # 筛选未核验
    unverified = await client.get(
        "/api/v1/admin/locations",
        params={"is_verified": "false"},
        headers=admin_headers,
    )
    assert unverified.status_code == 200
    items = unverified.json()["items"]
    assert any(i["id"] == loc.id and i["is_verified"] is False for i in items)

    # 核验通过
    verify = await client.put(
        f"/api/v1/admin/locations/{loc.id}/verify",
        params={"is_verified": "true"},
        headers=admin_headers,
    )
    assert verify.status_code == 200
    assert verify.json()["is_verified"] is True

    # 操作日志
    log = (await db_session.execute(
        select(AdminOperationLog).where(
            AdminOperationLog.action == "verify_location",
            AdminOperationLog.target_id == loc.id,
        )
    )).scalar_one_or_none()
    assert log is not None

    # 重复核验返回 400
    again = await client.put(
        f"/api/v1/admin/locations/{loc.id}/verify",
        params={"is_verified": "true"},
        headers=admin_headers,
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_verify_location_cross_school_returns_404(
    client: AsyncClient, admin_headers: dict, other_school_post: dict
):
    """ADM-01.6: 跨校地点核验统一返回 404"""
    response = await client.put(
        f"/api/v1/admin/locations/{other_school_post['location_id']}/verify",
        params={"is_verified": "true"},
        headers=admin_headers,
    )
    assert response.status_code == 404
