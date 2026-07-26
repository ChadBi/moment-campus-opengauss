"""TEN-04: 平台学校管理 + 开通清单 + 暂停恢复 + 平台审计 测试。

覆盖：
- TEN-04.1：POST /platform/schools 创建学校（含默认分类复制/设置/邀请/订阅）
- TEN-04.1：GET /platform/schools 平台学校列表（含订阅/激活/成员/内容数）
- TEN-04.1：GET /platform/schools/{id} 学校详情（含开通清单）
- TEN-04.1：PUT /platform/schools/{id}/status 启用/暂停学校
- TEN-04.2：开通清单 5 项 bool
- TEN-04.2：暂停学校后写接口拒绝（tenant.py 404）
- TEN-04.3：平台审计日志记录（school.create / school.suspend / school.reactivate / subscription.assign）
- TEN-04.3：GET /platform/audit 审计日志列表
- 权限：普通 user 访问 platform 路由 403
"""
import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.platform_audit import PlatformAuditLog
from app.models.school import School
from app.models.school_invitation import SchoolInvitation
from app.models.school_settings import SchoolSettings
from app.models.school_subscription import SchoolSubscription


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
            "email": "platform-admin@example.com",
            "nickname": "平台超管",
            "password": "superpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    from app.models.user import User
    result = await db_session.execute(
        select(User).where(User.email == "platform-admin@example.com")
    )
    user = result.scalar_one()
    user.role = "super_admin"
    await db_session.commit()

    return {
        "email": "platform-admin@example.com",
        "password": "superpassword123",
        "school_id": test_school["id"],
        "access_token": data["access_token"],
        "id": user.id,
    }


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: dict) -> dict:
    return {"Authorization": f"Bearer {super_admin_user['access_token']}"}


@pytest_asyncio.fixture
async def jiangnan_template(db_session: AsyncSession) -> dict:
    """预置江南大学（code='jiangnan'）+ 2 个分类作为模板源。

    conftest 每用例 TRUNCATE，故需在用例内创建模板学校与分类。
    """
    now = datetime.now()
    jn = School(
        code="jiangnan", name="江南大学", is_active=True,
        center_lat=31.49, center_lng=120.27, map_zoom=16,
        created_at=now, updated_at=now,
    )
    db_session.add(jn)
    await db_session.flush()

    cats = [
        Category(
            school_id=jn.id, name="失物招领", code="lost-found", icon="🔍",
            default_validity_days=30, sort_order=1, is_active=True,
            created_at=now, updated_at=now,
        ),
        Category(
            school_id=jn.id, name="活动讲座", code="event", icon="📅",
            default_validity_days=7, sort_order=2, is_active=True,
            created_at=now, updated_at=now,
        ),
    ]
    for c in cats:
        db_session.add(c)
    await db_session.commit()
    return {"id": jn.id, "code": jn.code, "category_count": len(cats)}


# ============================================================
# TEN-04.1：创建学校（完整初始化）
# ============================================================
class TestCreateSchool:
    """POST /api/v1/platform/schools 创建学校。"""

    @pytest.mark.asyncio
    async def test_create_school_full_initialization(
        self, client: AsyncClient, super_admin_headers: dict,
        super_admin_user: dict, jiangnan_template: dict,
    ):
        """创建学校：自动复制分类/创建设置/邀请/订阅/审计。"""
        r = await client.post(
            "/api/v1/platform/schools",
            headers=super_admin_headers,
            json={
                "code": "demo-uni",
                "name": "演示大学",
                "center_lat": 30.5,
                "center_lng": 114.3,
                "map_zoom": 15,
                "logo_url": "https://example.com/logo.png",
                "brand_color": "#1890ff",
                "description": "TEN-04 测试学校",
                "admin_email": "demo-admin@example.com",
                "plan_code": "trial",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()

        # school
        school = data["school"]
        assert school["code"] == "demo-uni"
        assert school["name"] == "演示大学"
        assert school["is_active"] is True
        assert school["center_lat"] == 30.5
        assert school["map_zoom"] == 15

        # settings
        settings = data["settings"]
        assert settings["site_name"] == "演示大学"
        assert settings["brand_color"] == "#1890ff"
        assert settings["description"] == "TEN-04 测试学校"

        # invitation
        inv = data["invitation"]
        assert inv is not None
        assert inv["email"] == "demo-admin@example.com"
        assert inv["role"] == "admin"
        assert inv["status"] == "expires"
        assert inv["invitation_code"]

        # subscription（trial）
        sub = data["subscription"]
        assert sub is not None
        assert sub["plan_code"] == "trial"
        assert sub["status"] == "active"

        # 从江南大学复制了 2 个分类
        assert data["categories_copied"] == 2

        # 审计日志已写
        assert data["audit_id"] is not None

    @pytest.mark.asyncio
    async def test_create_school_without_admin_email(
        self, client: AsyncClient, super_admin_headers: dict,
        jiangnan_template: dict,
    ):
        """不传 admin_email → invitation=None，但仍分配默认 trial 套餐。"""
        r = await client.post(
            "/api/v1/platform/schools",
            headers=super_admin_headers,
            json={
                "code": "no-admin-uni",
                "name": "无管理员学校",
                "plan_code": "standard",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["invitation"] is None
        assert data["subscription"]["plan_code"] == "standard"
        # 无江南模板分类也能创建（本用例有 jiangnan_template）
        assert data["categories_copied"] == 2

    @pytest.mark.asyncio
    async def test_create_school_default_trial_plan(
        self, client: AsyncClient, super_admin_headers: dict,
    ):
        """不传 plan_code → 默认分配 trial。"""
        r = await client.post(
            "/api/v1/platform/schools",
            headers=super_admin_headers,
            json={"code": "default-trial-uni", "name": "默认试用校"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["subscription"]["plan_code"] == "trial"

    @pytest.mark.asyncio
    async def test_create_school_duplicate_code_conflict(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """重复 code → 409。"""
        r = await client.post(
            "/api/v1/platform/schools",
            headers=super_admin_headers,
            json={"code": test_school["code"], "name": "重复学校"},
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_create_school_non_super_admin_forbidden(
        self, client: AsyncClient, auth_headers: dict,
    ):
        """普通 user 创建学校 → 403。"""
        r = await client.post(
            "/api/v1/platform/schools",
            headers=auth_headers,
            json={"code": "forbidden-uni", "name": "无权学校"},
        )
        assert r.status_code == 403


# ============================================================
# TEN-04.1：学校列表 + 详情
# ============================================================
class TestListAndDetailSchools:
    """GET /platform/schools + /platform/schools/{id}。"""

    @pytest.mark.asyncio
    async def test_list_schools_with_aggregates(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """列表含订阅/激活/成员/内容数。"""
        r = await client.get(
            "/api/v1/platform/schools", headers=super_admin_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        items = data["items"]
        target = next(it for it in items if it["code"] == test_school["code"])
        assert target["is_active"] is True
        # test_school fixture 自动分配 operations
        assert target["subscription_status"] == "active"
        assert target["subscription_plan_code"] == "operations"

    @pytest.mark.asyncio
    async def test_list_schools_filter_by_active(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """按 is_active 筛选。"""
        r = await client.get(
            "/api/v1/platform/schools",
            headers=super_admin_headers,
            params={"is_active": True},
        )
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["is_active"] is True

    @pytest.mark.asyncio
    async def test_school_detail_with_checklist(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """详情含开通清单 5 项 bool。"""
        r = await client.get(
            f"/api/v1/platform/schools/{test_school['id']}",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == test_school["id"]
        cl = data["checklist"]
        # 5 项键齐全
        assert set(cl.keys()) >= {
            "brand_set", "admin_accepted", "locations_imported",
            "first_content", "first_members", "all_done",
        }
        # 全为 bool
        for k in ("brand_set", "admin_accepted", "locations_imported",
                  "first_content", "first_members", "all_done"):
            assert isinstance(cl[k], bool)

    @pytest.mark.asyncio
    async def test_school_detail_not_found(
        self, client: AsyncClient, super_admin_headers: dict,
    ):
        """不存在的学校 → 404。"""
        r = await client.get(
            "/api/v1/platform/schools/999999",
            headers=super_admin_headers,
        )
        assert r.status_code == 404


# ============================================================
# TEN-04.1 + TEN-04.2：启停学校 + 暂停后写拒绝
# ============================================================
class TestSuspendReactivateSchool:
    """PUT /platform/schools/{id}/status + 暂停后写拒绝。"""

    @pytest.mark.asyncio
    async def test_suspend_school_writes_audit(
        self, client: AsyncClient, super_admin_headers: dict,
        super_admin_user: dict, test_school: dict,
    ):
        """暂停学校 → is_active=false + 审计 school.suspend。"""
        r = await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": False, "reason": "测试暂停"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_active"] is False

        # 审计日志
        r2 = await client.get(
            "/api/v1/platform/audit",
            headers=super_admin_headers,
            params={"action": "school.suspend",
                    "target_school_id": test_school["id"]},
        )
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert len(items) >= 1
        assert items[0]["action"] == "school.suspend"
        assert items[0]["operator_id"] == super_admin_user["id"]
        assert items[0]["reason"] == "测试暂停"

    @pytest.mark.asyncio
    async def test_reactivate_school(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """先暂停再恢复 → is_active=true + 审计 school.reactivate。"""
        # 暂停
        r1 = await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": False, "reason": "暂停"},
        )
        assert r1.status_code == 200
        assert r1.json()["is_active"] is False

        # 恢复
        r2 = await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": True, "reason": "恢复"},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["is_active"] is True

        # 审计
        r3 = await client.get(
            "/api/v1/platform/audit",
            headers=super_admin_headers,
            params={"action": "school.reactivate"},
        )
        assert r3.status_code == 200
        assert any(it["target_school_id"] == test_school["id"]
                   for it in r3.json()["items"])

    @pytest.mark.asyncio
    async def test_suspend_then_write_rejected(
        self, client: AsyncClient, super_admin_headers: dict,
        auth_headers: dict, test_school: dict, test_category: dict,
        test_post_type: dict,
    ):
        """暂停学校后，普通用户发帖被拒绝（tenant.py 404）。

        tenant.py 的 get_tenant_context 在解析阶段对 inactive 学校直接 404，
        即系统级 is_active 拦截；本用例验证暂停后写接口确实被拒。
        """
        # 暂停前：发帖成功（auth_headers 用户属于 test_school）
        r_before = await client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "暂停前发帖",
                "content": "学校正常时发帖应成功",
                "category_id": test_category["id"],
                "post_type_id": test_post_type["id"],
            },
        )
        assert r_before.status_code == 201, r_before.text

        # 暂停学校
        r_suspend = await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": False, "reason": "测试写入拒绝"},
        )
        assert r_suspend.status_code == 200

        # 暂停后：发帖被拒（404，tenant.py 拦截 inactive 学校）
        r_after = await client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "暂停后发帖",
                "content": "学校暂停时应被拒绝",
                "category_id": test_category["id"],
                "post_type_id": test_post_type["id"],
            },
        )
        assert r_after.status_code == 404, r_after.text

        # 恢复学校
        r_reactivate = await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": True, "reason": "恢复写入"},
        )
        assert r_reactivate.status_code == 200

        # 恢复后：发帖重新可用
        r_recover = await client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "恢复后发帖",
                "content": "学校恢复后发帖应重新成功",
                "category_id": test_category["id"],
                "post_type_id": test_post_type["id"],
            },
        )
        assert r_recover.status_code == 201, r_recover.text

    @pytest.mark.asyncio
    async def test_status_no_change_bad_request(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """状态未变更 → 400。"""
        # test_school 已 active，再次设 active → 400
        r = await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": True, "reason": "无变更"},
        )
        assert r.status_code == 400


# ============================================================
# TEN-04.3：平台审计日志
# ============================================================
class TestPlatformAudit:
    """GET /platform/audit + 审计写入验证。"""

    @pytest.mark.asyncio
    async def test_audit_logs_after_create_school(
        self, client: AsyncClient, super_admin_headers: dict,
        super_admin_user: dict, jiangnan_template: dict,
    ):
        """创建学校后审计日志含 school.create。"""
        r_create = await client.post(
            "/api/v1/platform/schools",
            headers=super_admin_headers,
            json={"code": "audit-uni", "name": "审计校", "admin_email": "a@b.com"},
        )
        assert r_create.status_code == 200
        school_id = r_create.json()["school"]["id"]

        r = await client.get(
            "/api/v1/platform/audit",
            headers=super_admin_headers,
            params={"action": "school.create", "target_school_id": school_id},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        log = items[0]
        assert log["action"] == "school.create"
        assert log["operator_id"] == super_admin_user["id"]
        assert log["target_school_id"] == school_id
        # new_value 含 code/name
        assert "audit-uni" in (log["new_value"] or "")

    @pytest.mark.asyncio
    async def test_audit_logs_filter_by_operator(
        self, client: AsyncClient, super_admin_headers: dict,
        super_admin_user: dict, test_school: dict,
    ):
        """按操作者筛选审计日志。"""
        # 触发一次 suspend
        await client.put(
            f"/api/v1/platform/schools/{test_school['id']}/status",
            headers=super_admin_headers,
            json={"is_active": False, "reason": "x"},
        )
        r = await client.get(
            "/api/v1/platform/audit",
            headers=super_admin_headers,
            params={"operator_id": super_admin_user["id"]},
        )
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["operator_id"] == super_admin_user["id"]

    @pytest.mark.asyncio
    async def test_audit_logs_subscription_assign(
        self, client: AsyncClient, super_admin_headers: dict,
        test_school: dict,
    ):
        """分配套餐后审计含 subscription.assign。"""
        r = await client.post(
            f"/api/v1/platform/schools/{test_school['id']}/subscription",
            headers=super_admin_headers,
            json={"plan_code": "trial", "note": "审计测试分配"},
        )
        assert r.status_code == 200

        r2 = await client.get(
            "/api/v1/platform/audit",
            headers=super_admin_headers,
            params={"action": "subscription.assign",
                    "target_school_id": test_school["id"]},
        )
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert len(items) >= 1
        assert items[0]["action"] == "subscription.assign"

    @pytest.mark.asyncio
    async def test_audit_non_super_admin_forbidden(
        self, client: AsyncClient, auth_headers: dict,
    ):
        """普通 user 访问审计列表 → 403。"""
        r = await client.get(
            "/api/v1/platform/audit", headers=auth_headers
        )
        assert r.status_code == 403


# ============================================================
# TEN-04.2：开通清单单元测试（直接验证 service）
# ============================================================
class TestProvisioningChecklist:
    """SchoolProvisioningService.get_provisioning_checklist 单元测试。"""

    @pytest.mark.asyncio
    async def test_checklist_all_false_for_empty_school(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """空学校（无品牌/无管理员/无地点/无内容/无成员）→ 全 False。

        注意：test_school fixture 未创建 settings 行，brand_set 取决于
        school.logo_url（None）→ False。
        """
        from app.services.school_provisioning import SchoolProvisioningService

        svc = SchoolProvisioningService(db_session)
        cl = await svc.get_provisioning_checklist(test_school["id"])
        assert cl.brand_set is False
        assert cl.admin_accepted is False
        assert cl.locations_imported is False
        assert cl.first_content is False
        assert cl.first_members is False
        assert cl.all_done is False

    @pytest.mark.asyncio
    async def test_checklist_brand_set_when_logo(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """有 logo_url → brand_set=True。"""
        from app.services.school_provisioning import SchoolProvisioningService

        school = (await db_session.execute(
            select(School).where(School.id == test_school["id"])
        )).scalar_one()
        school.logo_url = "https://example.com/logo.png"
        await db_session.commit()

        svc = SchoolProvisioningService(db_session)
        cl = await svc.get_provisioning_checklist(test_school["id"])
        assert cl.brand_set is True

    @pytest.mark.asyncio
    async def test_assert_school_writable_rejects_suspended(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """暂停学校 → assert_school_writable 抛 400 含恢复路径。"""
        from app.services.school_provisioning import SchoolProvisioningService
        from app.core.exceptions import BadRequestException

        school = (await db_session.execute(
            select(School).where(School.id == test_school["id"])
        )).scalar_one()
        school.is_active = False
        await db_session.commit()

        with pytest.raises(BadRequestException) as exc:
            SchoolProvisioningService.assert_school_writable(school)
        # 错误信息含恢复路径
        assert "暂停" in exc.value.detail
        assert "status" in exc.value.detail.lower() or "恢复" in exc.value.detail

    @pytest.mark.asyncio
    async def test_assert_school_writable_passes_active(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """正常学校 → assert_school_writable 通过。"""
        from app.services.school_provisioning import SchoolProvisioningService

        school = (await db_session.execute(
            select(School).where(School.id == test_school["id"])
        )).scalar_one()
        # test_school 默认 is_active=True
        SchoolProvisioningService.assert_school_writable(school)
