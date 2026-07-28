"""ORG-01: 官方发布主体 API 测试

验证：
1. ORG-01.1 用户申请创建发布主体（强制 verified_status=pending，创建者自动成为 owner）
2. ORG-01.2 admin 审核/认证/撤销/恢复状态流转
3. ORG-01.2 admin 成员管理（添加/更新角色/移除）
4. ORG-01.3 模板管理（公共模板 + 主体专属模板）
5. ORG-01.4 聚合效果（浏览/分享/反馈/零结果）
6. 认证标识不可由用户自行设置
7. 认证不代表内容免审（关联帖子仍走 post_status 状态机）
8. TEN-02.3: 三校隔离 E2E（A/B/C 三校认证/撤销/发布/跨校拒绝）
"""
import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.core.post_status import PostStatus
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.publisher_profile import PublisherProfile
from app.models.publisher_membership import PublisherMembership
from app.models.post_template import PostTemplate
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription


# ============================================================
# 辅助函数
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    """COM-01: 为学校分配 operations 档订阅（避免 EntitlementService 校验拦截发帖）"""
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is None:
        return
    now = datetime.now()
    db.add(SchoolSubscription(
        school_id=school_id, plan_id=plan.id, status="active",
        started_at=now, expires_at=None, assigned_at=now,
    ))
    await db.flush()


async def _create_user(
    db: AsyncSession, email: str, nickname: str, school_id: int, role: str = "user"
) -> User:
    user = User(
        email=email, nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id, role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession, user_id: int, school_id: int, role: str = "member"
) -> SchoolMembership:
    m = SchoolMembership(
        user_id=user_id, school_id=school_id, role=role,
        status="active", is_default=False,
    )
    db.add(m)
    await db.flush()
    return m


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    c = Category(
        school_id=school_id, name=name, code=code, icon="📌",
        default_validity_days=30, is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


def _headers(token: str, school_code: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-School-Code": school_code,
    }


@pytest_asyncio.fixture
async def three_school_setup(db_session: AsyncSession) -> dict:
    """创建三校测试数据：A/B/C 三校，每校含 admin + 普通用户 + 分类 + 信息类型。

    用于验证 ORG-01.4 三校 E2E：认证/撤销/发布/跨校拒绝。
    """
    school_a = await _create_school(db_session, "A 校", "school-a")
    school_b = await _create_school(db_session, "B 校", "school-b")
    school_c = await _create_school(db_session, "C 校", "school-c")
    for sid in (school_a.id, school_b.id, school_c.id):
        await _assign_operations_subscription(db_session, sid)

    cat_a = await _create_category(db_session, school_a.id, "A 校通知", "a-notice")
    cat_b = await _create_category(db_session, school_b.id, "B 校通知", "b-notice")
    cat_c = await _create_category(db_session, school_c.id, "C 校通知", "c-notice")

    user_a = await _create_user(db_session, "a@example.com", "A 校用户", school_a.id)
    admin_a = await _create_user(db_session, "admin_a@example.com", "A 校管理员", school_a.id, role="admin")
    user_b = await _create_user(db_session, "b@example.com", "B 校用户", school_b.id)
    admin_b = await _create_user(db_session, "admin_b@example.com", "B 校管理员", school_b.id, role="admin")
    user_c = await _create_user(db_session, "c@example.com", "C 校用户", school_c.id)
    admin_c = await _create_user(db_session, "admin_c@example.com", "C 校管理员", school_c.id, role="admin")

    await _create_membership(db_session, user_a.id, school_a.id, "member")
    await _create_membership(db_session, admin_a.id, school_a.id, "admin")
    await _create_membership(db_session, user_b.id, school_b.id, "member")
    await _create_membership(db_session, admin_b.id, school_b.id, "admin")
    await _create_membership(db_session, user_c.id, school_c.id, "member")
    await _create_membership(db_session, admin_c.id, school_c.id, "admin")

    await db_session.commit()

    return {
        "schools": {
            "a": {"id": school_a.id, "code": school_a.code},
            "b": {"id": school_b.id, "code": school_b.code},
            "c": {"id": school_c.id, "code": school_c.code},
        },
        "categories": {"a": cat_a.id, "b": cat_b.id, "c": cat_c.id},
        "users": {
            "a": {"id": user_a.id, "token": _make_token(user_a.id)},
            "admin_a": {"id": admin_a.id, "token": _make_token(admin_a.id)},
            "b": {"id": user_b.id, "token": _make_token(user_b.id)},
            "admin_b": {"id": admin_b.id, "token": _make_token(admin_b.id)},
            "c": {"id": user_c.id, "token": _make_token(user_c.id)},
            "admin_c": {"id": admin_c.id, "token": _make_token(admin_c.id)},
        },
    }


# ============================================================
# 1. ORG-01.1 用户申请创建发布主体
# ============================================================
@pytest.mark.asyncio
async def test_user_create_publisher_forced_pending(client: AsyncClient, three_school_setup: dict):
    """用户申请创建发布主体：verified_status 强制为 pending（不可自行设置认证标识）。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={
            "name": "A 校学生会",
            "type": "club",
            "intro": "学生自治组织",
            "service_hours": "周一至周五 9:00-17:00",
            "contact": "a@example.com",
        },
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "A 校学生会"
    assert data["type"] == "club"
    assert data["verified_status"] == "pending"  # 强制 pending
    assert data["school_id"] == school_a["id"]
    assert data["is_member"] is True
    assert data["my_role"] == "owner"  # 创建者自动成为 owner


@pytest.mark.asyncio
async def test_create_publisher_creator_becomes_owner(
    client: AsyncClient, three_school_setup: dict
):
    """创建者自动成为 owner 成员（成员列表含创建者）。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "测试主体", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200
    memberships = resp.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["user_id"] == user_a["id"]
    assert memberships[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_create_publisher_invalid_type(client: AsyncClient, three_school_setup: dict):
    """类型不合法返回 422。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "测试", "type": "invalid_type"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 422


# ============================================================
# 2. ORG-01.2 admin 审核/认证/撤销/恢复状态流转
# ============================================================
@pytest.mark.asyncio
async def test_admin_verify_publisher_full_lifecycle(
    client: AsyncClient, three_school_setup: dict
):
    """完整状态流转：pending → verified → revoked → pending（恢复）→ verified。"""
    user_a = three_school_setup["users"]["a"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]

    # 用户申请
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "认证生命周期测试", "type": "service_org"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]
    assert resp.json()["verified_status"] == "pending"

    # admin 认证通过 pending → verified
    resp_approve = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "approve", "note": "材料齐全"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_approve.status_code == 200
    assert resp_approve.json()["verified_status"] == "verified"
    assert resp_approve.json()["verified_at"] is not None
    assert resp_approve.json()["verified_by"] == admin_a["id"]
    assert resp_approve.json()["verify_note"] == "材料齐全"

    # 重复 approve 应失败（状态不符）
    resp_approve_again = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "approve"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_approve_again.status_code == 400

    # 撤销 verified → revoked
    resp_revoke = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "revoke", "note": "违规操作"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_revoke.status_code == 200
    assert resp_revoke.json()["verified_status"] == "revoked"

    # 恢复 revoked → pending
    resp_restore = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "restore"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_restore.status_code == 200
    assert resp_restore.json()["verified_status"] == "pending"

    # 再次认证
    resp_re_approve = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "approve"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_re_approve.json()["verified_status"] == "verified"


@pytest.mark.asyncio
async def test_admin_reject_publisher(client: AsyncClient, three_school_setup: dict):
    """admin 驳回申请：pending → rejected，再 restore → pending。"""
    user_a = three_school_setup["users"]["a"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "待驳回主体", "type": "club"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # 驳回
    resp_reject = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "reject", "note": "材料不齐"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_reject.status_code == 200
    assert resp_reject.json()["verified_status"] == "rejected"

    # restore 允许从 rejected → pending
    resp_restore = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "restore"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_restore.status_code == 200
    assert resp_restore.json()["verified_status"] == "pending"


@pytest.mark.asyncio
async def test_normal_user_cannot_verify(client: AsyncClient, three_school_setup: dict):
    """普通用户无权审核发布主体（403）。"""
    user_a = three_school_setup["users"]["a"]
    user_b = three_school_setup["users"]["b"]
    school_a = three_school_setup["schools"]["a"]

    # A 校用户创建
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "权限测试主体", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # A 校普通用户尝试审核 → 403
    resp_user_verify = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "approve"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_user_verify.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_set_verified_status_on_create(
    client: AsyncClient, three_school_setup: dict
):
    """认证标识不可由用户自行设置——POST /publishers 忽略 body 中的 verified_status。

    schema PublisherProfileCreate 不含 verified_status 字段，Pydantic 默认忽略额外字段。
    后端强制写入 pending，确保用户无法绕过审核。
    """
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={
            "name": "尝试绕过认证",
            "type": "department",
            "verified_status": "verified",  # 试图自行设置认证
        },
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200
    # 仍为 pending，verified_status 被后端强制覆盖
    assert resp.json()["verified_status"] == "pending"


# ============================================================
# 3. ORG-01.2 admin 成员管理
# ============================================================
@pytest.mark.asyncio
async def test_admin_add_update_remove_member(
    client: AsyncClient, three_school_setup: dict
):
    """admin 添加成员 → 更新角色 → 移除成员。"""
    user_a = three_school_setup["users"]["a"]
    user_b = three_school_setup["users"]["b"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]

    # A 校用户创建主体
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "成员管理测试", "type": "club"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # admin 添加 B 校用户为成员（admin 可跨用户添加，但 B 校用户在不同学校）
    # 这里添加 A 校的另一个用户（admin_a 自己）作为测试
    resp_add = await client.post(
        f"/api/v1/admin/publishers/{pub_id}/members",
        json={"user_id": admin_a["id"], "role": "admin"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add.status_code == 200
    assert resp_add.json()["role"] == "admin"

    # 重复添加应 Conflict
    resp_add_dup = await client.post(
        f"/api/v1/admin/publishers/{pub_id}/members",
        json={"user_id": admin_a["id"], "role": "member"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add_dup.status_code == 409

    # 更新角色
    resp_update = await client.put(
        f"/api/v1/admin/publishers/{pub_id}/members/{admin_a['id']}",
        json={"role": "member"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["role"] == "member"

    # 移除成员
    resp_remove = await client.delete(
        f"/api/v1/admin/publishers/{pub_id}/members/{admin_a['id']}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_remove.status_code == 200

    # 再次移除应 404
    resp_remove_again = await client.delete(
        f"/api/v1/admin/publishers/{pub_id}/members/{admin_a['id']}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_remove_again.status_code == 404


# ============================================================
# 4. ORG-01.3 模板管理
# ============================================================
@pytest.mark.asyncio
async def test_admin_create_public_template(client: AsyncClient, three_school_setup: dict):
    """admin 创建学校级公共模板（publisher_id 为空）。"""
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]
    cat_a = three_school_setup["categories"]["a"]

    resp = await client.post(
        "/api/v1/admin/templates",
        json={
            "name": "营业时间通知模板",
            "title_template": "【营业时间】{名称}",
            "content_template": "营业时间：周一至周五 9:00-17:00",
            "category_id": cat_a,
            "scene": "business_hours",
            "sort_order": 10,
        },
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "营业时间通知模板"
    assert data["publisher_id"] is None
    assert data["school_id"] == school_a["id"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_public_templates_filtered_by_school(
    client: AsyncClient, three_school_setup: dict
):
    """公共模板按学校过滤：A 校看不到 B 校模板。"""
    admin_a = three_school_setup["users"]["admin_a"]
    admin_b = three_school_setup["users"]["admin_b"]
    school_a = three_school_setup["schools"]["a"]
    school_b = three_school_setup["schools"]["b"]

    # A 校创建 2 个公共模板
    for i in range(2):
        await client.post(
            "/api/v1/admin/templates",
            json={
                "name": f"A 校模板 {i}",
                "title_template": f"A{i} 标题",
                "content_template": f"A{i} 内容",
                "scene": "notification",
            },
            headers=_headers(admin_a["token"], school_a["code"]),
        )
    # B 校创建 1 个公共模板
    await client.post(
        "/api/v1/admin/templates",
        json={
            "name": "B 校模板",
            "title_template": "B 标题",
            "content_template": "B 内容",
            "scene": "notification",
        },
        headers=_headers(admin_b["token"], school_b["code"]),
    )

    # A 校用户端获取公共模板：只应返回 A 校的 2 个
    resp_a = await client.get(
        "/api/v1/templates",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_a.status_code == 200
    templates_a = resp_a.json()
    assert len(templates_a) == 2
    for t in templates_a:
        assert t["school_id"] == school_a["id"]

    # B 校用户端获取公共模板：只应返回 B 校的 1 个
    resp_b = await client.get(
        "/api/v1/templates",
        headers=_headers(admin_b["token"], school_b["code"]),
    )
    assert resp_b.status_code == 200
    templates_b = resp_b.json()
    assert len(templates_b) == 1
    assert templates_b[0]["school_id"] == school_b["id"]


@pytest.mark.asyncio
async def test_publisher_owner_create_template(
    client: AsyncClient, three_school_setup: dict
):
    """主体 owner 成员可创建主体专属模板。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]
    cat_a = three_school_setup["categories"]["a"]

    # 创建主体
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "模板测试主体", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # owner 创建专属模板
    resp_tmpl = await client.post(
        f"/api/v1/publishers/{pub_id}/templates",
        json={
            "name": "讲座通知模板",
            "title_template": "【讲座】{主题}",
            "content_template": "讲座时间：{时间}；地点：{地点}",
            "category_id": cat_a,
            "scene": "lecture",
        },
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_tmpl.status_code == 200
    assert resp_tmpl.json()["publisher_id"] == pub_id


@pytest.mark.asyncio
async def test_non_member_cannot_create_publisher_template(
    client: AsyncClient, three_school_setup: dict
):
    """非成员无法为主体创建专属模板（403）。"""
    user_a = three_school_setup["users"]["a"]
    user_b = three_school_setup["users"]["b"]
    school_a = three_school_setup["schools"]["a"]

    # A 校 user_a 创建主体
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "非成员模板测试", "type": "club"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # B 校 user_b 尝试为该主体创建模板（跨校 → 404，先于权限校验）
    resp_cross = await client.post(
        f"/api/v1/publishers/{pub_id}/templates",
        json={
            "name": "越权模板",
            "title_template": "越权",
            "content_template": "越权内容",
            "scene": "other",
        },
        headers=_headers(user_b["token"], three_school_setup["schools"]["b"]["code"]),
    )
    assert resp_cross.status_code == 404  # 跨校统一 404


# ============================================================
# 5. ORG-01.4 聚合效果（浏览/分享/反馈/零结果）
# ============================================================
@pytest.mark.asyncio
async def test_publisher_view_count_increment(
    client: AsyncClient, three_school_setup: dict
):
    """访问主体详情时 view_count +1。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "浏览数测试", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]
    assert resp.json()["view_count"] == 0

    # 访问详情 2 次
    await client.get(f"/api/v1/publishers/{pub_id}", headers=_headers(user_a["token"], school_a["code"]))
    resp_detail = await client.get(
        f"/api/v1/publishers/{pub_id}", headers=_headers(user_a["token"], school_a["code"])
    )
    assert resp_detail.status_code == 200
    assert resp_detail.json()["view_count"] == 2


@pytest.mark.asyncio
async def test_publisher_share_and_feedback(
    client: AsyncClient, three_school_setup: dict
):
    """分享计数 + 有效性反馈 + 零结果聚合。"""
    user_a = three_school_setup["users"]["a"]
    user_b = three_school_setup["users"]["b"]
    school_a = three_school_setup["schools"]["a"]

    # A 校创建主体
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "聚合测试主体", "type": "service_org"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # 分享 2 次
    await client.post(
        f"/api/v1/publishers/{pub_id}/share", json={},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    await client.post(
        f"/api/v1/publishers/{pub_id}/share", json={},
        headers=_headers(user_a["token"], school_a["code"]),
    )

    # 有效性反馈：valid 2 次，invalid 1 次
    await client.post(
        f"/api/v1/publishers/{pub_id}/feedback", json={"feedback_type": "valid"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    await client.post(
        f"/api/v1/publishers/{pub_id}/feedback", json={"feedback_type": "valid"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    await client.post(
        f"/api/v1/publishers/{pub_id}/feedback", json={"feedback_type": "invalid"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    # 零结果 1 次
    await client.post(
        f"/api/v1/publishers/{pub_id}/feedback", json={"feedback_type": "zero_result"},
        headers=_headers(user_a["token"], school_a["code"]),
    )

    # 查询聚合
    resp_agg = await client.get(
        f"/api/v1/publishers/{pub_id}/aggregation",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_agg.status_code == 200
    data = resp_agg.json()
    assert data["share_count"] == 2
    assert data["valid_feedback_count"] == 2
    assert data["invalid_feedback_count"] == 1
    assert data["zero_result_count"] == 1
    # 有效性反馈率 = 2 / (2+1) = 0.6667
    assert data["valid_rate"] is not None
    assert abs(data["valid_rate"] - 2 / 3) < 0.01


# ============================================================
# 6. 认证不代表内容免审（关联帖子仍走 post_status 状态机）
# ============================================================
@pytest.mark.asyncio
async def test_publisher_post_still_requires_review(
    client: AsyncClient, three_school_setup: dict
):
    """关联发布主体的帖子仍走 post_status 状态机：创建为 pending，需 admin 审核才能 published。

    认证不等于内容免审——这是 ORG-01.2 的关键约束。
    """
    user_a = three_school_setup["users"]["a"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]
    cat_a = three_school_setup["categories"]["a"]

    # 创建主体并由 admin 认证
    resp_pub = await client.post(
        "/api/v1/publishers",
        json={"name": "免审测试主体", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp_pub.json()["id"]
    await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "approve"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )

    # 以主体名义发帖（status=pending 提交审核）
    resp_post = await client.post(
        "/api/v1/posts",
        json={
            "title": "主体发布的内容测试",
            "content": "认证主体发布的内容，仍需走审核流程",
            "category_id": cat_a,
            "publisher_id": pub_id,
            "status": "pending",
        },
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_post.status_code == 201, resp_post.text
    post_data = resp_post.json()
    assert post_data["publisher_id"] == pub_id
    # 关键断言：状态为 pending（未免审），需 admin 审核
    assert post_data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_post_with_non_member_publisher_forbidden(
    client: AsyncClient, three_school_setup: dict
):
    """非主体成员不能以该主体名义发帖（403）。"""
    user_a = three_school_setup["users"]["a"]
    user_b = three_school_setup["users"]["b"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]
    cat_a = three_school_setup["categories"]["a"]

    # A 校 user_a 创建主体并认证
    resp_pub = await client.post(
        "/api/v1/publishers",
        json={"name": "成员校验主体", "type": "club"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp_pub.json()["id"]
    await client.put(
        f"/api/v1/admin/publishers/{pub_id}/verify",
        json={"action": "approve"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )

    # 把 user_b 也加入 A 校（让 user_b 在 A 校有 membership，但不是主体成员）
    # 注意：user_b 的 school_id 是 B 校，这里通过 X-School-Code 头切换上下文
    # 但 user_b 没有 A 校 membership，会被 tenant 校验拦截
    # 简化：直接用 A 校的 admin_a（admin_a 不是该主体成员）
    resp_post = await client.post(
        "/api/v1/posts",
        json={
            "title": "非成员主体发帖测试",
            "content": "非主体成员尝试以主体名义发帖",
            "category_id": cat_a,
            "publisher_id": pub_id,
            "status": "pending",
        },
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    # admin_a 不是该主体成员 → 403
    assert resp_post.status_code == 403


# ============================================================
# 7. TEN-02.3: 三校隔离 E2E（A/B/C 三校认证/撤销/发布/跨校拒绝）
# ============================================================
@pytest.mark.asyncio
async def test_three_school_e2e(client: AsyncClient, three_school_setup: dict):
    """ORG-01.4 三校 E2E：A/B/C 三校各自认证主体 → 跨校访问拒绝。

    验证：
    1. 三校分别创建主体并认证
    2. 三校用户各自只能看到本校主体列表
    3. 跨校访问主体详情统一 404
    4. 跨校 admin 无法操作他校主体
    5. 切换学校上下文只展示当前学校主体
    """
    user_a = three_school_setup["users"]["a"]
    user_b = three_school_setup["users"]["b"]
    user_c = three_school_setup["users"]["c"]
    admin_a = three_school_setup["users"]["admin_a"]
    admin_b = three_school_setup["users"]["admin_b"]
    admin_c = three_school_setup["users"]["admin_c"]
    school_a = three_school_setup["schools"]["a"]
    school_b = three_school_setup["schools"]["b"]
    school_c = three_school_setup["schools"]["c"]

    # === 步骤 1：三校各自创建主体 ===
    resp_a = await client.post(
        "/api/v1/publishers",
        json={"name": "A 校官方主体", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    resp_b = await client.post(
        "/api/v1/publishers",
        json={"name": "B 校官方主体", "type": "club"},
        headers=_headers(user_b["token"], school_b["code"]),
    )
    resp_c = await client.post(
        "/api/v1/publishers",
        json={"name": "C 校官方主体", "type": "service_org"},
        headers=_headers(user_c["token"], school_c["code"]),
    )
    pub_a_id = resp_a.json()["id"]
    pub_b_id = resp_b.json()["id"]
    pub_c_id = resp_c.json()["id"]
    assert resp_a.json()["verified_status"] == "pending"
    assert resp_b.json()["verified_status"] == "pending"
    assert resp_c.json()["verified_status"] == "pending"

    # === 步骤 2：三校各自 admin 认证本校主体 ===
    for admin, school, pub_id in [
        (admin_a, school_a, pub_a_id),
        (admin_b, school_b, pub_b_id),
        (admin_c, school_c, pub_c_id),
    ]:
        resp_verify = await client.put(
            f"/api/v1/admin/publishers/{pub_id}/verify",
            json={"action": "approve"},
            headers=_headers(admin["token"], school["code"]),
        )
        assert resp_verify.status_code == 200
        assert resp_verify.json()["verified_status"] == "verified"

    # === 步骤 3：三校各自列表只返回本校主体 ===
    resp_list_a = await client.get(
        "/api/v1/publishers",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    resp_list_b = await client.get(
        "/api/v1/publishers",
        headers=_headers(user_b["token"], school_b["code"]),
    )
    resp_list_c = await client.get(
        "/api/v1/publishers",
        headers=_headers(user_c["token"], school_c["code"]),
    )
    a_ids = {p["id"] for p in resp_list_a.json()["items"]}
    b_ids = {p["id"] for p in resp_list_b.json()["items"]}
    c_ids = {p["id"] for p in resp_list_c.json()["items"]}
    assert a_ids == {pub_a_id}
    assert b_ids == {pub_b_id}
    assert c_ids == {pub_c_id}
    # 交叉断言：A 校列表不含 B/C 主体
    assert pub_b_id not in a_ids
    assert pub_c_id not in a_ids

    # === 步骤 4：跨校访问主体详情统一 404 ===
    resp_cross_b = await client.get(
        f"/api/v1/publishers/{pub_a_id}",
        headers=_headers(user_b["token"], school_b["code"]),
    )
    assert resp_cross_b.status_code == 404

    resp_cross_c = await client.get(
        f"/api/v1/publishers/{pub_a_id}",
        headers=_headers(user_c["token"], school_c["code"]),
    )
    assert resp_cross_c.status_code == 404

    # === 步骤 5：跨校 admin 无法操作他校主体（撤销/删除/成员）===
    # B 校 admin 尝试撤销 A 校主体 → 404
    resp_cross_revoke = await client.put(
        f"/api/v1/admin/publishers/{pub_a_id}/verify",
        json={"action": "revoke"},
        headers=_headers(admin_b["token"], school_b["code"]),
    )
    assert resp_cross_revoke.status_code == 404

    # C 校 admin 尝试删除 A 校主体 → 404
    resp_cross_delete = await client.delete(
        f"/api/v1/admin/publishers/{pub_a_id}",
        headers=_headers(admin_c["token"], school_c["code"]),
    )
    assert resp_cross_delete.status_code == 404

    # B 校 admin 尝试向 A 校主体添加成员 → 404
    resp_cross_add_member = await client.post(
        f"/api/v1/admin/publishers/{pub_a_id}/members",
        json={"user_id": user_b["id"], "role": "member"},
        headers=_headers(admin_b["token"], school_b["code"]),
    )
    assert resp_cross_add_member.status_code == 404


@pytest.mark.asyncio
async def test_cross_school_publisher_create_with_other_school_location(
    client: AsyncClient, three_school_setup: dict, db_session: AsyncSession
):
    """创建主体时若指定他校 location_id → 404（租户隔离，check_resource_in_tenant 统一 404）。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]
    school_b = three_school_setup["schools"]["b"]

    # 在 B 校创建一个 location
    from app.models.location import Location
    loc_b = Location(
        school_id=school_b["id"], name="B 校地点",
        latitude=31.0, longitude=120.0, is_verified=True,
    )
    db_session.add(loc_b)
    await db_session.commit()
    await db_session.refresh(loc_b)

    # A 校用户创建主体时引用 B 校 location → 404（check_resource_in_tenant 跨校统一 404）
    resp = await client.post(
        "/api/v1/publishers",
        json={
            "name": "跨校地点测试",
            "type": "department",
            "location_id": loc_b.id,
        },
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 404


# ============================================================
# 8. 用户更新主体信息（不可改 verified_status）
# ============================================================
@pytest.mark.asyncio
async def test_owner_update_publisher_info(client: AsyncClient, three_school_setup: dict):
    """owner 可更新主体信息，但 verified_status 不可改。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "原名称", "type": "department", "intro": "原简介"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # owner 更新
    resp_update = await client.put(
        f"/api/v1/publishers/{pub_id}",
        json={"name": "新名称", "intro": "新简介", "contact": "new@example.com"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["name"] == "新名称"
    assert resp_update.json()["intro"] == "新简介"
    assert resp_update.json()["contact"] == "new@example.com"
    # verified_status 不变
    assert resp_update.json()["verified_status"] == "pending"


@pytest.mark.asyncio
async def test_non_owner_cannot_update(client: AsyncClient, three_school_setup: dict):
    """非 owner/admin 成员无法更新主体信息（403）。"""
    user_a = three_school_setup["users"]["a"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]

    # user_a 创建主体（user_a 是 owner）
    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "权限测试", "type": "club"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # admin_a 不是该主体成员（虽然 admin_a 是 A 校管理员），但 admin_a 在 admin_publishers 接口可管理
    # 这里测试的是用户端 PUT /publishers/{id} 接口：仅 owner/admin 成员可改
    # admin_a 不是主体成员 → 403
    resp_update = await client.put(
        f"/api/v1/publishers/{pub_id}",
        json={"name": "越权修改"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_update.status_code == 403


# ============================================================
# 9. 软删除发布主体
# ============================================================
@pytest.mark.asyncio
async def test_admin_soft_delete_publisher(client: AsyncClient, three_school_setup: dict):
    """admin 软删除发布主体：列表不再返回，详情 404。"""
    user_a = three_school_setup["users"]["a"]
    admin_a = three_school_setup["users"]["admin_a"]
    school_a = three_school_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/publishers",
        json={"name": "待删除主体", "type": "department"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_id = resp.json()["id"]

    # admin 删除
    resp_del = await client.delete(
        f"/api/v1/admin/publishers/{pub_id}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_del.status_code == 200

    # 列表不再返回
    resp_list = await client.get(
        "/api/v1/publishers",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    pub_ids = {p["id"] for p in resp_list.json()["items"]}
    assert pub_id not in pub_ids

    # 详情 404
    resp_detail = await client.get(
        f"/api/v1/publishers/{pub_id}",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_detail.status_code == 404

    # 重复删除 → 404（_load_publisher_admin 已过滤 is_deleted=True，跨校/已删统一 404）
    resp_del_again = await client.delete(
        f"/api/v1/admin/publishers/{pub_id}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_del_again.status_code == 404


# ============================================================
# 10. me/publishers 列出当前用户加入的主体
# ============================================================
@pytest.mark.asyncio
async def test_list_my_publishers(client: AsyncClient, three_school_setup: dict):
    """当前用户加入的发布主体列表（仅本校）。"""
    user_a = three_school_setup["users"]["a"]
    school_a = three_school_setup["schools"]["a"]

    # 创建 2 个主体（user_a 自动成为 owner）
    for i in range(2):
        await client.post(
            "/api/v1/publishers",
            json={"name": f"我的主体 {i}", "type": "club"},
            headers=_headers(user_a["token"], school_a["code"]),
        )

    resp = await client.get(
        "/api/v1/me/publishers",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for p in data:
        assert p["name"].startswith("我的主体")
