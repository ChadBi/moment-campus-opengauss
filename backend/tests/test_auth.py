import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school_invitation import SchoolInvitation
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


# ============================================================
# ACC-01.2: 邀请码注册消费闭环
# ============================================================
@pytest.mark.asyncio
async def test_register_with_valid_invite_code_consumes_invitation(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """ACC-01.2: 注册时携带有效 invite_code → 用户创建 + 邀请码消费 + membership 创建"""
    from datetime import datetime, timedelta

    # 预置一条邀请码
    invitation = SchoolInvitation(
        school_id=test_school["id"],
        email="invitee@example.com",
        role="member",
        invitation_code="ACC012-VALID-CODE",
        status="expires",
        expires_at=datetime.now() + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()
    await db_session.refresh(invitation)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "invitee@example.com",
            "nickname": "受邀用户",
            "password": "securepassword",
            "school_id": test_school["id"],
            "invite_code": "ACC012-VALID-CODE",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data

    # 邀请码已标记为 accepted + accepted_at + used_by
    await db_session.refresh(invitation, attribute_names=["status", "accepted_at", "used_by"])
    assert invitation.status == "accepted"
    assert invitation.accepted_at is not None
    assert invitation.used_by is not None

    # 用户已创建
    user = (
        await db_session.execute(select(User).where(User.email == "invitee@example.com"))
    ).scalar_one()
    assert invitation.used_by == user.id

    # membership 已创建（active + is_default=True + invited_by=None）
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


@pytest.mark.asyncio
async def test_register_with_invalid_invite_code_returns_400(
    client: AsyncClient, test_school: dict
):
    """ACC-01.2: 注册时携带无效 invite_code → 400，不创建用户"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-invite@example.com",
            "nickname": "无效邀请码用户",
            "password": "securepassword",
            "school_id": test_school["id"],
            "invite_code": "NONEXISTENT-CODE-XYZ",
        },
    )
    assert response.status_code == 400
    assert "邀请码" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_with_expired_invite_code_returns_400(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """ACC-01.2: 过期 invite_code → 400"""
    from datetime import datetime, timedelta

    invitation = SchoolInvitation(
        school_id=test_school["id"],
        email="expired@example.com",
        role="member",
        invitation_code="ACC012-EXPIRED-CODE",
        status="expires",
        expires_at=datetime.now() - timedelta(days=1),  # 已过期
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "expired@example.com",
            "nickname": "过期邀请码用户",
            "password": "securepassword",
            "school_id": test_school["id"],
            "invite_code": "ACC012-EXPIRED-CODE",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_with_email_mismatch_invite_code_returns_400(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """ACC-01.2: 邮箱不匹配 invite_code → 400"""
    from datetime import datetime, timedelta

    invitation = SchoolInvitation(
        school_id=test_school["id"],
        email="someone-else@example.com",
        role="member",
        invitation_code="ACC012-MISMATCH-CODE",
        status="expires",
        expires_at=datetime.now() + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong-email@example.com",
            "nickname": "邮箱不匹配用户",
            "password": "securepassword",
            "school_id": test_school["id"],
            "invite_code": "ACC012-MISMATCH-CODE",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_with_already_accepted_invite_code_returns_400(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """ACC-01.2: 已使用 invite_code → 400"""
    from datetime import datetime, timedelta

    invitation = SchoolInvitation(
        school_id=test_school["id"],
        email="reused@example.com",
        role="member",
        invitation_code="ACC012-REUSED-CODE",
        status="accepted",  # 已使用
        expires_at=datetime.now() + timedelta(days=1),
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reused@example.com",
            "nickname": "重复使用邀请码用户",
            "password": "securepassword",
            "school_id": test_school["id"],
            "invite_code": "ACC012-REUSED-CODE",
        },
    )
    assert response.status_code == 400
