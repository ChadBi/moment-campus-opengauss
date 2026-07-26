"""FND-03.1: 帖子详情可见性策略测试

覆盖 can_view_post 辅助函数与 GET /api/v1/posts/{id} 接口的可见性策略：
- 公开访问（游客/非作者）：仅 published / expired 可见
- 作者：可见自己所有状态
- 管理员：可见所有状态（TODO TEN-02 完善本校校验）
- 草稿/待审/归档/冲突帖子对无权限用户返回 404（不泄露存在性）
"""
import pytest
from httpx import AsyncClient
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.posts import can_view_post
from app.core.post_status import PostStatus
from app.models.post import Post


# ============================================================
# can_view_post 单元测试（不依赖数据库）
# ============================================================
def _make_post(status: str, user_id: int = 1, school_id: int = 1, is_deleted: bool = False) -> Post:
    """构造内存中的 Post 对象（不写库）

    使用 SimpleNamespace 避免 SQLAlchemy Mapped 描述符需要 _sa_instance_state 的问题。
    can_view_post 只读取 is_deleted / status / user_id 字段，SimpleNamespace 完全兼容。
    """
    return SimpleNamespace(
        id=100, user_id=user_id, school_id=school_id,
        status=status, is_deleted=is_deleted,
    )


def _make_user(user_id: int, role: str = "user", school_id: int = 1) -> SimpleNamespace:
    """构造内存中的 User 对象

    使用 SimpleNamespace 避免 SQLAlchemy Mapped 描述符问题。
    is_admin() 只读取 role 字段，can_view_post 只读取 id 字段，SimpleNamespace 完全兼容。
    """
    return SimpleNamespace(id=user_id, role=role, school_id=school_id)


class TestCanViewPostUnit:
    """can_view_post 单元测试"""

    def test_anonymous_can_view_published(self):
        """游客可见 published"""
        assert can_view_post(_make_post(PostStatus.PUBLISHED), None) is True

    def test_anonymous_can_view_expired(self):
        """游客可见 expired（默认允许展示过期帖子）"""
        assert can_view_post(_make_post(PostStatus.EXPIRED), None) is True

    def test_anonymous_cannot_view_draft(self):
        """游客不可见 draft"""
        assert can_view_post(_make_post(PostStatus.DRAFT), None) is False

    def test_anonymous_cannot_view_pending(self):
        """游客不可见 pending"""
        assert can_view_post(_make_post(PostStatus.PENDING), None) is False

    def test_anonymous_cannot_view_archived(self):
        """游客不可见 archived"""
        assert can_view_post(_make_post(PostStatus.ARCHIVED), None) is False

    def test_anonymous_cannot_view_conflict(self):
        """游客不可见 conflict"""
        assert can_view_post(_make_post(PostStatus.CONFLICT), None) is False

    def test_anonymous_cannot_view_deleted(self):
        """任何人都不可见已软删除的帖子"""
        assert can_view_post(
            _make_post(PostStatus.PUBLISHED, is_deleted=True), None
        ) is False

    def test_author_can_view_own_all_statuses(self):
        """作者可见自己所有状态"""
        author = _make_user(user_id=1, role="user")
        for status in PostStatus.ALL:
            assert can_view_post(_make_post(status, user_id=1), author) is True

    def test_other_user_cannot_view_draft(self):
        """非作者普通用户不可见他人 draft"""
        other = _make_user(user_id=999, role="user")
        assert can_view_post(_make_post(PostStatus.DRAFT, user_id=1), other) is False

    def test_other_user_can_view_published(self):
        """非作者普通用户可见 published"""
        other = _make_user(user_id=999, role="user")
        assert can_view_post(_make_post(PostStatus.PUBLISHED, user_id=1), other) is True

    def test_admin_can_view_all_statuses(self):
        """管理员可见所有状态（含 draft/pending/archived/conflict）"""
        admin = _make_user(user_id=999, role="admin", school_id=1)
        for status in PostStatus.ALL:
            assert can_view_post(_make_post(status, user_id=1, school_id=1), admin) is True

    def test_super_admin_can_view_all_statuses(self):
        """超级管理员可见所有状态"""
        sa = _make_user(user_id=999, role="super_admin", school_id=1)
        for status in PostStatus.ALL:
            assert can_view_post(_make_post(status, user_id=1, school_id=1), sa) is True

    def test_none_post_returns_false(self):
        """post=None 返回 False"""
        assert can_view_post(None, None) is False


# ============================================================
# GET /api/v1/posts/{id} 可见性端到端测试
# ============================================================
async def _create_post_with_status(
    db_session: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    post_type_id: int,
    status: str,
) -> Post:
    """直接在 DB 创建指定状态的帖子"""
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        post_type_id=post_type_id,
        title=f"测试帖子-{status}",
        content=f"这是 {status} 状态的测试帖子内容，至少十个字符",
        status=status,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


@pytest.mark.asyncio
async def test_get_published_post_anonymous(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 游客可见 published 帖子"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.PUBLISHED,
    )

    # TEN-02.1：游客必须显式提供 X-School-Code 头解析学校上下文
    response = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200
    assert response.json()["id"] == post.id


@pytest.mark.asyncio
async def test_get_expired_post_anonymous(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 游客可见 expired 帖子（允许展示过期内容）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.EXPIRED,
    )

    # TEN-02.1：游客必须显式提供 X-School-Code 头解析学校上下文
    response = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"X-School-Code": test_school["code"]},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_draft_post_anonymous_404(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 游客访问 draft 帖子返回 404（不泄露存在性）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.DRAFT,
    )

    response = await client.get(f"/api/v1/posts/{post.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_pending_post_anonymous_404(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 游客访问 pending 帖子返回 404"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.PENDING,
    )

    response = await client.get(f"/api/v1/posts/{post.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_archived_post_anonymous_404(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 游客访问 archived 帖子返回 404"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.ARCHIVED,
    )

    response = await client.get(f"/api/v1/posts/{post.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_conflict_post_anonymous_404(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 游客访问 conflict 帖子返回 404"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.CONFLICT,
    )

    response = await client.get(f"/api/v1/posts/{post.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_author_can_view_own_pending(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """FND-03.1: 作者可见自己 pending 帖子（test_post fixture 默认 pending）"""
    response = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == test_post["id"]


@pytest.mark.asyncio
async def test_other_user_cannot_view_pending(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """FND-03.1: 非作者普通用户访问他人 pending 帖子返回 404"""
    response = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=second_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_view_other_user_pending(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """FND-03.1: 管理员可见他人 pending 帖子"""
    response = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == test_post["id"]


@pytest.mark.asyncio
async def test_view_count_not_incremented_on_404(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict, test_post_type: dict,
):
    """FND-03.1: 不可见时浏览次数不应增加"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_post_with_status(
        db_session, user_id, test_school["id"],
        test_category["id"], test_post_type["id"], PostStatus.PENDING,
    )
    original_view_count = post.view_count

    # 游客访问 pending → 404
    response = await client.get(f"/api/v1/posts/{post.id}")
    assert response.status_code == 404

    # 重新查询 view_count 应保持不变
    await db_session.refresh(post, attribute_names=["view_count"])
    assert post.view_count == original_view_count


@pytest.mark.asyncio
async def test_unified_error_response_with_request_id(
    client: AsyncClient
):
    """FND-03.5: 404 响应应包含 request_id 字段，且响应头有 X-Request-ID"""
    response = await client.get("/api/v1/posts/99999")
    assert response.status_code == 404
    data = response.json()
    # 统一异常响应结构 {detail, request_id}
    assert "detail" in data
    assert "request_id" in data
    # 响应头包含 X-Request-ID
    assert "X-Request-ID".lower() in {k.lower() for k in response.headers.keys()}


@pytest.mark.asyncio
async def test_request_id_passthrough(
    client: AsyncClient
):
    """FND-03.5: 客户端传入的 X-Request-ID 应原样返回"""
    custom_id = "test-request-id-12345"
    response = await client.get(
        "/api/v1/posts/99999",
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 404
    assert response.headers.get("X-Request-ID") == custom_id
    assert response.json()["request_id"] == custom_id
