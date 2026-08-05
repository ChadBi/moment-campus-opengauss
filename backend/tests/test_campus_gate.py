"""UC-01 / D4: 未认证全站只读门禁测试

验证：未完成校园身份认证（campus_verified=False）的用户，
对所有写操作端点（发帖/评论/点赞/评价/协同验证/订阅）均返回 403；
完成认证后恢复正常写权限。
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def unverified_user(client: AsyncClient, test_school: dict) -> dict:
    """注册一个未完成校园认证的测试用户（campus_verified=False，默认注册态）。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "unverified@example.com",
            "nickname": "未认证用户",
            "password": "testpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["campus_verified"] is False
    return {
        "id": data["user"]["id"],
        "email": "unverified@example.com",
        "access_token": data["access_token"],
        "school_id": test_school["id"],
    }


@pytest_asyncio.fixture
async def unverified_headers(unverified_user: dict) -> dict:
    return {"Authorization": f"Bearer {unverified_user['access_token']}"}


# ------------------------------------------------------------
# 未认证用户写操作全部 403
# ------------------------------------------------------------

async def test_unverified_cannot_create_post(
    client: AsyncClient, unverified_headers: dict, test_category: dict
):
    res = await client.post(
        "/api/v1/posts",
        json={
            "title": "未认证发帖",
            "content": "未认证用户不应该能发布内容",
            "category_id": test_category["id"],
            "is_anonymous": False,
        },
        headers=unverified_headers,
    )
    assert res.status_code == 403


async def test_unverified_cannot_create_comment(
    client: AsyncClient, unverified_headers: dict, test_post: dict
):
    res = await client.post(
        f"/api/v1/posts/{test_post['id']}/comments",
        json={"content": "未认证评论"},
        headers=unverified_headers,
    )
    assert res.status_code == 403


async def test_unverified_cannot_like(
    client: AsyncClient, unverified_headers: dict, test_post: dict
):
    res = await client.post(
        f"/api/v1/posts/{test_post['id']}/like",
        headers=unverified_headers,
    )
    assert res.status_code == 403


async def test_unverified_cannot_validate(
    client: AsyncClient, unverified_headers: dict, test_post: dict
):
    res = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation", "comment": "未认证验证"},
        headers=unverified_headers,
    )
    assert res.status_code == 403


async def test_unverified_cannot_submit_location_review(
    client: AsyncClient, unverified_headers: dict, db_session, test_school: dict
):
    """未认证用户无法提交地点评价。"""
    from sqlalchemy import select
    from app.models.location import Location
    loc = (
        await db_session.execute(
            select(Location).where(Location.school_id == test_school["id"]).limit(1)
        )
    ).scalar_one_or_none()
    if loc is None:
        pytest.skip("测试学校无地点数据")
    res = await client.post(
        f"/api/v1/locations/{loc.id}/reviews",
        json={"score": 5, "content": "未认证评价"},
        headers=unverified_headers,
    )
    assert res.status_code == 403


async def test_unverified_cannot_subscribe(
    client: AsyncClient, unverified_headers: dict, test_category: dict
):
    res = await client.post(
        "/api/v1/subscriptions",
        json={"target_type": "category", "target_id": test_category["id"]},
        headers=unverified_headers,
    )
    assert res.status_code == 403


# ------------------------------------------------------------
# 已认证用户写操作正常（对照）
# ------------------------------------------------------------

async def test_verified_user_can_create_post(
    client: AsyncClient, auth_headers: dict, test_category: dict
):
    res = await client.post(
        "/api/v1/posts",
        json={
            "title": "已认证用户发帖",
            "content": "已认证用户可以正常发布内容",
            "category_id": test_category["id"],
            "is_anonymous": False,
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
