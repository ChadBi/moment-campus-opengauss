"""B-01: 校园身份认证接口测试。

覆盖：域名校验、验证码一次性、认证状态、已认证拦截、权限校验。
"""
import pytest
import pytest_asyncio

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


@pytest.mark.asyncio
async def test_send_returns_code_in_dev(
    client, auth_headers, test_school_domain: dict
):
    """dev 模式：合法域名发送返回验证码。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]
    assert body["code"] is not None
    assert len(body["code"]) == 6


@pytest.mark.asyncio
async def test_send_rejects_invalid_domain(client, auth_headers, test_school_domain: dict):
    """域名不匹配本校允许域名 → 400。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@gmail.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_success_marks_verified(
    client, auth_headers, test_school_domain: dict
):
    """发送后确认 → campus_verified=True，GET /me 返回认证状态。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=auth_headers,
    )).json()
    code = send["code"]

    confirm = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": code},
        headers=auth_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["campus_verified"] is True

    me = (await client.get("/api/v1/users/me", headers=auth_headers)).json()
    assert me["campus_verified"] is True


@pytest.mark.asyncio
async def test_confirm_wrong_code(client, auth_headers, test_school_domain: dict):
    """错误验证码 → 400。"""
    await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": "000000"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_code_single_use(client, auth_headers, test_school_domain: dict):
    """验证码一次性：使用后再次使用 → 400。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=auth_headers,
    )).json()
    code = send["code"]

    first = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": code},
        headers=auth_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": code},
        headers=auth_headers,
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_already_verified_cannot_send_again(
    client, auth_headers, test_school_domain: dict
):
    """已认证用户不能再发起/确认认证。"""
    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn"},
        headers=auth_headers,
    )).json()
    await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"student_id": "20260001", "campus_email": "stu@test-uni.edu.cn", "code": send["code"]},
        headers=auth_headers,
    )

    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        json={"student_id": "20260002", "campus_email": "stu@test-uni.edu.cn"},
        headers=auth_headers,
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