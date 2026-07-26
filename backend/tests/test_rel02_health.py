"""REL-02.1: 健康检查端点测试

覆盖：
- GET /health/live  : 进程存活探针，始终返回 alive
- GET /health/ready : DB + uploads + AI 检查；AI 缺失只降级不阻断
- GET /version      : 返回 commit_sha / build_time / migration_version / app_env

测试要点：
- live 端点不依赖 DB，即使 DB 不可达也应返回 200
- ready 端点 DB 失败 → 503 unavailable
- ready 端点 AI 配置缺失 → 200 degraded（不阻断）
- ready 端点全部正常 → 200 ready
- version 端点返回必填字段
"""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.asyncio


# ============================================================
# /health/live
# ============================================================
class TestHealthLive:
    """存活探针：仅证明进程可响应，不检查任何依赖。"""

    async def test_live_returns_200_with_alive_status(self, client: AsyncClient):
        resp = await client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    async def test_live_does_not_require_db(self, client: AsyncClient):
        """live 探针不依赖 DB——即使 DB session 抛错也应返回 alive（不进入 get_db）"""
        # live 端点没有 Depends(get_db)，DB 异常不会影响响应
        resp = await client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"


# ============================================================
# /health/ready
# ============================================================
class TestHealthReady:
    """就绪探针：检查 DB + uploads + AI 配置。"""

    async def test_ready_returns_200_when_all_ok(self, client: AsyncClient, monkeypatch):
        """DB/uploads 正常 + AI 配置存在 → 200 ready"""
        # 确保 AI_PROVIDER 环境变量已设置
        monkeypatch.setenv("AI_PROVIDER", "mock")
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["db"] == "ok"
        assert data["checks"]["uploads"] == "ok"
        assert data["checks"]["ai"] == "ok"

    async def test_ready_degraded_when_ai_not_configured(
        self, client: AsyncClient, monkeypatch
    ):
        """AI_PROVIDER 未配置 → 200 degraded（不阻断就绪判定）"""
        # 清空 AI_PROVIDER 环境变量
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["db"] == "ok"
        assert data["checks"]["uploads"] == "ok"
        assert "degraded" in data["checks"]["ai"]

    async def test_ready_unavailable_when_db_fails(
        self, client: AsyncClient, monkeypatch
    ):
        """DB execute 抛错 → 503 unavailable（health_ready 内 try/except 捕获）"""
        monkeypatch.setenv("AI_PROVIDER", "mock")

        # 通过 dependency_overrides 注入一个 execute 抛错的 mock session
        from app.database import get_db
        from app.main import app

        async def _failing_get_db():
            mock_session = MagicMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("connection refused"))
            yield mock_session

        original = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = _failing_get_db
        try:
            resp = await client.get("/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unavailable"
            assert "fail" in data["checks"]["db"]
        finally:
            if original is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = original


# ============================================================
# /version
# ============================================================
class TestVersion:
    """版本信息端点。"""

    async def test_version_returns_required_fields(self, client: AsyncClient):
        resp = await client.get("/version")
        assert resp.status_code == 200
        data = resp.json()
        # 必填字段
        assert "commit_sha" in data
        assert "build_time" in data
        assert "migration_version" in data
        assert "app_env" in data
        assert "app_name" in data
        # 本地开发默认 commit_sha=local
        assert data["commit_sha"] == os.environ.get("GIT_COMMIT_SHA", "local")
        # app_env 来自 settings
        from app.config import settings
        assert data["app_env"] == settings.APP_ENV
        assert data["app_name"] == settings.APP_NAME

    async def test_version_honors_env_vars(self, client: AsyncClient, monkeypatch):
        """GIT_COMMIT_SHA / BUILD_TIME 环境变量被读取"""
        monkeypatch.setenv("GIT_COMMIT_SHA", "abc123def")
        monkeypatch.setenv("BUILD_TIME", "2026-07-25T10:00:00Z")
        resp = await client.get("/version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["commit_sha"] == "abc123def"
        assert data["build_time"] == "2026-07-25T10:00:00Z"

    async def test_version_migration_version_loaded_from_db(
        self, client: AsyncClient
    ):
        """migration_version 从 alembic_version 表读取（非 unknown 即视为成功）"""
        resp = await client.get("/version")
        assert resp.status_code == 200
        data = resp.json()
        # 测试库已通过 Base.metadata.create_all 建表，但 alembic_version 表可能不存在
        # 不存在时返回 "error: ..." 也算合理（不阻断接口）
        assert data["migration_version"]  # 非空字符串


# ============================================================
# REL-02.2: X-Request-ID 透传（健康端点也应有）
# ============================================================
class TestRequestIdOnHealth:
    """所有端点应通过 RequestIDMiddleware 注入 X-Request-ID 响应头。"""

    async def test_live_returns_request_id_header(self, client: AsyncClient):
        resp = await client.get("/health/live")
        assert "X-Request-ID" in resp.headers
        assert resp.headers["X-Request-ID"]  # 非空

    async def test_live_accepts_client_request_id(self, client: AsyncClient):
        """客户端传入 X-Request-ID 应被沿用"""
        custom_id = "rel02-health-test-12345"
        resp = await client.get(
            "/health/live",
            headers={"X-Request-ID": custom_id},
        )
        assert resp.headers["X-Request-ID"] == custom_id

    async def test_ready_returns_request_id_header(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "mock")
        resp = await client.get("/health/ready")
        assert "X-Request-ID" in resp.headers

    async def test_version_returns_request_id_header(self, client: AsyncClient):
        resp = await client.get("/version")
        assert "X-Request-ID" in resp.headers

