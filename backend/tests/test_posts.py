import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_posts_empty(client: AsyncClient):
    """Test listing posts when there are none returns empty list."""
    response = await client.get("/api/v1/posts")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_posts_with_data(client: AsyncClient, db_session, test_user: dict, test_school: dict, test_category: dict, test_post_type: dict):
    """Test listing posts returns published posts."""
    from app.models.post import Post
    from app.core.security import decode_token
    # Get user_id from the test_user token
    payload = decode_token(test_user["access_token"])
    user_id = int(payload["sub"])
    # Create a published post directly in DB (new posts default to "pending")
    post = Post(
        user_id=user_id,
        school_id=test_school["id"],
        category_id=test_category["id"],
        post_type_id=test_post_type["id"],
        title="已发布的帖子",
        content="这是已发布帖子的内容，至少十个字符",
        status="published",
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    response = await client.get("/api/v1/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(p["id"] == post.id for p in data["items"])


@pytest.mark.asyncio
async def test_list_posts_pagination(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict, test_post_type: dict):
    """Test pagination parameters work correctly."""
    # Create multiple posts
    for i in range(3):
        await client.post(
            "/api/v1/posts",
            json={
                "title": f"分页测试帖子 {i}",
                "content": "这是分页测试帖子的内容，至少十个字符",
                "category_id": test_category["id"],
                "post_type_id": test_post_type["id"],
            },
            headers=auth_headers,
        )

    response = await client.get("/api/v1/posts?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_get_post_detail(client: AsyncClient, test_post: dict):
    """Test getting a specific post by ID."""
    response = await client.get(f"/api/v1/posts/{test_post['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_post["id"]
    assert data["title"] == test_post["title"]
    assert data["content"] == test_post["content"]


@pytest.mark.asyncio
async def test_get_post_detail_increments_view(client: AsyncClient, test_post: dict):
    """Test that viewing a post increments view_count."""
    response1 = await client.get(f"/api/v1/posts/{test_post['id']}")
    view_count_1 = response1.json()["view_count"]

    response2 = await client.get(f"/api/v1/posts/{test_post['id']}")
    view_count_2 = response2.json()["view_count"]

    assert view_count_2 == view_count_1 + 1


@pytest.mark.asyncio
async def test_get_post_not_found(client: AsyncClient):
    """Test getting a non-existent post returns 404."""
    response = await client.get("/api/v1/posts/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_post_authenticated(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict, test_post_type: dict):
    """Test creating a post with authentication."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "新创建的帖子",
            "content": "这是新创建帖子的内容，至少十个字符",
            "category_id": test_category["id"],
            "post_type_id": test_post_type["id"],
            "is_anonymous": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "新创建的帖子"
    assert data["content"] == "这是新创建帖子的内容，至少十个字符"
    assert data["status"] == "pending"  # New posts need review
    assert data["category_id"] == test_category["id"]


@pytest.mark.asyncio
async def test_create_post_unauthenticated(client: AsyncClient, test_category: dict, test_post_type: dict):
    """Test creating a post without authentication returns 401."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "未认证帖子",
            "content": "这个帖子不应该被创建",
            "category_id": test_category["id"],
            "post_type_id": test_post_type["id"],
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_post_with_tags(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict, test_post_type: dict):
    """Test creating a post with tags."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "带标签的帖子",
            "content": "这是带标签帖子的内容，至少十个字符",
            "category_id": test_category["id"],
            "post_type_id": test_post_type["id"],
            "tags": ["测试", "标签"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tags"] is not None
    tag_names = [t["name"] for t in data["tags"]]
    assert "测试" in tag_names
    assert "标签" in tag_names


@pytest.mark.asyncio
async def test_update_post_owner(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test updating a post as the owner."""
    response = await client.put(
        f"/api/v1/posts/{test_post['id']}",
        json={"title": "更新后的标题", "content": "更新后的内容，至少十个字符"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "更新后的标题"
    assert data["content"] == "更新后的内容，至少十个字符"


@pytest.mark.asyncio
async def test_update_post_not_owner(client: AsyncClient, second_auth_headers: dict, test_post: dict):
    """Test updating a post as a non-owner returns 403."""
    response = await client.put(
        f"/api/v1/posts/{test_post['id']}",
        json={"title": "非法修改标题"},
        headers=second_auth_headers,
    )
    assert response.status_code == 403
    assert "没有权限" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_post_not_found(client: AsyncClient, auth_headers: dict):
    """Test updating a non-existent post returns 404."""
    response = await client.put(
        "/api/v1/posts/99999",
        json={"title": "不存在的帖子"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_post_owner(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict, test_post_type: dict):
    """Test deleting a post as the owner."""
    # Create a post to delete
    create_response = await client.post(
        "/api/v1/posts",
        json={
            "title": "待删除的帖子",
            "content": "这个帖子将被删除，至少十个字符",
            "category_id": test_category["id"],
            "post_type_id": test_post_type["id"],
        },
        headers=auth_headers,
    )
    post_id = create_response.json()["id"]

    # Delete the post
    delete_response = await client.delete(
        f"/api/v1/posts/{post_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200
    assert "删除成功" in delete_response.json()["message"]

    # Verify the post is soft-deleted (should return 404)
    get_response = await client.get(f"/api/v1/posts/{post_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_post_not_owner(client: AsyncClient, second_auth_headers: dict, test_post: dict):
    """Test deleting a post as a non-owner returns 403."""
    response = await client.delete(
        f"/api/v1/posts/{test_post['id']}",
        headers=second_auth_headers,
    )
    assert response.status_code == 403
    assert "没有权限" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_post_not_found(client: AsyncClient, auth_headers: dict):
    """Test deleting a non-existent post returns 404."""
    response = await client.delete(
        "/api/v1/posts/99999",
        headers=auth_headers,
    )
    assert response.status_code == 404
