import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_approve_post_creates_audit_notification(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
):
    """管理员审核通过后，帖子作者能在通知中心看到审核通知。"""
    response = await client.put(
        f"/api/v1/admin/posts/{test_post['id']}/approve",
        json={"reason": "内容真实有效"},
        headers=admin_headers,
    )
    assert response.status_code == 200

    detail_response = await client.get(f"/api/v1/posts/{test_post['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "published"

    notifications_response = await client.get("/api/v1/notifications", headers=auth_headers)
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()["items"]
    assert any(
        item["type"] == "audit"
        and item["target_type"] == "post"
        and item["target_id"] == test_post["id"]
        and "审核通过" in item["title"]
        for item in notifications
    )


@pytest.mark.asyncio
async def test_comment_creates_notification_for_post_author(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    test_post: dict,
):
    """他人评论帖子后，帖子作者能在通知中心看到评论通知。"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/comments",
        json={"content": "这是一条通知回归测试评论"},
        headers=second_auth_headers,
    )
    assert response.status_code == 201

    notifications_response = await client.get("/api/v1/notifications", headers=auth_headers)
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()["items"]
    assert any(
        item["type"] == "comment"
        and item["target_type"] == "post"
        and item["target_id"] == test_post["id"]
        and "新评论" in item["title"]
        for item in notifications
    )
