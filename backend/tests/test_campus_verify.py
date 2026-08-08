"""B-01: 校园身份认证接口测试（统一教育邮箱方案）。

覆盖：域名校验（用登录邮箱域名）、token/验证码流程、一次性、认证状态、
已认证拦截、权限校验。

统一教育邮箱后：认证 = 向当前登录邮箱发码验证，无需单独 campus_email/student_id。
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash, create_access_token
from app.models.school_domain import SchoolDomain
from app.models.user import User
from app.models.school_membership import SchoolMembership


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
async def test_send_returns_six_digit_code_without_link_in_dev(
    client, unverified_auth_headers, test_school_domain: dict
):
    """dev 模式：登录邮箱命中允许域名 → 发送返回 6 位数字验证码，不返回链接。"""
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=unverified_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]
    assert body["code"] is not None
    assert len(body["code"]) == 6
    assert body["code"].isdigit()
    assert body.get("verify_link") is None


@pytest.mark.asyncio
async def test_send_rejects_non_school_domain(
    client, test_school: dict, test_school_domain: dict, db_session
):
    """登录邮箱域名不在允许域名内 → send campus verify 400。

    因为注册阶段本身也会对非允许域 400，这里不走 /register，而是直接在
    DB 中插入 Gmail 用户并签发 access token，从而精准验证 send 接口的
    域名校验逻辑（而非 register 的）。
    """
    # 1. 直接插入用户（跳过注册阶段域名校验）
    import time
    from datetime import datetime
    email = f"baduser_{time.time_ns()}@gmail.com"
    user = User(
        email=email,
        nickname="baduser",
        password_hash=get_password_hash("testpass123"),
        school_id=test_school["id"],
        campus_verified=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db_session.add(user)
    await db_session.flush()
    uid = user.id
    db_session.add(SchoolMembership(
        user_id=uid, school_id=test_school["id"], role="user",
        joined_at=datetime.now(), created_at=datetime.now(),
    ))
    await db_session.commit()

    # 2. 签发 access token 构造鉴权头
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(uid)})}"}

    # 3. 发起认证 → 400：gmail.com 不在允许域，也不在全局测试域（仅 qq.com）
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
async def test_confirm_with_six_digit_code(
    client, unverified_auth_headers, test_school_domain: dict
):
    """6 位数字验证码确认生效。"""
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


@pytest.mark.asyncio
async def test_qq_email_user_send_verification_returns_200_no_extra_params(
    client: AsyncClient, test_school: dict, test_school_domain: dict
):
    """@qq.com 注册用户（全局测试域白名单）：send 空 body/不传参数 → 200 + 6 位数字验证码。

    验证点：认证阶段域名校验必须和注册阶段保持一致（使用同款 allowlist 逻辑）。
    qq.com 用户应当和教育邮箱用户走完全一致的直接认证流程，不需要额外输入框。
    """
    import time
    headers = await _register(
        client, f"qq_verify_{time.time_ns()}@qq.com", test_school["id"]
    )
    resp = await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["message"]
    assert body["code"] is not None
    assert len(body["code"]) == 6
    assert body["code"].isdigit()
    assert body.get("verify_link") is None


@pytest.mark.asyncio
async def test_qq_email_user_full_verify_confirms_and_marks_verified(
    client: AsyncClient, test_school: dict, test_school_domain: dict
):
    """@qq.com 注册用户全链路：空 body send → confirm → campus_verified=True 不变更邮箱。

    验证点：confirm 成功后 GET /me 的 email 仍是登录的 qq.com 邮箱（不要乱改用户邮箱），
    但 campus_verified=True。与教育邮箱注册用户行为完全一致。
    """
    import time
    qq_email = f"qq_verify_full_{time.time_ns()}@qq.com"
    headers = await _register(client, qq_email, test_school["id"])

    send = (await client.post(
        "/api/v1/users/me/verify-campus/send",
        headers=headers,
    )).json()
    assert send["code"] is not None

    confirm = await client.post(
        "/api/v1/users/me/verify-campus/confirm",
        json={"code": send["code"]},
        headers=headers,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["campus_verified"] is True

    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["campus_verified"] is True
    assert me["email"].lower() == qq_email
