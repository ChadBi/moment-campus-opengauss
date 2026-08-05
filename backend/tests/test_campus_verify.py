"""B-01: 校园身份认证接口测试。

覆盖：域名校验、token/验证码流程、一次性、认证状态、已认证拦截、权限校验。
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


@pytest_asyncio.fixture
async def unverified_auth_headers(client: AsyncClient, test_school: dict) -> dict:
    """注册未认证用户并返回其鉴权头。"""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "verifyuser@example.com",
            "nickname": "认证测试用户",
            "password": "testpassword123",
            "school_id": test_school["id"],
        },
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_send_returns_code_and_link_in_dev(
    client, unverified_auth_headers, test_school_domain: dict
):
    """dev 模式：合法域名发送返回验证凭证与验证链接。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]
    assert body["code"] is not None
    assert body["verify_link"] is not None
    assert "token=" in body["verify_link"]


@pytest.mark.asyncio
async def test_send_rejects_invalid_domain(
    client, unverified_auth_headers, test_school_domain: dict
):
    """域名不匹配本校允许域名 → 400。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@gmail.com"},
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_success_marks_verified(
    client, unverified_auth_headers, test_school_domain: dict
):
    """发送后确认（code 凭证）→ campus_verified=True，GET /me 返回认证状态。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )).json()
    code = send["code"]

    confirm = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": code},
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
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )).json()
    token = send["code"]  # code 与 token 为同一凭证（双通道）

    confirm = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "token": token},
        headers=unverified_auth_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["campus_verified"] is True


@pytest.mark.asyncio
async def test_confirm_wrong_code(client, unverified_auth_headers, test_school_domain: dict):
    """错误验证凭证 → 400。"""
    await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )
    resp = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": "000000"},
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
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )).json()
    code = send["code"]

    first = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": code},
        headers=unverified_auth_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": code},
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
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )).json()
    await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": send["code"]},
        headers=unverified_auth_headers,
    )

    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260002", "campus_email": "stu@test-uni.edu.cn"},
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_requires_auth(client):
    """未登录发起认证 → 401。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
    )
    assert resp.status_code == 401
