"""ACC-01.3: 找回密码闭环测试

测试覆盖：
- forgot-password: 已注册邮箱返回 token（本地开发）
- forgot-password: 未注册邮箱不返回 token，但返回相同 message
- reset-password: 合法 token + 新密码 → 重置成功
- reset-password: 旧密码不能再登录
- reset-password: 重置后旧 refresh token 失效
- reset-password: 重置后用新密码登录获得新 refresh token 可刷新
- reset-password: 已使用的 token 不能再次使用
- reset-password: 过期的 token 被拒绝
- reset-password: 不存在的 token 被拒绝（统一安全失败提示）
- reset-password: 跨账号场景（token 与 user 强绑定）
"""
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.password_reset_token import PasswordResetToken
from app.api.auth import _hash_token


pytestmark = pytest.mark.asyncio


async def test_forgot_password_registered_email_returns_token(
    client: AsyncClient, test_user: dict
):
    """已注册邮箱发起找回密码，本地开发环境响应中应返回 token。"""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    # 本地开发环境：reset_token 应该返回
    assert data.get("reset_token"), "本地开发环境应在响应中返回 reset_token 供测试"


async def test_forgot_password_unregistered_email_no_token(
    client: AsyncClient,
):
    """未注册邮箱发起找回密码，响应中不应返回 token，但 message 相同。"""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    # 未注册邮箱：不应返回 token
    assert data.get("reset_token") is None


async def test_forgot_password_message_identical(
    client: AsyncClient, test_user: dict
):
    """已注册与未注册邮箱返回的 message 相同（不泄露账号存在性）。"""
    resp_registered = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    resp_unregistered = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert resp_registered.json()["message"] == resp_unregistered.json()["message"]


async def test_reset_password_success(
    client: AsyncClient, test_user: dict
):
    """合法 token + 新密码 → 重置成功。"""
    # 1. 发起找回密码
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]

    # 2. 重置密码
    new_password = "newpassword456"
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert resp.status_code == 200
    assert "已重置" in resp.json()["message"]


async def test_reset_password_old_password_fails(
    client: AsyncClient, test_user: dict
):
    """重置后，旧密码不能再登录。"""
    # 发起找回 + 重置
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "brandnewpass789"},
    )

    # 用旧密码登录应失败
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert resp.status_code == 401


async def test_reset_password_new_password_works(
    client: AsyncClient, test_user: dict
):
    """重置后，新密码可登录。"""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]
    new_password = "brandnewpass789"
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )

    # 新密码登录应成功
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": new_password},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_reset_password_invalidates_old_refresh_token(
    client: AsyncClient, test_user: dict
):
    """重置后，旧 refresh token 失效（不能再刷新）。"""
    # test_user["refresh_token"] 是注册时签发的旧 refresh token
    old_refresh_token = test_user["refresh_token"]

    # 发起找回 + 重置
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "anothernewpass999"},
    )

    # 用旧 refresh token 刷新应失败
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert resp.status_code == 401


async def test_reset_password_new_refresh_token_works(
    client: AsyncClient, test_user: dict
):
    """重置后，用新密码登录获得的新 refresh token 可正常刷新。"""
    # 重置密码
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]
    new_password = "yetanotherpass11"
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )

    # 用新密码登录
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": new_password},
    )
    new_refresh_token = resp.json()["refresh_token"]

    # 用新 refresh token 刷新应成功
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_reset_password_token_cannot_be_reused(
    client: AsyncClient, test_user: dict
):
    """已使用的 token 不能再次使用。"""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]

    # 第一次重置：成功
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "firstnewpass123"},
    )
    assert resp.status_code == 200

    # 第二次重置（同 token）：失败
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "secondnewpass456"},
    )
    assert resp.status_code == 400
    assert "无效或已过期" in resp.json()["detail"]


async def test_reset_password_nonexistent_token_rejected(
    client: AsyncClient,
):
    """不存在的 token 被拒绝（统一安全失败提示）。"""
    fake_token = "a" * 50  # 随机字符串，DB 中不存在
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": fake_token, "new_password": "newpass123456"},
    )
    assert resp.status_code == 400
    assert "无效或已过期" in resp.json()["detail"]


async def test_reset_password_expired_token_rejected(
    client: AsyncClient, test_user: dict, db_session
):
    """过期的 token 被拒绝。"""
    # 发起找回密码
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]

    # 手动把 token 的 expires_at 改为过去时间
    token_hash = _hash_token(reset_token)
    result = await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    )
    prt = result.scalar_one_or_none()
    assert prt is not None
    prt.expires_at = datetime.now() - timedelta(minutes=1)
    await db_session.commit()

    # 用过期 token 重置：失败
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123456"},
    )
    assert resp.status_code == 400
    assert "无效或已过期" in resp.json()["detail"]


async def test_reset_password_cross_account_isolated(
    client: AsyncClient, test_user: dict, second_user: dict
):
    """跨账号场景：A 的 token 不能重置 B 的密码。

    Token 与 user_id 强绑定：DB 查询 token_hash → prt.user_id → 查找 user。
    即使攻击者拿到 A 的 token，也只能重置 A 的密码，无法影响 B。
    """
    # A 发起找回密码
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    a_reset_token = resp.json()["reset_token"]

    # 用 A 的 token 重置，传 B 的新密码（实际上不会影响 B，因为 token 绑定 A.user_id）
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": a_reset_token, "new_password": "attackerpass123"},
    )
    assert resp.status_code == 200

    # A 的旧密码失效（说明重置的是 A）
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert resp.status_code == 401

    # B 的密码未受影响（仍然可登录）
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": second_user["email"], "password": second_user["password"]},
    )
    assert resp.status_code == 200


async def test_reset_password_db_stores_hash_not_plaintext(
    client: AsyncClient, test_user: dict, db_session
):
    """DB 中存的是 token 哈希，不是明文。"""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )
    reset_token = resp.json()["reset_token"]

    # 查 DB 中所有 PasswordResetToken 记录的 token_hash
    result = await db_session.execute(select(PasswordResetToken))
    tokens = result.scalars().all()
    assert len(tokens) > 0

    # DB 中不应有任何 token_hash 等于明文 token
    for t in tokens:
        assert t.token_hash != reset_token
        # 但应该是 reset_token 的 SHA-256 哈希
        if t.token_hash == _hash_token(reset_token):
            # 找到了对应的记录，OK
            break
    else:
        pytest.fail("DB 中未找到与 reset_token 匹配的哈希记录")


async def test_forgot_password_creates_db_record(
    client: AsyncClient, test_user: dict, db_session
):
    """发起找回密码后，DB 中应创建一条 PasswordResetToken 记录。"""
    # 先记下当前数量
    result = await db_session.execute(select(PasswordResetToken))
    before_count = len(result.scalars().all())

    await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user["email"]},
    )

    # 重新查询
    await db_session.rollback()  # 清除 session 缓存
    result = await db_session.execute(select(PasswordResetToken))
    after_count = len(result.scalars().all())

    assert after_count == before_count + 1


async def test_register_uses_x_school_code_header(
    client: AsyncClient, test_school: dict
):
    """ACC-01.2: register 接受 X-School-Code 头解析 school_id（优先于 body）。"""
    # body 中传一个不存在的 school_id（如 99999），但 X-School-Code 头指向 test_school
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "headeruser@example.com",
            "nickname": "HeaderUser",
            "password": "securepassword",
            "school_id": 99999,  # 故意传一个无效 ID
        },
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    data = response.json()
    # 用户实际 school_id 应为 X-School-Code 解析的 test_school.id，而非 body 中的 99999
    assert data["user"]["school_id"] == test_school["id"]
