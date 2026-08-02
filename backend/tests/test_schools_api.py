"""TEN-03.1: 学校目录、加入、默认学校、切换 API 测试

覆盖 5 个端点：
    GET    /api/v1/schools                公开目录
    GET    /api/v1/schools/current        当前学校
    GET    /api/v1/me/memberships         我的学校列表
    POST   /api/v1/schools/{code}/join    加入学校
    PUT    /api/v1/me/default-school      设置默认学校

关键场景：
- 公开目录无需登录、无需 X-School-Code
- /schools/current 需 X-School-Code 或登录用户默认学校
- /me/* 需登录，未登录 401
- join 幂等：已是 active 成员返回 already_member=true
- join invited/suspended 成员：升级为 active
- 设置默认学校时取消其它默认，并同步 user.school_id
- 公开目录只返回 is_active=true 的学校
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User


# ============================================================
# 辅助函数
# ============================================================
async def _create_school(
    db: AsyncSession, name: str, code: str, is_active: bool = True
) -> School:
    school = School(name=name, code=code, is_active=is_active)
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
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    role: str = "member",
    status: str = "active",
    is_default: bool = False,
) -> SchoolMembership:
    m = SchoolMembership(
        user_id=user_id,
        school_id=school_id,
        role=role,
        status=status,
        is_default=is_default,
    )
    db.add(m)
    await db.flush()
    return m


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _school_headers(code: str) -> dict:
    return {"X-School-Code": code}


# ============================================================
# 共享 fixture：三所学校 + 多校成员用户
# ============================================================
@pytest_asyncio.fixture
async def schools_fixture(db_session: AsyncSession) -> dict:
    """创建三所学校（A/B 启用，C 停用）+ 一个有多校 membership 的用户。"""
    school_a = await _create_school(db_session, "A 校", "school-a")
    school_b = await _create_school(db_session, "B 校", "school-b")
    school_c = await _create_school(db_session, "C 校（停用）", "school-c", is_active=False)

    # 用户 u1：默认 A 校，同时加入 B 校
    u1 = await _create_user(db_session, "u1@example.com", "U1", school_a.id)
    await _create_membership(
        db_session, u1.id, school_a.id, role="member", is_default=True
    )
    await _create_membership(
        db_session, u1.id, school_b.id, role="admin", is_default=False
    )

    # 用户 u2：仅 A 校
    u2 = await _create_user(db_session, "u2@example.com", "U2", school_a.id)
    await _create_membership(
        db_session, u2.id, school_a.id, role="member", is_default=True
    )

    # 用户 u3：A 校 invited 状态（待升级）
    u3 = await _create_user(db_session, "u3@example.com", "U3", school_a.id)
    await _create_membership(
        db_session, u3.id, school_a.id, role="member", status="invited", is_default=False
    )

    await db_session.commit()

    return {
        "schools": {
            "a": {"id": school_a.id, "code": school_a.code, "name": school_a.name},
            "b": {"id": school_b.id, "code": school_b.code, "name": school_b.name},
            "c": {"id": school_c.id, "code": school_c.code, "name": school_c.name},
        },
        "users": {
            "u1": {"id": u1.id, "token": create_access_token(data={"sub": str(u1.id)})},
            "u2": {"id": u2.id, "token": create_access_token(data={"sub": str(u2.id)})},
            "u3": {"id": u3.id, "token": create_access_token(data={"sub": str(u3.id)})},
        },
    }


# ============================================================
# GET /api/v1/schools（公开目录）
# ============================================================
class TestListSchools:
    """公开学校目录接口"""

    @pytest.mark.asyncio
    async def test_public_directory_no_auth_required(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """无 Token / 无 X-School-Code 也能访问"""
        resp = await client.get("/api/v1/schools")
        assert resp.status_code == 200
        data = resp.json()
        codes = {s["code"] for s in data}
        # 仅返回 is_active=true 的学校
        assert "school-a" in codes
        assert "school-b" in codes
        assert "school-c" not in codes  # 停用学校不返回

    @pytest.mark.asyncio
    async def test_directory_fields(self, client: AsyncClient, schools_fixture: dict):
        """返回字段包含 id/code/name/logo_url/is_active 等"""
        resp = await client.get("/api/v1/schools")
        data = resp.json()
        assert len(data) >= 2
        for item in data:
            assert "id" in item
            assert "code" in item
            assert "name" in item
            assert item.get("is_active") is True


# ============================================================
# GET /api/v1/schools/current
# ============================================================
class TestGetCurrentSchool:
    """当前学校接口（基于 TenantContext）"""

    @pytest.mark.asyncio
    async def test_guest_with_school_code_header(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """游客通过 X-School-Code 获取当前学校"""
        resp = await client.get(
            "/api/v1/schools/current",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "school-a"
        assert data["name"] == "A 校"

    @pytest.mark.asyncio
    async def test_guest_without_school_code_returns_404(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """游客未传 X-School-Code → 404"""
        resp = await client.get("/api/v1/schools/current")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_logged_in_user_defaults_to_own_school(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """登录用户未传 X-School-Code → user.school_id"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.get("/api/v1/schools/current", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "school-a"

    @pytest.mark.asyncio
    async def test_logged_in_user_with_header_overrides_default(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """登录用户传 X-School-Code → 切换到目标学校（需有 membership）"""
        headers = {
            **_auth_headers(schools_fixture["users"]["u1"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get("/api/v1/schools/current", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "school-b"

    @pytest.mark.asyncio
    async def test_nonexistent_school_returns_404(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """不存在的 school code → 404"""
        resp = await client.get(
            "/api/v1/schools/current",
            headers=_school_headers("nonexistent"),
        )
        assert resp.status_code == 404


# ============================================================
# GET /api/v1/me/memberships
# ============================================================
class TestListMyMemberships:
    """我的学校成员关系列表"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient, schools_fixture: dict):
        """未登录 → 401"""
        resp = await client.get("/api/v1/me/memberships")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_all_memberships(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """u1 返回 A/B 两校 membership"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.get("/api/v1/me/memberships", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        school_ids = {m["school_id"] for m in data}
        assert schools_fixture["schools"]["a"]["id"] in school_ids
        assert schools_fixture["schools"]["b"]["id"] in school_ids

    @pytest.mark.asyncio
    async def test_membership_fields(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """返回字段：role/status/is_default/joined_at/school{...}"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.get("/api/v1/me/memberships", headers=headers)
        for m in resp.json():
            assert "role" in m
            assert "status" in m
            assert "is_default" in m
            assert "joined_at" in m
            assert "school" in m
            assert "id" in m["school"]
            assert "code" in m["school"]
            assert "name" in m["school"]

    @pytest.mark.asyncio
    async def test_default_school_sorted_first(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """默认学校排在前面"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.get("/api/v1/me/memberships", headers=headers)
        data = resp.json()
        # u1 默认学校是 A
        assert data[0]["is_default"] is True
        assert data[0]["school_id"] == schools_fixture["schools"]["a"]["id"]


# ============================================================
# POST /api/v1/schools/{code}/join
# ============================================================
class TestJoinSchool:
    """加入学校接口"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient, schools_fixture: dict):
        """未登录 → 401"""
        resp = await client.post(
            "/api/v1/schools/school-b/join",
            json={},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_join_new_school_creates_active_membership(
        self, client: AsyncClient, schools_fixture: dict, db_session: AsyncSession
    ):
        """u2（仅 A 校）加入 B 校 → 创建 active membership"""
        headers = _auth_headers(schools_fixture["users"]["u2"]["token"])
        resp = await client.post(
            "/api/v1/schools/school-b/join",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["already_member"] is False
        assert data["membership"]["status"] == "active"
        assert data["membership"]["school_id"] == schools_fixture["schools"]["b"]["id"]

        # DB 校验
        db_m = (
            await db_session.execute(
                select(SchoolMembership).where(
                    SchoolMembership.user_id == schools_fixture["users"]["u2"]["id"],
                    SchoolMembership.school_id == schools_fixture["schools"]["b"]["id"],
                )
            )
        ).scalar_one_or_none()
        assert db_m is not None
        assert db_m.status == "active"

    @pytest.mark.asyncio
    async def test_join_idempotent_when_already_member(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """u1 已是 B 校成员 → 幂等返回 already_member=true"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.post(
            "/api/v1/schools/school-b/join",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_member"] is True
        assert data["membership"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_join_upgrades_invited_to_active(
        self, client: AsyncClient, schools_fixture: dict, db_session: AsyncSession
    ):
        """u3 在 A 校是 invited 状态 → 升级为 active"""
        headers = _auth_headers(schools_fixture["users"]["u3"]["token"])
        resp = await client.post(
            "/api/v1/schools/school-a/join",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_member"] is False
        assert data["membership"]["status"] == "active"

        # DB 校验
        await db_session.refresh(
            (
                await db_session.execute(
                    select(SchoolMembership).where(
                        SchoolMembership.user_id == schools_fixture["users"]["u3"]["id"],
                        SchoolMembership.school_id == schools_fixture["schools"]["a"]["id"],
                    )
                )
            ).scalar_one(),
            attribute_names=["status"],
        )

    @pytest.mark.asyncio
    async def test_join_nonexistent_school_returns_404(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """加入不存在的学校 → 404"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.post(
            "/api/v1/schools/nonexistent/join",
            json={},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_join_inactive_school_returns_404(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """加入已停用的学校 → 404"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.post(
            "/api/v1/schools/school-c/join",
            json={},
            headers=headers,
        )
        assert resp.status_code == 404


# ============================================================
# PUT /api/v1/me/default-school
# ============================================================
class TestSetDefaultSchool:
    """设置默认学校接口"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient, schools_fixture: dict):
        """未登录 → 401"""
        resp = await client.put(
            "/api/v1/me/default-school",
            json={"school_id": 1},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_set_default_to_joined_school(
        self,
        client: AsyncClient,
        schools_fixture: dict,
        db_session: AsyncSession,
    ):
        """u1 把默认学校从 A 切换到 B → B 成为默认，A 取消默认"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.put(
            "/api/v1/me/default-school",
            json={"school_id": schools_fixture["schools"]["b"]["id"]},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["default_school_id"] == schools_fixture["schools"]["b"]["id"]
        assert data["membership"]["is_default"] is True

        # A 校 membership 应取消默认
        db_session.expire_all()
        m_a = (
            await db_session.execute(
                select(SchoolMembership).where(
                    SchoolMembership.user_id == schools_fixture["users"]["u1"]["id"],
                    SchoolMembership.school_id == schools_fixture["schools"]["a"]["id"],
                )
            )
        ).scalar_one()
        m_b = (
            await db_session.execute(
                select(SchoolMembership).where(
                    SchoolMembership.user_id == schools_fixture["users"]["u1"]["id"],
                    SchoolMembership.school_id == schools_fixture["schools"]["b"]["id"],
                )
            )
        ).scalar_one()
        assert m_a.is_default is False
        assert m_b.is_default is True

        # user.school_id 同步
        u1 = (
            await db_session.execute(
                select(User).where(User.id == schools_fixture["users"]["u1"]["id"])
            )
        ).scalar_one()
        assert u1.school_id == schools_fixture["schools"]["b"]["id"]

    @pytest.mark.asyncio
    async def test_set_default_to_non_joined_school_returns_404(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """u2 未加入 B 校 → 404"""
        headers = _auth_headers(schools_fixture["users"]["u2"]["token"])
        resp = await client.put(
            "/api/v1/me/default-school",
            json={"school_id": schools_fixture["schools"]["b"]["id"]},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_set_default_to_nonexistent_school_returns_404(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """设置不存在的 school_id → 404"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])
        resp = await client.put(
            "/api/v1/me/default-school",
            json={"school_id": 999999},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_set_default_only_one_default_at_a_time(
        self,
        client: AsyncClient,
        schools_fixture: dict,
        db_session: AsyncSession,
    ):
        """设置默认学校后，再次切换默认，确保仅有一个默认"""
        headers = _auth_headers(schools_fixture["users"]["u1"]["token"])

        # u1 默认是 A，先切换到 B
        await client.put(
            "/api/v1/me/default-school",
            json={"school_id": schools_fixture["schools"]["b"]["id"]},
            headers=headers,
        )
        # 再切换回 A
        resp = await client.put(
            "/api/v1/me/default-school",
            json={"school_id": schools_fixture["schools"]["a"]["id"]},
            headers=headers,
        )
        assert resp.status_code == 200

        db_session.expire_all()
        defaults = (
            await db_session.execute(
                select(SchoolMembership).where(
                    SchoolMembership.user_id == schools_fixture["users"]["u1"]["id"],
                    SchoolMembership.is_default == True,  # noqa: E712
                )
            )
        ).scalars().all()
        assert len(defaults) == 1
        assert defaults[0].school_id == schools_fixture["schools"]["a"]["id"]


# ============================================================
# 集成场景：加入学校后 memberships 列表更新
# ============================================================
class TestJoinThenListMemberships:
    """加入学校后，memberships 列表立即反映新成员关系"""

    @pytest.mark.asyncio
    async def test_join_then_list(
        self, client: AsyncClient, schools_fixture: dict
    ):
        """u2 加入 B 校后，/me/memberships 包含 B 校"""
        headers = _auth_headers(schools_fixture["users"]["u2"]["token"])

        # 加入前
        resp_before = await client.get("/api/v1/me/memberships", headers=headers)
        before_ids = {m["school_id"] for m in resp_before.json()}
        assert schools_fixture["schools"]["b"]["id"] not in before_ids

        # 加入 B 校
        await client.post(
            "/api/v1/schools/school-b/join",
            json={},
            headers=headers,
        )

        # 加入后
        resp_after = await client.get("/api/v1/me/memberships", headers=headers)
        after_ids = {m["school_id"] for m in resp_after.json()}
        assert schools_fixture["schools"]["b"]["id"] in after_ids
