import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school_membership import SchoolMembership
from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, test_school: dict):
    """Test successful user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "nickname": "新用户",
            "password": "securepassword",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user: dict, test_school: dict):
    """Test registration with an already registered email returns 409."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": test_user["email"],
            "nickname": "另一个昵称",
            "password": "anotherpassword",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 409
    assert "已被注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: dict):
    """Test successful login with correct credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: dict):
    """Test login with wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert "密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    """Test login with non-existent email returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "somepassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, test_user: dict):
    """Test successful token refresh."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": test_user["refresh_token"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Verify new tokens are valid (they may be identical if generated in the same second)
    assert data["access_token"] is not None


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test refresh with invalid token returns 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_with_access_token(client: AsyncClient, test_user: dict):
    """Test refresh endpoint rejects an access token (wrong type)."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": test_user["access_token"]},
    )
    assert response.status_code == 401
    assert "token 类型" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint returns success."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert "登出成功" in response.json()["message"]


@pytest.mark.asyncio
async def test_register_without_school_returns_400(client: AsyncClient):
    """2026-08-01 起注册需确定学校：未提供 school_id 且无 X-School-Code 头 → 400"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "noschool@example.com",
            "nickname": "无学校用户",
            "password": "securepassword",
        },
    )
    assert response.status_code == 400
    assert "无法确定注册学校" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_with_x_school_code_header_succeeds(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """2026-08-01 起：未提供 school_id 时回退到 X-School-Code 头解析学校"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "header-school@example.com",
            "nickname": "头部学校用户",
            "password": "securepassword",
        },
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["school_id"] == test_school["id"]

    # membership 已创建（active + is_default=True + role=member）
    user = (
        await db_session.execute(select(User).where(User.email == "header-school@example.com"))
    ).scalar_one()
    membership = (
        await db_session.execute(
            select(SchoolMembership).where(
                SchoolMembership.user_id == user.id,
                SchoolMembership.school_id == test_school["id"],
            )
        )
    ).scalar_one_or_none()
    assert membership is not None
    assert membership.status == "active"
    assert membership.is_default is True
    assert membership.role == "member"


# ============================================================
# B-01 注册阶段教育邮箱强制校验（SchoolDomain 拦截）
# 说明：pytest 不 seed 三校，每个用例在事务内临时自建 1 所学校 + 对应 SchoolDomain
#       （测试结束自动回滚，不污染其他用例）。
# ============================================================


async def _seed_school_with_domains(db_session: AsyncSession, suffix: str, domains: list[str]):
    """在当前测试事务里自建一所临时学校（含其 1~N 条 SchoolDomain），返回学校 dict。"""
    from app.models.school import School
    from app.models.school_domain import SchoolDomain
    import time as _t
    short_code = f"t{suffix}{_t.time_ns() % 10000000:07d}"  # 保证 <=20 字，唯一
    school = School(
        name=f"测试校-{suffix}",
        code=short_code,
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()
    for i, d in enumerate([x.strip().lower().lstrip("@") for x in domains if x.strip()]):
        db_session.add(SchoolDomain(
            school_id=school.id,
            domain=d,
            is_primary=(i == 0),
        ))
    await db_session.commit()
    return {"id": school.id, "name": school.name, "code": school.code, "domains": domains}


@pytest.mark.asyncio
async def test_register_email_domain_mismatch_returns_400(client: AsyncClient, db_session: AsyncSession):
    """邮箱注册：选临时学校（有 SchoolDomain），但传 gmail 邮箱 → 后端 400 拦，提示使用该校官方教育邮箱。"""
    jn = await _seed_school_with_domains(
        db_session,
        suffix="jn",
        domains=["jiangnan.edu.cn", "stu.jiangnan.edu.cn", "example.jiangnan.edu.cn"],
    )

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "random_jiangnan@gmail.com",
            "password": "pass12345",
            "nickname": "gmail用户",
            "school_id": jn["id"],
        },
    )
    assert resp.status_code == 400
    assert "官方教育邮箱" in resp.json()["detail"]
    assert jn["name"] in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_email_domain_example_match_returns_200(client: AsyncClient, db_session: AsyncSession):
    """邮箱注册：选临时江南校，传 @example.jiangnan.edu.cn（附加域名）→ 200 成功且自动校园认证。

    邮箱域名完全命中该校 SchoolDomain → 自动设置 campus_verified=True 并记录认证时间，
    免去用户重新走 send/confirm 邮箱验证码流程。
    """
    jn = await _seed_school_with_domains(
        db_session,
        suffix="jn2",
        domains=["jiangnan.edu.cn", "example.jiangnan.edu.cn"],
    )
    unique_email = f"new_user_{__import__('time').time_ns()}@example.jiangnan.edu.cn"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "教育邮箱新生",
            "school_id": jn["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == unique_email
    # 命中 addl_domains（example.jiangnan.edu.cn）→ 自动认证
    assert body["user"]["campus_verified"] is True


@pytest.mark.asyncio
async def test_register_momentcampus_com_whitelist_returns_200(client: AsyncClient, db_session: AsyncSession):
    """邮箱注册：临时复旦校有 SchoolDomain 但不包含 momentcampus.com → 因豁免域白名单，注册仍成功。"""
    fd = await _seed_school_with_domains(
        db_session,
        suffix="fd",
        domains=["fudan.edu.cn", "example.fudan.edu.cn"],
    )
    unique_email = f"ops_fudan_{__import__('time').time_ns()}@momentcampus.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "复旦运营小号",
            "school_id": fd["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == unique_email
    assert resp.json()["user"]["campus_verified"] is False


@pytest.mark.asyncio
async def test_register_qq_com_global_test_domain_returns_200(client: AsyncClient, db_session: AsyncSession):
    """邮箱注册：临时学校有严格 SchoolDomain（不含 qq.com）→ qq.com 作为全局测试邮箱白名单域仍放行，200。"""
    jn = await _seed_school_with_domains(
        db_session,
        suffix="jnQQ",
        domains=["jiangnan.edu.cn", "stu.jiangnan.edu.cn", "example.jiangnan.edu.cn"],
    )
    unique_email = f"qq_tester_{__import__('time').time_ns()}@qq.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "QQ邮箱测试者",
            "school_id": jn["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == unique_email
    assert resp.json()["user"]["campus_verified"] is False


@pytest.mark.asyncio
async def test_register_school_with_empty_domains_allows_any_email(client: AsyncClient, test_school: dict, db_session: AsyncSession):
    """邮箱注册：test_school 未配置任何 SchoolDomain（配置期极端场景）→ 允许任意邮箱注册，不 400 死锁。"""
    # 先断言 test_school 确实没配任何 domains（保证用例正确性）
    schools_resp = await client.get("/api/v1/schools")
    my_school = next((s for s in schools_resp.json() if s["id"] == test_school["id"]), None)
    assert my_school is not None
    assert len(my_school["domains"]) == 0, "本用例依赖 test_school 没有 SchoolDomains（conftest 创建 test-uni 时本就没配）"

    unique_email = f"temp_user_{__import__('time').time_ns()}@outlook.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "临时用户（空域名阶段）",
            "school_id": test_school["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == unique_email
    assert resp.json()["user"]["campus_verified"] is False

