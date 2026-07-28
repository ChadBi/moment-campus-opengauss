"""COM-02：套餐分配、初始化导入、额度告警、开通清单、激活漏斗与校级用量页 测试。

覆盖：
- COM-02.1：GET /platform/schools/{id}/subscription-history 套餐历史变更
- COM-02.1：GET /platform/schools/{id}/alerts 学校额度告警
- COM-02.1：GET /platform/alerts 全平台告警汇总
- COM-02.2：GET /platform/import-template 下载 CSV 模板
- COM-02.2：POST /platform/schools/{id}/import?dry_run=true 预览
- COM-02.2：POST /platform/schools/{id}/import 提交（事务保护）
- COM-02.2：任一行失败整批不提交
- COM-02.3：GET /admin/usage 校级用量页
- COM-02.4：GET /platform/activation-funnel 激活漏斗
- 权限：普通 user 访问 platform 路由 403
"""
import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school import School
from app.models.school_subscription import SchoolSubscription
from app.models.user import User


# ============================================================
# fixtures
# ============================================================
@pytest_asyncio.fixture
async def super_admin_user(
    client: AsyncClient, db_session: AsyncSession, test_school: dict
) -> dict:
    """注册一名 super_admin 用户并返回其 token + id。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "com02-admin@example.com",
            "nickname": "COM02超管",
            "password": "superpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    result = await db_session.execute(
        select(User).where(User.email == "com02-admin@example.com")
    )
    user = result.scalar_one()
    user.role = "super_admin"
    await db_session.commit()

    return {
        "email": "com02-admin@example.com",
        "password": "superpassword123",
        "school_id": test_school["id"],
        "access_token": data["access_token"],
        "id": user.id,
    }


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: dict) -> dict:
    return {"Authorization": f"Bearer {super_admin_user['access_token']}"}


@pytest_asyncio.fixture
async def import_ready_school(
    db_session: AsyncSession, test_school: dict
) -> dict:
    """为导入测试准备学校：已有分类。

    test_school fixture 已创建学校并分配 operations 订阅。
    test_category fixture 创建了 lost-found 分类。
    """
    # 确保 lost-found 分类存在并属于 test_school
    cat = (await db_session.execute(
        select(Category).where(
            Category.school_id == test_school["id"],
            Category.code == "lost-found",
        )
    )).scalar_one_or_none()
    if cat is None:
        cat = Category(
            name="失物招领", code="lost-found", icon="🔍",
            default_validity_days=30, is_active=True,
            school_id=test_school["id"],
        )
        db_session.add(cat)
        await db_session.commit()
        await db_session.refresh(cat)

    return {
        "school_id": test_school["id"],
        "category_id": cat.id,
        "category_code": cat.code,
    }


# ============================================================
# COM-02.1：套餐历史变更
# ============================================================
@pytest.mark.asyncio
async def test_subscription_history(
    client: AsyncClient,
    super_admin_headers: dict,
    test_school: dict,
):
    """GET /platform/schools/{id}/subscription-history 返回历史订阅列表（含 school_name）。"""
    response = await client.get(
        f"/api/v1/platform/schools/{test_school['id']}/subscription-history",
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    # test_school fixture 已分配 operations 订阅
    assert data["total"] >= 1
    assert data["items"][0]["plan_code"] == "operations"
    # Task 1.5: 历史订阅响应也应包含 school_name
    assert data["items"][0]["school_name"] == test_school["name"]


@pytest.mark.asyncio
async def test_subscription_history_forbidden_for_user(
    client: AsyncClient,
    auth_headers: dict,
    test_school: dict,
):
    """普通用户访问 subscription-history 被 403 拒绝。"""
    response = await client.get(
        f"/api/v1/platform/schools/{test_school['id']}/subscription-history",
        headers=auth_headers,
    )
    assert response.status_code == 403


# ============================================================
# COM-02.1：学校额度告警
# ============================================================
@pytest.mark.asyncio
async def test_school_alerts(
    client: AsyncClient,
    super_admin_headers: dict,
    test_school: dict,
):
    """GET /platform/schools/{id}/alerts 返回学校告警与额度余量。"""
    response = await client.get(
        f"/api/v1/platform/schools/{test_school['id']}/alerts",
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["school_id"] == test_school["id"]
    assert "entitlements" in data
    assert "alerts" in data
    assert "alerts_count" in data
    # operations 档有 4 项权益
    assert len(data["entitlements"]) == 4


@pytest.mark.asyncio
async def test_all_platform_alerts(
    client: AsyncClient,
    super_admin_headers: dict,
):
    """GET /platform/alerts 返回全平台告警汇总。"""
    response = await client.get(
        "/api/v1/platform/alerts",
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "alert_schools_count" in data


# ============================================================
# COM-02.2：下载导入模板
# ============================================================
@pytest.mark.asyncio
async def test_download_import_template(
    client: AsyncClient,
    super_admin_headers: dict,
):
    """GET /platform/import-template 返回 CSV 模板。"""
    response = await client.get(
        "/api/v1/platform/import-template",
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    content = response.text
    # 模板首行须含 type 列
    assert "type" in content
    assert "location" in content
    assert "post" in content


@pytest.mark.asyncio
async def test_download_template_forbidden_for_user(
    client: AsyncClient,
    auth_headers: dict,
):
    """普通用户下载模板被 403 拒绝。"""
    response = await client.get(
        "/api/v1/platform/import-template",
        headers=auth_headers,
    )
    assert response.status_code == 403


# ============================================================
# COM-02.2：批量导入预览（dry_run）
# ============================================================
@pytest.mark.asyncio
async def test_import_preview_dry_run(
    client: AsyncClient,
    super_admin_headers: dict,
    import_ready_school: dict,
):
    """POST /platform/schools/{id}/import?dry_run=true 预览不写库。"""
    school_id = import_ready_school["school_id"]
    rows = [
        {
            "type": "location",
            "name": "图书馆北门",
            "latitude": 31.4912,
            "longitude": 120.2705,
            "floor": "1",
            "building": "图书馆",
        },
        {
            "type": "post",
            "title": "失物招领测试",
            "content": "在图书馆北门丢失黑色钱包一个",
            "category_code": "lost-found",
            "location_ref": "1",
            "is_anonymous": False,
        },
    ]
    response = await client.post(
        f"/api/v1/platform/schools/{school_id}/import?dry_run=true",
        json={"rows": rows},
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "preview"
    result = data["result"]
    assert result["total_rows"] == 2
    assert result["locations_count"] == 1
    assert result["posts_count"] == 1
    assert result["valid"] is True
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_import_preview_with_errors(
    client: AsyncClient,
    super_admin_headers: dict,
    import_ready_school: dict,
):
    """预览时含错误行：type 非法 + 缺字段。"""
    school_id = import_ready_school["school_id"]
    rows = [
        {"type": "invalid_type", "name": "xxx"},
        {"type": "location"},  # 缺 name/latitude/longitude
        {
            "type": "post",
            "title": "缺分类",
            "content": "内容不足十个字吗",
            "category_code": "non-existent",
        },
    ]
    response = await client.post(
        f"/api/v1/platform/schools/{school_id}/import?dry_run=true",
        json={"rows": rows},
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "preview"
    result = data["result"]
    assert result["valid"] is False
    assert len(result["errors"]) > 0


# ============================================================
# COM-02.2：批量导入提交（事务保护）
# ============================================================
@pytest.mark.asyncio
async def test_import_commit_success(
    client: AsyncClient,
    super_admin_headers: dict,
    import_ready_school: dict,
    db_session: AsyncSession,
):
    """POST /platform/schools/{id}/import 提交成功写库。"""
    school_id = import_ready_school["school_id"]
    rows = [
        {
            "type": "location",
            "name": "测试地点A",
            "latitude": 31.4912,
            "longitude": 120.2705,
        },
        {
            "type": "post",
            "title": "首批内容测试帖",
            "content": "这是导入的首批内容测试帖",
            "category_code": "lost-found",
            "location_ref": "1",
            "is_anonymous": False,
        },
    ]
    response = await client.post(
        f"/api/v1/platform/schools/{school_id}/import",
        json={"rows": rows},
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "commit"
    result = data["result"]
    assert result["locations_created"] == 1
    assert result["posts_created"] == 1
    assert result["total_created"] == 2
    assert "batch_id" in result

    # 验证数据库确实写入
    loc_count = (await db_session.execute(
        select(Location).where(
            Location.school_id == school_id,
            Location.name == "测试地点A",
        )
    )).scalars().all()
    assert len(loc_count) == 1

    post_count = (await db_session.execute(
        select(Post).where(
            Post.school_id == school_id,
            Post.title == "首批内容测试帖",
        )
    )).scalars().all()
    assert len(post_count) == 1


@pytest.mark.asyncio
async def test_import_commit_rollback_on_error(
    client: AsyncClient,
    super_admin_headers: dict,
    import_ready_school: dict,
    db_session: AsyncSession,
):
    """提交时含错误行：预览阶段就返回 errors，不写库。"""
    school_id = import_ready_school["school_id"]
    rows = [
        {
            "type": "location",
            "name": "回滚测试地点",
            "latitude": 31.4912,
            "longitude": 120.2705,
        },
        {
            "type": "post",
            # 故意缺 content
            "title": "缺内容",
            "category_code": "lost-found",
        },
    ]
    response = await client.post(
        f"/api/v1/platform/schools/{school_id}/import",
        json={"rows": rows},
        headers=super_admin_headers,
    )
    # 含错误时返回 preview mode（不提交）
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "preview"
    assert data["result"]["valid"] is False

    # 验证数据库未写入
    loc_count = (await db_session.execute(
        select(Location).where(
            Location.school_id == school_id,
            Location.name == "回滚测试地点",
        )
    )).scalars().all()
    assert len(loc_count) == 0


@pytest.mark.asyncio
async def test_import_forbidden_for_user(
    client: AsyncClient,
    auth_headers: dict,
    test_school: dict,
):
    """普通用户调用导入被 403 拒绝。"""
    response = await client.post(
        f"/api/v1/platform/schools/{test_school['id']}/import?dry_run=true",
        json={"rows": [{"type": "location", "name": "x", "latitude": 0, "longitude": 0}]},
        headers=auth_headers,
    )
    assert response.status_code == 403


# ============================================================
# COM-02.3：校级用量页
# ============================================================
@pytest.mark.asyncio
async def test_admin_usage_endpoint(
    client: AsyncClient,
    admin_headers: dict,
):
    """GET /admin/usage 返回校级用量数据（admin 可访问）。"""
    response = await client.get(
        "/api/v1/admin/usage",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "school_id" in data
    assert "entitlements" in data
    assert "alerts" in data
    assert "alerts_count" in data
    assert "stats" in data
    assert "members_count" in data["stats"]
    assert "posts_count" in data["stats"]
    assert "ai_calls_today" in data["stats"]
    assert "storage_used_mb" in data["stats"]
    assert "last_updated_at" in data["stats"]
    assert "stat_basis" in data["stats"]
    assert "contact_platform_hint" in data
    # test_school 有 operations 订阅
    assert data["plan_code"] == "operations"


@pytest.mark.asyncio
async def test_admin_usage_forbidden_for_user(
    client: AsyncClient,
    auth_headers: dict,
):
    """普通用户访问 /admin/usage 被 403 拒绝。"""
    response = await client.get(
        "/api/v1/admin/usage",
        headers=auth_headers,
    )
    assert response.status_code == 403


# ============================================================
# COM-02.4：激活漏斗
# ============================================================
@pytest.mark.asyncio
async def test_activation_funnel(
    client: AsyncClient,
    super_admin_headers: dict,
    test_school: dict,
):
    """GET /platform/activation-funnel 返回各校激活阶段。"""
    response = await client.get(
        "/api/v1/platform/activation-funnel",
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "activated_count" in data
    assert "avg_activated_stage" in data
    assert data["total"] >= 1
    # 每条 items 须含 checklist + activated_stage
    for item in data["items"]:
        assert "school_id" in item
        assert "checklist" in item
        assert "activated" in item
        assert "activated_stage" in item
        assert 0 <= item["activated_stage"] <= 5


@pytest.mark.asyncio
async def test_activation_funnel_with_keyword_filter(
    client: AsyncClient,
    super_admin_headers: dict,
    test_school: dict,
):
    """激活漏斗支持 keyword 搜索。"""
    response = await client.get(
        "/api/v1/platform/activation-funnel?keyword=测试",
        headers=super_admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    # test_school name 含"测试"
    assert data["total"] >= 1
    assert "测试" in data["items"][0]["school_name"]


@pytest.mark.asyncio
async def test_activation_funnel_forbidden_for_user(
    client: AsyncClient,
    auth_headers: dict,
):
    """普通用户访问激活漏斗被 403 拒绝。"""
    response = await client.get(
        "/api/v1/platform/activation-funnel",
        headers=auth_headers,
    )
    assert response.status_code == 403
