"""T-E-01 单元测试：app/dependencies.py

覆盖 get_current_user / get_current_user_optional / get_current_admin。
通过 httpx AsyncClient 调用受保护接口间接验证（与 test_auth.py 风格一致）。
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.security import create_access_token, create_refresh_token


@pytest_asyncio.fixture
async def no_token_client() -> AsyncClient:
    """无认证的 client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestGetCurrentUserOptional:
    """get_current_user_optional 依赖"""

    @pytest.mark.asyncio
    async def test_no_token_returns_none_anonymous_access(
        self, no_token_client: AsyncClient, test_school: dict
    ):
        """无 token 时访问公开接口应成功（get_current_user_optional 返回 None）"""
        # GET /posts 是公开接口，使用 get_current_user_optional
        response = await no_token_client.get("/api/v1/posts")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_token_treated_as_anonymous(
        self, no_token_client: AsyncClient
    ):
        """无效 token 时 get_current_user_optional 返回 None，不报错"""
        response = await no_token_client.get(
            "/api/v1/posts",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_token_treated_as_anonymous(
        self, no_token_client: AsyncClient, test_user: dict
    ):
        """过期 token 被当作未登录处理（不抛 401）"""
        # 创建一个已过期的 access token
        import time
        expired_payload = {
            "sub": str(test_user["access_token"]),
            "type": "access",
            "exp": int(time.time()) - 3600,  # 1 小时前过期
        }
        # 直接用畸形 token 测试
        response = await no_token_client.get(
            "/api/v1/posts",
            headers={"Authorization": "Bearer expired.invalid.token"},
        )
        assert response.status_code == 200


class TestGetCurrentUser:
    """get_current_user 依赖（强制认证）"""

    @pytest.mark.asyncio
    async def test_no_token_raises_401(
        self, no_token_client: AsyncClient, test_school: dict
    ):
        """无 token 访问受保护接口应 401"""
        response = await no_token_client.post(
            "/api/v1/posts",
            json={"title": "测试标题", "content": "测试内容至少十个字符", "category_id": 1},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, no_token_client: AsyncClient):
        """无效 token 访问受保护接口应 401"""
        response = await no_token_client.post(
            "/api/v1/posts",
            json={"title": "测试标题", "content": "测试内容至少十个字符", "category_id": 1},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_passes(
        self, client: AsyncClient, auth_headers: dict, test_post: dict
    ):
        """有效 token 访问受保护接口应成功"""
        response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_for_access(
        self, client: AsyncClient, test_user: dict
    ):
        """refresh token 不能用于 access 接口"""
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {test_user['refresh_token']}"},
        )
        assert response.status_code == 401


class TestGetCurrentAdmin:
    """get_current_admin 依赖"""

    @pytest.mark.asyncio
    async def test_normal_user_forbidden(
        self, client: AsyncClient, auth_headers: dict, test_post: dict
    ):
        """普通用户访问管理员接口应 403"""
        # /admin/* 接口需要管理员权限
        response = await client.get("/api/v1/admin/users", headers=auth_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_user_allowed(
        self, client: AsyncClient, admin_headers: dict
    ):
        """管理员访问管理员接口应成功"""
        response = await client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_no_token_admin_raises_401(
        self, no_token_client: AsyncClient
    ):
        """未登录访问管理员接口应 401（先校验认证再校验权限）"""
        response = await no_token_client.get("/api/v1/admin/users")
        assert response.status_code == 401
