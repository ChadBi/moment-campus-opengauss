"""REL-02.3: 安全测试——SQL 注入 / XSS / CSRF / 限流 / 鉴权

覆盖：
1. SQL 注入：搜索关键词 / 帖子标题等输入字段使用 SQLAlchemy 参数化查询，
   注入 payload 应被当作字面字符串处理，不改变查询语义。
2. XSS：帖子标题/正文含 <script> 等 HTML 标签，应被原样存储（前端负责转义），
   不应在 API 响应中触发执行（JSON 响应天然不执行脚本）。
3. CSRF：API 使用 Bearer Token（非 Cookie），跨站请求无法复用未携带 Token 的请求；
   无 Token 访问受保护端点应返回 401。
4. 鉴权：未登录访问 admin 端点 → 401；普通用户访问 admin 端点 → 403。
5. 限流：单元测试 _match_rate_limit_rule / _get_client_ip 逻辑。
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.middleware import (
    _match_rate_limit_rule,
    _get_client_ip,
    _sanitize_path,
    SENSITIVE_PARAM_NAMES,
    _SENSITIVE_VALUE_PLACEHOLDER,
    RATE_LIMIT_RULES,
)
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.core.post_status import PostStatus


# ============================================================
# 辅助
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    s = School(name=name, code=code, is_active=True)
    db.add(s)
    await db.flush()
    return s


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is None:
        return
    now = datetime.now()
    db.add(SchoolSubscription(
        school_id=school_id, plan_id=plan.id, status="active",
        started_at=now, expires_at=None, assigned_at=now,
    ))
    await db.flush()


async def _create_user(db: AsyncSession, email: str, nickname: str, school_id: int, role: str = "user") -> User:
    u = User(
        email=email, nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id, role=role,
    )
    db.add(u)
    await db.flush()
    return u


async def _create_membership(db: AsyncSession, user_id: int, school_id: int) -> None:
    db.add(SchoolMembership(
        user_id=user_id, school_id=school_id,
        role="member", status="active", is_default=False,
    ))
    await db.flush()


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    c = Category(
        school_id=school_id, name=name, code=code, icon="🔍",
        default_validity_days=30, is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


def _school(code: str) -> dict:
    return {"X-School-Code": code}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# SQL 注入测试
# ============================================================
@pytest.mark.asyncio
class TestSQLInjection:
    """搜索关键词 / 帖子字段使用 SQLAlchemy 参数化查询，注入 payload 应被当作字面字符串。"""

    @pytest_asyncio.fixture
    async def sec_setup(self, db_session: AsyncSession) -> dict:
        """单校 + 1 用户 + 1 分类 + 1 类型 + 2 已发布帖子"""
        school = await _create_school(db_session, "安全测试大学", "sec-uni")
        await _assign_operations_subscription(db_session, school.id)
        user = await _create_user(db_session, "secuser@example.com", "安全用户", school.id)
        await _create_membership(db_session, user.id, school.id)
        cat = await _create_category(db_session, school.id, "失物招领", "lost-sec")

        now = datetime.now()
        p1 = Post(
            user_id=user.id, school_id=school.id,
            category_id=cat.id,
            title="校园卡丢失", content="在图书馆丢失校园卡",
            status=PostStatus.PUBLISHED, created_at=now,
        )
        p2 = Post(
            user_id=user.id, school_id=school.id,
            category_id=cat.id,
            title="钱包捡到", content="在食堂捡到钱包",
            status=PostStatus.PUBLISHED, created_at=now,
        )
        db_session.add_all([p1, p2])
        await db_session.commit()
        return {
            "school": {"id": school.id, "code": school.code},
            "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
            "category": cat,
            "posts": {"p1": p1, "p2": p2},
        }

    async def test_search_keyword_with_sql_injection_is_literal(
        self, client: AsyncClient, sec_setup: dict
    ):
        """搜索关键词 `' OR '1'='1` 应被当作字面字符串，不返回所有帖子"""
        # 注入 payload：试图用 OR 短路返回全部行
        payload = "' OR '1'='1"
        resp = await client.get(
            "/api/v1/search",
            params={"keyword": payload},
            headers=_school(sec_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # 应该返回 0 条（因为字面字符串不匹配任何标题/内容）
        assert data["total"] == 0
        assert len(data["items"]) == 0

    async def test_search_keyword_with_comment_payload_safe(
        self, client: AsyncClient, sec_setup: dict
    ):
        """搜索关键词 `; DROP TABLE posts; --` 不应导致表被删"""
        payload = "; DROP TABLE posts; --"
        resp = await client.get(
            "/api/v1/search",
            params={"keyword": payload},
            headers=_school(sec_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        # 表应该仍然存在（后续查询能成功）
        data = resp.json()
        assert data["total"] == 0

        # 再次搜索正常关键词，验证 posts 表未被删
        resp2 = await client.get(
            "/api/v1/search",
            params={"keyword": "校园卡"},
            headers=_school(sec_setup["school"]["code"]),
        )
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 1

    async def test_search_keyword_with_union_payload_safe(
        self, client: AsyncClient, sec_setup: dict
    ):
        """搜索关键词 `UNION SELECT password FROM users` 不应泄露密码"""
        payload = "' UNION SELECT password_hash FROM users --"
        resp = await client.get(
            "/api/v1/search",
            params={"keyword": payload},
            headers=_school(sec_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # 应返回 0 条（字面字符串不匹配）
        assert data["total"] == 0
        # 响应中不应包含 password_hash 字段
        for item in data["items"]:
            assert "password_hash" not in item
            assert "password" not in item

    async def test_post_create_with_sql_injection_in_title(
        self, client: AsyncClient, sec_setup: dict
    ):
        """帖子标题含 SQL 注入 payload 应被原样存储，不执行"""
        payload_title = "test'; DROP TABLE posts; --"
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": payload_title,
                "content": "内容至少需要十个字符",
                "category_id": sec_setup["category"].id,
                "is_anonymous": False,
            },
            headers={**_school(sec_setup["school"]["code"]), **_auth(sec_setup["user"]["token"])},
        )
        # 应该 201 创建成功（pending 状态）
        assert resp.status_code == 201
        # 验证 posts 表仍在
        resp2 = await client.get(
            "/api/v1/search",
            params={"keyword": "test"},
            headers=_school(sec_setup["school"]["code"]),
        )
        assert resp2.status_code == 200


# ============================================================
# XSS 测试
# ============================================================
@pytest.mark.asyncio
class TestXSSProtection:
    """XSS payload 在 JSON API 响应中天然不执行（前端负责渲染转义）"""

    @pytest_asyncio.fixture
    async def xss_setup(self, db_session: AsyncSession) -> dict:
        school = await _create_school(db_session, "XSS测试大学", "xss-uni")
        await _assign_operations_subscription(db_session, school.id)
        user = await _create_user(db_session, "xssuser@example.com", "XSS用户", school.id)
        await _create_membership(db_session, user.id, school.id)
        cat = await _create_category(db_session, school.id, "失物", "xss-lost")

        # 直接在 DB 中插入含 XSS payload 的帖子（绕过校验，模拟最坏情况）
        now = datetime.now()
        xss_payloads = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert(1)>',
            '"><svg/onload=alert(1)>',
            'javascript:alert(document.cookie)',
        ]
        posts = {}
        for i, payload in enumerate(xss_payloads):
            p = Post(
                user_id=user.id, school_id=school.id,
                category_id=cat.id,
                title=f"XSS测试{i}", content=payload,
                status=PostStatus.PUBLISHED, created_at=now,
            )
            db_session.add(p)
            await db_session.flush()
            posts[f"p{i}"] = p

        await db_session.commit()
        return {
            "school": {"id": school.id, "code": school.code},
            "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
            "category": cat,
            "posts": posts,
            "payloads": xss_payloads,
        }

    async def test_search_response_does_not_execute_xss(
        self, client: AsyncClient, xss_setup: dict
    ):
        """搜索结果 content 字段含 XSS payload，但 JSON 响应不执行脚本"""
        resp = await client.get(
            "/api/v1/search",
            params={"keyword": "XSS"},
            headers=_school(xss_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # 应该返回包含 XSS payload 的帖子
        assert data["total"] == len(xss_setup["payloads"])
        # content 字段应保留原始 payload（前端负责转义）
        contents = [item["content"] for item in data["items"]]
        for payload in xss_setup["payloads"]:
            assert payload in contents

    async def test_post_detail_content_preserved(
        self, client: AsyncClient, xss_setup: dict
    ):
        """帖子详情接口返回原始 content（前端渲染时转义）"""
        post = xss_setup["posts"]["p0"]
        resp = await client.get(
            f"/api/v1/posts/{post.id}",
            headers=_school(xss_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # content 字段应保留原始 payload
        assert data["content"] == xss_setup["payloads"][0]

    async def test_post_create_with_xss_in_content_stored_as_is(
        self, client: AsyncClient, xss_setup: dict
    ):
        """发布含 XSS payload 的帖子应被原样存储（pending 状态）"""
        xss_payload = '<script>alert("new xss")</script>'
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "新XSS测试",
                "content": xss_payload,
                "category_id": xss_setup["category"].id,
                "is_anonymous": False,
            },
            headers={**_school(xss_setup["school"]["code"]), **_auth(xss_setup["user"]["token"])},
        )
        assert resp.status_code == 201
        data = resp.json()
        # 创建后 status=pending（需审核才能 published）
        assert data["status"] == PostStatus.PENDING


# ============================================================
# CSRF / 鉴权测试
# ============================================================
@pytest.mark.asyncio
class TestCSRFAndAuth:
    """API 使用 Bearer Token（非 Cookie），CSRF 攻击向量不适用；
    但需验证受保护端点强制鉴权。"""

    @pytest_asyncio.fixture
    async def auth_setup(self, db_session: AsyncSession) -> dict:
        school = await _create_school(db_session, "鉴权测试大学", "auth-uni")
        await _assign_operations_subscription(db_session, school.id)
        user = await _create_user(db_session, "authuser@example.com", "鉴权用户", school.id)
        await _create_membership(db_session, user.id, school.id)
        admin = await _create_user(
            db_session, "authadmin@example.com", "鉴权管理员", school.id, role="admin"
        )
        await _create_membership(db_session, admin.id, school.id)
        await db_session.commit()
        return {
            "school": {"id": school.id, "code": school.code},
            "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
            "admin": {"id": admin.id, "token": create_access_token(data={"sub": str(admin.id)})},
        }

    async def test_no_token_create_post_returns_401(
        self, client: AsyncClient, auth_setup: dict
    ):
        """无 Token 创建帖子 → 401 Unauthorized"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "无Token帖子",
                "content": "内容至少需要十个字符",
                "category_id": 1,
                "is_anonymous": False,
            },
            headers=_school(auth_setup["school"]["code"]),
            # 不带 Authorization
        )
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(
        self, client: AsyncClient, auth_setup: dict
    ):
        """无效 Token → 401"""
        resp = await client.get(
            "/api/v1/users/me",
            headers={**_school(auth_setup["school"]["code"]), "Authorization": "Bearer invalidtoken123"},
        )
        assert resp.status_code == 401

    async def test_normal_user_cannot_access_admin_endpoints(
        self, client: AsyncClient, auth_setup: dict
    ):
        """普通用户访问 admin 端点 → 403 Forbidden"""
        # /admin/stats 是 admin 专用
        resp = await client.get(
            "/api/v1/admin/stats",
            headers={**_school(auth_setup["school"]["code"]), **_auth(auth_setup["user"]["token"])},
        )
        assert resp.status_code == 403

    async def test_admin_can_access_admin_endpoints(
        self, client: AsyncClient, auth_setup: dict
    ):
        """admin 用户访问 admin 端点 → 200"""
        resp = await client.get(
            "/api/v1/admin/stats",
            headers={**_school(auth_setup["school"]["code"]), **_auth(auth_setup["admin"]["token"])},
        )
        assert resp.status_code == 200

    async def test_admin_todos_includes_ai_monitoring_fields(
        self, client: AsyncClient, auth_setup: dict
    ):
        """REL-02.3: /admin/todos 返回 AI 监控字段（ai_calls_24h / ai_fallback_24h / ai_fallback_rate）"""
        resp = await client.get(
            "/api/v1/admin/todos",
            headers={**_school(auth_setup["school"]["code"]), **_auth(auth_setup["admin"]["token"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        # REL-02.3 新增字段必须存在
        assert "ai_calls_24h" in data
        assert "ai_fallback_24h" in data
        assert "ai_fallback_rate" in data
        # 默认无调用时降级率为 0
        assert data["ai_calls_24h"] == 0
        assert data["ai_fallback_24h"] == 0
        assert data["ai_fallback_rate"] == 0.0


# ============================================================
# 限流逻辑单元测试（中间件在测试环境禁用，但逻辑应正确）
# ============================================================
class TestRateLimitLogic:
    """限流中间件在测试环境禁用（_is_test_env 返回 True），
    但 _match_rate_limit_rule / _get_client_ip 逻辑应正确。"""

    def test_match_login_rule(self):
        """登录端点匹配 5 次/60 秒规则"""
        rule = _match_rate_limit_rule("/api/v1/auth/login", "POST")
        assert rule is not None
        assert rule == (5, 60)

    def test_match_register_rule(self):
        """注册端点匹配 5 次/60 秒规则"""
        rule = _match_rate_limit_rule("/api/v1/auth/register", "POST")
        assert rule is not None
        assert rule == (5, 60)

    def test_match_ai_search_rule(self):
        """AI 搜索端点匹配 10 次/60 秒规则"""
        rule = _match_rate_limit_rule("/api/v1/search/ai", "POST")
        assert rule is not None
        assert rule == (10, 60)

    def test_match_ai_suggest_before_posts_rule(self):
        """AI 辅助发布建议（/api/v1/posts/ai-suggest）匹配 10 次/60 秒，
        而非通用 /api/v1/posts 的 20 次/60 秒（规则顺序敏感）"""
        rule = _match_rate_limit_rule("/api/v1/posts/ai-suggest", "POST")
        assert rule is not None
        assert rule == (10, 60)  # 不是 (20, 60)

    def test_match_get_request_not_limited(self):
        """GET 请求不限流（仅限 POST 关键端点）"""
        rule = _match_rate_limit_rule("/api/v1/auth/login", "GET")
        assert rule is None

    def test_match_unlimited_path_returns_none(self):
        """非关键端点不限流"""
        rule = _match_rate_limit_rule("/api/v1/posts/123", "GET")
        assert rule is None

        rule = _match_rate_limit_rule("/api/v1/users/me", "GET")
        assert rule is None

    def test_get_client_ip_from_request(self):
        """从 Request 提取客户端 IP"""
        from fastapi import Request

        # 模拟 Request 对象
        class _MockClient:
            host = "192.168.1.100"

        class _MockHeaders:
            def __init__(self, headers: dict):
                # 存储时统一小写 key，模拟真实 Starlette Headers 的大小写不敏感行为
                self._headers = {k.lower(): v for k, v in (headers or {}).items()}

            def get(self, name: str, default: str = None):
                return self._headers.get(name.lower(), default)

        class _MockRequest:
            def __init__(self, headers: dict = None, client_host: str = "127.0.0.1"):
                self.headers = _MockHeaders(headers or {})
                self.client = _MockClient()
                self.client.host = client_host

        # 无 X-Forwarded-For：取 client.host
        req = _MockRequest(client_host="10.0.0.1")
        assert _get_client_ip(req) == "10.0.0.1"

        # 有 X-Forwarded-For：取第一个 IP
        req = _MockRequest(headers={"X-Forwarded-For": "203.0.113.1, 70.41.3.18"})
        assert _get_client_ip(req) == "203.0.113.1"

    def test_all_critical_endpoints_have_rate_limit_rules(self):
        """REL-02.3: 所有关键端点（登录/注册/发布/评论/AI 搜索）必须有限流规则"""
        required_paths = [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/posts",
            "/api/v1/comments",
            "/api/v1/search/ai",
        ]
        for path in required_paths:
            rule = _match_rate_limit_rule(path, "POST")
            assert rule is not None, f"路径 {path} 缺少限流规则"

    def test_rate_limit_multiplier_non_production(self, monkeypatch):
        """非生产环境（APP_ENV != production）限流倍率应为 4

        场景：开发 / 测试 / 演示环境运行 verify_*.py API 验证脚本时，
        登录端点 5/60s → 20/60s，避免频繁触发 429。
        """
        from app.middleware import _get_rate_limit_multiplier, _is_production_env

        # 默认 APP_ENV=opengauss → 非生产 → 倍率 4
        monkeypatch.delenv("APP_ENV", raising=False)
        assert _is_production_env() is False
        assert _get_rate_limit_multiplier() == 4

        # 显式 APP_ENV=opengauss → 非生产 → 倍率 4
        monkeypatch.setenv("APP_ENV", "opengauss")
        assert _is_production_env() is False
        assert _get_rate_limit_multiplier() == 4

    def test_rate_limit_multiplier_production(self, monkeypatch):
        """生产环境（APP_ENV=production）限流倍率应为 1

        场景：生产部署保持严格限流（登录 5/60s 防爆破）。
        """
        from app.middleware import _get_rate_limit_multiplier, _is_production_env

        monkeypatch.setenv("APP_ENV", "production")
        assert _is_production_env() is True
        assert _get_rate_limit_multiplier() == 1


# ============================================================
# 日志脱敏单元测试
# ============================================================
class TestLogSanitization:
    """REL-02.2: 日志中 password/token/secret 等敏感参数必须脱敏。"""

    def test_password_query_param_redacted(self):
        """query 参数 password=xxx 应被替换为 ***REDACTED***"""
        sanitized = _sanitize_path("/api/v1/auth/login?password=secret123")
        assert "secret123" not in sanitized
        assert _SENSITIVE_VALUE_PLACEHOLDER in sanitized

    def test_token_query_param_redacted(self):
        """query 参数 token=xxx 应被替换"""
        sanitized = _sanitize_path("/api/v1/auth/refresh?token=abc.def.ghi")
        assert "abc.def.ghi" not in sanitized
        assert _SENSITIVE_VALUE_PLACEHOLDER in sanitized

    def test_api_key_query_param_redacted(self):
        """query 参数 api_key=xxx 应被替换"""
        sanitized = _sanitize_path("/api/v1/search?api_key=sk-12345&keyword=test")
        assert "sk-12345" not in sanitized
        assert _SENSITIVE_VALUE_PLACEHOLDER in sanitized
        # 非敏感参数保留
        assert "keyword=test" in sanitized

    def test_non_sensitive_params_preserved(self):
        """非敏感参数保留原值"""
        sanitized = _sanitize_path("/api/v1/search?keyword=校园卡&page=1")
        assert "keyword=校园卡" in sanitized
        assert "page=1" in sanitized

    def test_no_query_string_unchanged(self):
        """无 query string 的 path 不变"""
        path = "/api/v1/posts/123"
        assert _sanitize_path(path) == path

    def test_sensitive_param_names_covered(self):
        """敏感字段名集合覆盖 password/token/secret/key 等"""
        required_names = {"password", "token", "secret", "api_key", "apikey"}
        assert required_names.issubset(SENSITIVE_PARAM_NAMES)
