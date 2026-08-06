"""B-01: 校园身份认证接口测试（统一教育邮箱方案）。

覆盖：域名校验（用登录邮箱域名）、token/验证码流程、一次性、认证状态、
已认证拦截、权限校验。

统一教育邮箱后：认证 = 向当前登录邮箱发码验证，无需单独 campus_email/student_id。
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.school_domain import SchoolDomain


@pytest_asyncio.fixture
async def test_school_domain(db_session, test_school: dict) -> dict:
    """为测试学校创建允许域名（B-01 域名校验依赖）。"""
    domain = "test-uni.edu.cn"
    db_session.add(SchoolDomain(
        school_id=test_school["id"],
        domain=domain,
        is_primary=True,
    ))
    await db_session.commit()
    return {"school_id": test_school["id"], "domain": domain}


async def _register(client: AsyncClient, email: str, school_id: int) -> dict:
    """注册指定邮箱用户并返回鉴权头。"""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "nickname": "认证测试用户",
            "password": "testpassword123",
            "school_id": school_id,
        },
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def unverified_auth_headers(
    client: AsyncClient, test_school: dict, test_school_domain: dict
) -> dict:
    """注册「登录邮箱命中允许域名」的未认证用户。"""
    return await _register(client, "verifyuser@test-uni.edu.cn", test_school["id"])


@pytest.mark.asyncio
async def test_send_returns_code_and_link_in_dev(
    client, unverified_auth_headers, test_school_domain: dict
):
    """dev 模式：登录邮箱命中允许域名 → 发送返回验证凭证与验证链接。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]
    assert body["code"] is not None
    assert body["verify_link"] is not None
    assert "token=" in body["verify_link"]


@pytest.mark.asyncio
async def test_send_rejects_non_school_domain(client, test_school: dict):
    """登录邮箱域名不在允许域名内 → 400。"""
    headers = await _register(client, "baduser@gmail.com", test_school["id"])
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_success_marks_verified(
    client, unverified_auth_headers, test_school_domain: dict
):
    """发送后确认（code 凭证）→ campus_verified=True，GET /me 返回认证状态。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )).json()
    code = send["code"]

    confirm = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"code": code},
        headers=unverified_auth_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["campus_verified"] is True

    me = (await client.get("/api/v1/users/me", headers=unverified_auth_headers)).json()
    assert me["campus_verified"] is True


@pytest.mark.asyncio
async def test_confirm_with_token_credential(
    client, unverified_auth_headers, test_school_domain: dict
):
    """token 凭证（验证链接中的值）确认同样生效。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )).json()
    token = send["code"]  # code 与 token 为同一凭证（双通道）

    confirm = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"token": token},
        headers=unverified_auth_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["campus_verified"] is True


@pytest.mark.asyncio
async def test_confirm_wrong_code(client, unverified_auth_headers, test_school_domain: dict):
    """错误验证凭证 → 400。"""
    await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )
    resp = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"code": "000000"},
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_code_single_use(
    client, unverified_auth_headers, test_school_domain: dict
):
    """验证凭证一次性：使用后再次使用 → 400。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )).json()
    code = send["code"]

    first = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"code": code},
        headers=unverified_auth_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"code": code},
        headers=unverified_auth_headers,
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_already_verified_cannot_send_again(
    client, unverified_auth_headers, test_school_domain: dict
):
    """已认证用户不能再发起/确认认证。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )).json()
    await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"code": send["code"]},
        headers=unverified_auth_headers,
    )

    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_requires_auth(client):
    """未登录发起认证 → 401。"""
    resp = await client.post("/api/v1/users/me/verify-campus/send")
    assert resp.status_code == 401