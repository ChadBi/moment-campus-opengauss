import pytest
from httpx import AsyncClient
import warnings

from app.schemas.post import PostListResponse, UserBrief


def test_post_list_author_assignment_is_validated_before_serialization():
    """字典作者赋值后应转为 UserBrief，序列化不得产生类型不匹配警告。"""
    post = PostListResponse(
        id=1,
        user_id=2,
        title="序列化测试帖子",
        content="这是用于验证作者序列化的测试内容",
        created_at="2026-08-01T00:00:00",
    )

    post.author = {"id": 2, "nickname": "测试用户", "avatar_url": None}

    assert isinstance(post.author, UserBrief)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert post.model_dump()["author"]["nickname"] == "测试用户"


@pytest.mark.asyncio
async def test_list_posts_empty(client: AsyncClient, test_school: dict):
    """Test listing posts when there are none returns empty list.

    TEN-02: 需通过 X-School-Code 头提供租户上下文，否则列表接口返回 404。
    """
    response = await client.get(
        "/api/v1/posts",
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_posts_with_data(client: AsyncClient, db_session, test_user: dict, test_school: dict, test_category: dict):
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
        title="已发布的帖子",
        content="这是已发布帖子的内容，至少十个字符",
        status="published",
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    # TEN-02: 通过 X-School-Code 头提供租户上下文
    response = await client.get(
        "/api/v1/posts",
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(p["id"] == post.id for p in data["items"])


@pytest.mark.asyncio
async def test_list_posts_pagination(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict):
    """Test pagination parameters work correctly."""
    # Create multiple posts
    for i in range(3):
        await client.post(
            "/api/v1/posts",
            json={
                "title": f"分页测试帖子 {i}",
                "content": "这是分页测试帖子的内容，至少十个字符",
                "category_id": test_category["id"],
            },
            headers=auth_headers,
        )

    # TEN-02: 列表查询需带 auth_headers 以解析当前学校（用户 membership）
    response = await client.get(
        "/api/v1/posts?page=1&page_size=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_get_post_detail(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test getting a specific post by ID.

    FND-03.1: test_post 默认 pending，仅作者/管理员可见，需携带 auth_headers。
    """
    response = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_post["id"]
    assert data["title"] == test_post["title"]
    assert data["content"] == test_post["content"]


@pytest.mark.asyncio
async def test_get_post_detail_increments_view(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test that viewing a post increments view_count.

    FND-03.1: test_post 默认 pending，仅作者/管理员可见，需携带 auth_headers。
    """
    response1 = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    view_count_1 = response1.json()["view_count"]

    response2 = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    view_count_2 = response2.json()["view_count"]

    assert view_count_2 == view_count_1 + 1


@pytest.mark.asyncio
async def test_get_post_not_found(client: AsyncClient):
    """Test getting a non-existent post returns 404."""
    response = await client.get("/api/v1/posts/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_post_authenticated(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict):
    """Test creating a post with authentication."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "新创建的帖子",
            "content": "这是新创建帖子的内容，至少十个字符",
            "category_id": test_category["id"],
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
async def test_create_post_without_location(
    client: AsyncClient, auth_headers: dict, test_category: dict
):
    """Task 2.1: 验证不传 location_id / location_name / lat / lng 也能成功创建 Post。

    地点应为可选字段——无地点的帖子（如纯文字吐槽）应能正常创建并审核。
    """
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "无地点帖子测试",
            "content": "这是一条没有关联地点的帖子，至少十个字符",
            "category_id": test_category["id"],
            # 不传 location_id / location_name / location_lat / location_lng
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    # location_id 应为 None（Post 模型字段允许 NULL）
    assert data["location_id"] is None
    # location 关联对象也应为 None
    assert data.get("location") is None


@pytest.mark.asyncio
async def test_create_post_unauthenticated(client: AsyncClient, test_category: dict):
    """Test creating a post without authentication returns 401."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "未认证帖子",
            "content": "这个帖子不应该被创建",
            "category_id": test_category["id"],
        },
    )
    assert response.status_code == 401


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
async def test_delete_post_owner(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict):
    """Test deleting a post as the owner."""
    # Create a post to delete
    create_response = await client.post(
        "/api/v1/posts",
        json={
            "title": "待删除的帖子",
            "content": "这个帖子将被删除，至少十个字符",
            "category_id": test_category["id"],
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
