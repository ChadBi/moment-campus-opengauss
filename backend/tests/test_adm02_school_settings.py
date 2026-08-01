"""ADM-02: 学校设置、品牌与地点核验队列验收测试

覆盖：
- ADM-02.1 GET /admin/settings：默认值自动补建；仅 admin 可访问
- ADM-02.1 PUT /admin/settings：部分更新；审计日志记录 old/new/operator
- ADM-02.1 跨校隔离：B 校 admin 修改不会影响 A 校；TEN-02.3 强制 tenant
- ADM-02.1 /schools/current 公开返回品牌字段（site_name/description/brand_color）
- ADM-02.2 地点核验队列：is_verified=false 列表 + 核验通过 + 跨校 404
"""
import json
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.admin_operation_log import AdminOperationLog
from app.models.location import Location
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.school_settings import SchoolSettings
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
    db: AsyncSession, user_id: int, school_id: int, role: str = "admin"
) -> SchoolMembership:
    m = SchoolMembership(
        user_id=user_id,
        school_id=school_id,
        role=role,
        status="active",
        is_default=True,
    )
    db.add(m)
    await db.flush()
    return m


@pytest_asyncio.fixture
async def other_school_with_admin(db_session: AsyncSession) -> dict:
    """另一所学校 + 该校 admin（用于跨校隔离测试）。"""
    school_b = await _create_school(db_session, "B 校", "school-b-adm02")
    admin_b = await _create_user(
        db_session, "b-admin-adm02@example.com", "B 校管理员", school_b.id, role="admin"
    )
    await _create_membership(db_session, admin_b.id, school_b.id, role="admin")
    await db_session.commit()
    return {
        "school_id": school_b.id,
        "admin_id": admin_b.id,
        "admin_email": admin_b.email,
        "headers": {"Authorization": f"Bearer {_make_token(admin_b.id)}"},
    }


# ============================================================
# ADM-02.1: GET /admin/settings
# ============================================================
@pytest.mark.asyncio
async def test_get_settings_auto_creates_default_row(
    client: AsyncClient, admin_headers: dict, test_school: dict, db_session: AsyncSession
):
    """GET /admin/settings 不存在时按默认值自动补建并返回"""
    # 前置：确认无 settings 行
    existing = await db_session.execute(
        select(SchoolSettings).where(SchoolSettings.school_id == test_school["id"])
    )
    assert existing.scalar_one_or_none() is None

    response = await client.get("/api/v1/admin/settings", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()

    # 默认值校验
    assert data["require_review"] is True
    assert data["allow_anonymous"] is True
    assert data["allow_comments"] is True
    assert data["publish_frequency"] == 10
    assert data["image_limit"] == 9
    assert data["default_validity_days"] == 30
    assert data["site_name"] is None
    assert data["description"] is None
    assert data["brand_color"] is None
    assert data["logo_url"] is None
    assert "updated_at" in data

    # DB 已写入
    db_session.expire_all()
    row = (await db_session.execute(
        select(SchoolSettings).where(SchoolSettings.school_id == test_school["id"])
    )).scalar_one()
    assert row.require_review is True
    assert row.publish_frequency == 10


@pytest.mark.asyncio
async def test_get_settings_forbidden_for_normal_user(
    client: AsyncClient, auth_headers: dict
):
    """GET /admin/settings 普通用户 403"""
    response = await client.get("/api/v1/admin/settings", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_settings_unauthorized_without_token(client: AsyncClient):
    """GET /admin/settings 未登录 401"""
    response = await client.get("/api/v1/admin/settings")
    assert response.status_code == 401


# ============================================================
# ADM-02.1: PUT /admin/settings
# ============================================================
@pytest.mark.asyncio
async def test_update_settings_records_audit_log_with_old_new_operator(
    client: AsyncClient, admin_headers: dict, admin_user: dict,
    test_school: dict, db_session: AsyncSession,
):
    """PUT /admin/settings 更新成功 + 审计日志含 old/new/operator"""
    # 先 GET 触发自动补建，拿到旧值
    first = await client.get("/api/v1/admin/settings", headers=admin_headers)
    assert first.status_code == 200
    old = first.json()

    # PUT 修改多个字段
    response = await client.put(
        "/api/v1/admin/settings",
        json={
            "site_name": "此刻校园-江南",
            "description": "江南大学校园信息平台",
            "require_review": False,
            "publish_frequency": 20,
            "image_limit": 6,
            "brand_color": "#1890ff",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["site_name"] == "此刻校园-江南"
    assert data["description"] == "江南大学校园信息平台"
    assert data["require_review"] is False
    assert data["publish_frequency"] == 20
    assert data["image_limit"] == 6
    assert data["brand_color"] == "#1890ff"
    # 未传字段保持原值
    assert data["allow_anonymous"] == old["allow_anonymous"]
    assert data["default_validity_days"] == old["default_validity_days"]

    # 审计日志
    db_session.expire_all()
    log = (await db_session.execute(
        select(AdminOperationLog).where(
            AdminOperationLog.action == "update_school_settings",
            AdminOperationLog.target_type == "school_settings",
            AdminOperationLog.target_id == test_school["id"],
        )
    )).scalar_one()
    assert log.admin_id == admin_user["id"]  # 操作者
    payload = json.loads(log.detail)
    assert "old" in payload and "new" in payload
    assert payload["old"]["require_review"] is True
    assert payload["new"]["require_review"] is False
    assert payload["old"]["publish_frequency"] == 10
    assert payload["new"]["publish_frequency"] == 20
    assert payload["operator"]["id"] == admin_user["id"]
    assert payload["operator"]["email"] == admin_user["email"]
    assert payload["school_id"] == test_school["id"]
    # 字段级 diff 至少包含修改过的字段
    changes_text = " ".join(payload["changes"])
    assert "require_review" in changes_text
    assert "publish_frequency" in changes_text
    assert "brand_color" in changes_text


@pytest.mark.asyncio
async def test_update_settings_no_change_returns_current_without_audit_log(
    client: AsyncClient, admin_headers: dict, test_school: dict, db_session: AsyncSession,
):
    """PUT 传入与原值相同的字段时不写审计日志"""
    # 触发默认值补建
    first = await client.get("/api/v1/admin/settings", headers=admin_headers)
    assert first.status_code == 200

    # 用默认值 PUT（应无变更）
    response = await client.put(
        "/api/v1/admin/settings",
        json={
            "require_review": True,
            "allow_anonymous": True,
            "allow_comments": True,
            "publish_frequency": 10,
            "image_limit": 9,
            "default_validity_days": 30,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200

    # 不应出现审计日志
    logs = (await db_session.execute(
        select(AdminOperationLog).where(
            AdminOperationLog.action == "update_school_settings",
        )
    )).scalars().all()
    assert len(logs) == 0


@pytest.mark.asyncio
async def test_update_settings_validation_error_on_invalid_values(
    client: AsyncClient, admin_headers: dict
):
    """PUT 校验失败：publish_frequency 超上限 / image_limit 为负"""
    resp1 = await client.put(
        "/api/v1/admin/settings",
        json={"publish_frequency": 9999},
        headers=admin_headers,
    )
    assert resp1.status_code == 422

    resp2 = await client.put(
        "/api/v1/admin/settings",
        json={"image_limit": -1},
        headers=admin_headers,
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_update_settings_forbidden_for_normal_user(
    client: AsyncClient, auth_headers: dict
):
    """PUT /admin/settings 普通用户 403"""
    response = await client.put(
        "/api/v1/admin/settings",
        json={"site_name": "hacked"},
        headers=auth_headers,
    )
    assert response.status_code == 403


# ============================================================
# ADM-02.1: 跨校隔离
# ============================================================
@pytest.mark.asyncio
async def test_settings_cross_school_isolation(
    client: AsyncClient, admin_headers: dict, other_school_with_admin: dict,
    test_school: dict, db_session: AsyncSession,
):
    """B 校 admin 修改 B 校设置不影响 A 校；两校 settings 行独立"""
    # A 校 admin 设置 A 校站点名
    a_resp = await client.put(
        "/api/v1/admin/settings",
        json={"site_name": "A 校站点", "brand_color": "#aaaaaa"},
        headers=admin_headers,
    )
    assert a_resp.status_code == 200
    assert a_resp.json()["site_name"] == "A 校站点"

    # B 校 admin 设置 B 校站点名
    b_resp = await client.put(
        "/api/v1/admin/settings",
        json={"site_name": "B 校站点", "brand_color": "#bbbbbb"},
        headers=other_school_with_admin["headers"],
    )
    assert b_resp.status_code == 200
    assert b_resp.json()["site_name"] == "B 校站点"

    # A 校再次 GET，确认未被 B 校操作影响
    a_again = await client.get("/api/v1/admin/settings", headers=admin_headers)
    assert a_again.status_code == 200
    assert a_again.json()["site_name"] == "A 校站点"
    assert a_again.json()["brand_color"] == "#aaaaaa"

    # DB 层两校独立
    db_session.expire_all()
    rows = (await db_session.execute(
        select(SchoolSettings).order_by(SchoolSettings.school_id.asc())
    )).scalars().all()
    by_school = {r.school_id: r for r in rows}
    assert by_school[test_school["id"]].site_name == "A 校站点"
    assert by_school[other_school_with_admin["school_id"]].site_name == "B 校站点"


# ============================================================
# ADM-02.1: /schools/current 公开品牌字段
# ============================================================
@pytest.mark.asyncio
async def test_current_school_returns_brand_fields(
    client: AsyncClient, admin_headers: dict, test_school: dict
):
    """/schools/current 返回 site_name/description/brand_color 来自 school_settings"""
    # 先设置品牌字段
    await client.put(
        "/api/v1/admin/settings",
        json={
            "site_name": "此刻校园-江南",
            "description": "江南大学校园信息平台",
            "brand_color": "#1890ff",
        },
        headers=admin_headers,
    )

    # 公开接口读取
    response = await client.get(
        "/api/v1/schools/current",
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["site_name"] == "此刻校园-江南"
    assert data["description"] == "江南大学校园信息平台"
    assert data["brand_color"] == "#1890ff"


@pytest.mark.asyncio
async def test_current_school_brand_fields_none_when_no_settings(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """无 school_settings 行时 /schools/current 的品牌字段为 None"""
    # 前置：确认无 settings 行（test_school fixture 不自动创建 settings）
    existing = (await db_session.execute(
        select(SchoolSettings).where(SchoolSettings.school_id == test_school["id"])
    )).scalar_one_or_none()
    assert existing is None

    response = await client.get(
        "/api/v1/schools/current",
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["site_name"] is None
    assert data["description"] is None
    assert data["brand_color"] is None


# ============================================================
# ADM-02.2: 地点核验队列（验收已实现路由仍可用）
# ============================================================
@pytest.mark.asyncio
async def test_location_verification_queue_filter_and_verify(
    client: AsyncClient, admin_headers: dict, test_school: dict, db_session: AsyncSession
):
    """地点核验队列：列出 is_verified=false；核验通过后状态翻转"""
    loc1 = Location(
        school_id=test_school["id"], name="待核验地点A",
        latitude=31.49, longitude=120.27, is_verified=False,
    )
    loc2 = Location(
        school_id=test_school["id"], name="已核验地点B",
        latitude=31.50, longitude=120.28, is_verified=True,
    )
    db_session.add_all([loc1, loc2])
    await db_session.commit()

    # 列表筛选未核验
    resp = await client.get(
        "/api/v1/admin/locations",
        params={"is_verified": "false"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["id"] for i in items]
    assert loc1.id in ids
    assert loc2.id not in ids

    # 核验通过
    verify = await client.put(
        f"/api/v1/admin/locations/{loc1.id}/verify",
        params={"is_verified": "true"},
        headers=admin_headers,
    )
    assert verify.status_code == 200
    assert verify.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_location_verify_cross_school_404(
    client: AsyncClient, admin_headers: dict, other_school_with_admin: dict,
    db_session: AsyncSession,
):
    """A 校 admin 核验 B 校地点返回 404（不暴露存在性）"""
    loc_b = Location(
        school_id=other_school_with_admin["school_id"],
        name="B 校地点",
        latitude=32.0, longitude=121.0, is_verified=False,
    )
    db_session.add(loc_b)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/admin/locations/{loc_b.id}/verify",
        params={"is_verified": "true"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
