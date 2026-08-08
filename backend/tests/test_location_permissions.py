"""地点新增权限定向测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def _register_user(client: AsyncClient, school_id: int, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "nickname": "地点权限测试",
            "password": "testpassword123",
            "school_id": school_id,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_location_requires_campus_verification(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """未完成校园认证的普通用户不能新增地点。"""
    headers = await _register_user(client, test_school["id"], "location-gate@example.com")
    user = (await db_session.execute(
        select(User).where(User.email == "location-gate@example.com")
    )).scalar_one()
    user.campus_verified = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/locations",
        json={"name": "未认证地点", "latitude": 31.5, "longitude": 120.3},
        headers={**headers, "X-School-Code": test_school["code"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_location_without_campus_verification(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """管理员保留地点管理权限，不要求单独完成校园认证。"""
    headers = await _register_user(client, test_school["id"], "location-admin@example.com")
    user = (await db_session.execute(
        select(User).where(User.email == "location-admin@example.com")
    )).scalar_one()
    user.campus_verified = False
    user.role = "admin"
    await db_session.commit()

    response = await client.post(
        "/api/v1/locations",
        json={"name": "管理员新增地点", "latitude": 31.5, "longitude": 120.3},
        headers={**headers, "X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    assert response.json()["is_verified"] is False
