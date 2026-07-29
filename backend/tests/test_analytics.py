"""ANA-01: 产品事件白名单 + 最小字段 + 幂等入库 + 环境标记 测试

覆盖：
- ANA-01.1 白名单拒绝非法事件 / 敏感字段
- ANA-01.1 最小字段：多余字段被剔除
- ANA-01.2 幂等入库（重复 event_id 不重复入库）
- ANA-01.2 环境标记 production/demo/test/seed
- ANA-01.3 批量上报 API（登录/游客均可）
- ANA-01.3 游客无 user_id / 普通用户 user_id 由 tenant 决定（忽略载荷伪造）
"""
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analytics import (
    EVENT_WHITELIST, SENSITIVE_FIELD_NAMES, VALID_ENVIRONMENTS,
    is_allowed_event, sanitize_fields, resolve_environment,
    track_event, track_events_batch,
)
from app.models.product_event import ProductEvent


# ============================================================
# ANA-01.1: 白名单 + 最小字段
# ============================================================
class TestWhitelist:
    """白名单事件字典与最小字段定义。"""

    def test_whitelist_contains_required_events(self):
        """spec ANA-01.1 要求的事件全部在白名单内。"""
        required = {
            "school_viewed", "search_started", "search_succeeded", "search_zero",
            "post_viewed", "share_clicked", "subscribed", "draft_saved",
            "post_submitted", "tenant_activated",
        }
        assert required.issubset(EVENT_WHITELIST.keys()), (
            f"缺失事件：{required - set(EVENT_WHITELIST.keys())}"
        )

    def test_is_allowed_event(self):
        assert is_allowed_event("post_viewed") is True
        assert is_allowed_event("school_viewed") is True
        assert is_allowed_event("non_existent_event") is False
        assert is_allowed_event("") is False

    def test_search_events_do_not_record_keyword(self):
        """spec ANA-01.2 严禁写完整搜索隐私：搜索事件白名单不含 keyword 原文字段。"""
        for ev in ("search_started", "search_succeeded", "search_zero"):
            allowed = EVENT_WHITELIST[ev]
            assert "keyword" not in allowed, f"{ev} 不应记录 keyword 原文"
            assert "query" not in allowed, f"{ev} 不应记录 query 原文"
            assert "keyword_length" in allowed, f"{ev} 应允许 keyword_length"

    def test_draft_post_events_do_not_record_content(self):
        """spec ANA-01.2 严禁写正文：草稿/帖子事件白名单不含 content/title/body。"""
        for ev in ("draft_saved", "post_submitted"):
            allowed = EVENT_WHITELIST[ev]
            for forbidden in ("content", "title", "body", "text", "description"):
                assert forbidden not in allowed, f"{ev} 不应记录 {forbidden}"


class TestSanitizeFields:
    """sanitize_fields：剔除多余字段 + 拒绝敏感字段。"""

    def test_strip_non_whitelist_fields(self):
        """非白名单字段被静默剔除。"""
        cleaned = sanitize_fields("post_viewed", {
            "post_id": 42,
            "source": "list",
            "extra_field": "should_be_removed",
            "another_extra": 123,
        })
        assert cleaned == {"post_id": 42, "source": "list"}

    def test_keep_only_keyword_length_for_search(self):
        """搜索事件只保留 keyword_length，剔除 keyword 原文。"""
        cleaned = sanitize_fields("search_started", {
            "keyword_length": 5,
            "category_code": "lost-found",
            "source": "home",
        })
        assert cleaned == {
            "keyword_length": 5, "category_code": "lost-found", "source": "home",
        }

    def test_reject_non_whitelist_event(self):
        """非白名单事件抛 ValueError。"""
        with pytest.raises(ValueError, match="非白名单事件"):
            sanitize_fields("evil_event", {"anything": 1})

    def test_reject_sensitive_fields(self):
        """敏感字段（password/token/keyword/content 等）拒绝入库。"""
        # 直接调用 sanitize_fields 时，敏感字段会抛错（即便字段名在白名单内）
        # 注意：keyword 不在 search_started 的白名单内，但因为它是敏感字段名，
        # 应当抛 ValueError 而不是静默剔除
        with pytest.raises(ValueError, match="敏感字段"):
            sanitize_fields("search_started", {"keyword": "用户的搜索词原文"})

        with pytest.raises(ValueError, match="敏感字段"):
            sanitize_fields("post_viewed", {"token": "abc"})

        with pytest.raises(ValueError, match="敏感字段"):
            sanitize_fields("draft_saved", {"content": "草稿正文"})

    def test_empty_fields_returns_empty_dict(self):
        assert sanitize_fields("post_viewed", None) == {}
        assert sanitize_fields("post_viewed", {}) == {}


# ============================================================
# ANA-01.2: 环境标记
# ============================================================
class TestEnvironment:
    """环境标记 production/demo/test/seed。"""

    def test_valid_environments(self):
        assert VALID_ENVIRONMENTS == frozenset({
            "production", "demo", "test", "seed",
        })

    def test_resolve_environment_returns_valid_value(self):
        env = resolve_environment()
        assert env in VALID_ENVIRONMENTS, f"非法 environment: {env}"

    def test_resolve_environment_test_env(self, monkeypatch):
        """TEST_DATABASE_URL 非空时返回 test。"""
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://x@localhost/y_test")
        env = resolve_environment()
        assert env == "test"

    def test_resolve_environment_explicit_config(self, monkeypatch):
        """settings.ANALYTICS_ENV 显式配置优先。"""
        from app.config import settings
        monkeypatch.setattr(settings, "ANALYTICS_ENV", "seed")
        assert resolve_environment() == "seed"

        monkeypatch.setattr(settings, "ANALYTICS_ENV", "production")
        assert resolve_environment() == "production"

    def test_resolve_environment_invalid_config_falls_back(self, monkeypatch):
        """非法 ANALYTICS_ENV 回退到 APP_ENV 推导。"""
        from app.config import settings
        monkeypatch.setattr(settings, "ANALYTICS_ENV", "invalid_value")
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        # APP_ENV=opengauss → demo
        monkeypatch.setattr(settings, "APP_ENV", "opengauss")
        assert resolve_environment() == "demo"


# ============================================================
# ANA-01.2: 幂等入库
# ============================================================
class TestTrackEventIdempotent:
    """track_event 幂等写入。"""

    async def test_insert_new_event(self, db_session: AsyncSession, test_school: dict):
        """首次入库成功。"""
        event_id = str(uuid.uuid4())
        inserted, event = await track_event(
            db_session,
            event_id=event_id,
            event_name="post_viewed",
            school_id=test_school["id"],
            fields={"post_id": 1, "source": "list"},
            environment="test",
        )
        assert inserted is True
        assert event is not None
        assert event.event_id == event_id
        assert event.event_name == "post_viewed"
        assert event.school_id == test_school["id"]
        assert event.environment == "test"
        assert event.fields_json == {"post_id": 1, "source": "list"}

    async def test_idempotent_same_event_id(self, db_session: AsyncSession, test_school: dict):
        """重复上报同 event_id 不重复入库。"""
        event_id = str(uuid.uuid4())
        # 第一次
        inserted1, _ = await track_event(
            db_session,
            event_id=event_id,
            event_name="school_viewed",
            school_id=test_school["id"],
            fields={"source": "home"},
            environment="test",
        )
        assert inserted1 is True

        # 第二次：同 event_id
        inserted2, event2 = await track_event(
            db_session,
            event_id=event_id,
            event_name="school_viewed",
            school_id=test_school["id"],
            fields={"source": "home"},
            environment="test",
        )
        assert inserted2 is False
        assert event2 is not None
        assert event2.event_id == event_id

        # 数据库只有一行
        rows = (await db_session.execute(
            select(ProductEvent).where(ProductEvent.event_id == event_id)
        )).scalars().all()
        assert len(rows) == 1

    async def test_reject_non_whitelist_event(self, db_session: AsyncSession, test_school: dict):
        """非白名单事件拒绝入库。"""
        with pytest.raises(ValueError, match="非白名单事件"):
            await track_event(
                db_session,
                event_id=str(uuid.uuid4()),
                event_name="evil_tracking",
                school_id=test_school["id"],
                environment="test",
            )
        # 数据库无该事件
        count = (await db_session.execute(
            select(ProductEvent).where(ProductEvent.event_name == "evil_tracking")
        )).scalars().all()
        assert len(count) == 0

    async def test_reject_sensitive_fields(self, db_session: AsyncSession, test_school: dict):
        """敏感字段（keyword 原文 / token / content）拒绝入库。"""
        with pytest.raises(ValueError, match="敏感字段"):
            await track_event(
                db_session,
                event_id=str(uuid.uuid4()),
                event_name="search_started",
                school_id=test_school["id"],
                fields={"keyword": "用户的搜索词", "keyword_length": 7},
                environment="test",
            )

    async def test_strip_non_whitelist_fields_on_insert(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """多余字段被剔除后再入库（不抛错）。"""
        event_id = str(uuid.uuid4())
        inserted, event = await track_event(
            db_session,
            event_id=event_id,
            event_name="post_viewed",
            school_id=test_school["id"],
            fields={
                "post_id": 99,
                "source": "search",
                "extra_unrelated_field": "should_be_stripped",
                "another_extra": 123,
            },
            environment="test",
        )
        assert inserted is True
        assert event is not None
        # fields_json 只保留白名单字段
        assert event.fields_json == {"post_id": 99, "source": "search"}
        assert "extra_unrelated_field" not in (event.fields_json or {})

    async def test_guest_event_no_user_id(self, db_session: AsyncSession, test_school: dict):
        """游客事件 user_id 为 None。"""
        event_id = str(uuid.uuid4())
        inserted, event = await track_event(
            db_session,
            event_id=event_id,
            event_name="school_viewed",
            school_id=test_school["id"],
            user_id=None,
            fields={"source": "map"},
            environment="test",
        )
        assert inserted is True
        assert event.user_id is None

    async def test_environment_recorded(self, db_session: AsyncSession, test_school: dict):
        """environment 字段正确记录。"""
        for env in ("production", "demo", "test", "seed"):
            event_id = str(uuid.uuid4())
            _, event = await track_event(
                db_session,
                event_id=event_id,
                event_name="school_viewed",
                school_id=test_school["id"],
                environment=env,
            )
            assert event.environment == env

    async def test_invalid_environment_rejected(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """非法 environment 抛 ValueError。"""
        with pytest.raises(ValueError, match="非法 environment"):
            await track_event(
                db_session,
                event_id=str(uuid.uuid4()),
                event_name="school_viewed",
                school_id=test_school["id"],
                environment="staging",
            )


# ============================================================
# ANA-01.2: 批量幂等入库
# ============================================================
class TestTrackEventsBatch:
    """track_events_batch 批量入库：单个失败不影响其他事件。"""

    async def test_batch_mixed_events(self, db_session: AsyncSession, test_school: dict):
        """混合合法 / 非白名单 / 敏感字段事件，合法事件正常入库。"""
        good_id1 = str(uuid.uuid4())
        good_id2 = str(uuid.uuid4())
        evil_id = str(uuid.uuid4())
        sensitive_id = str(uuid.uuid4())

        results = await track_events_batch(
            db_session,
            [
                {"event_id": good_id1, "event_name": "post_viewed",
                 "fields": {"post_id": 1, "source": "list"}},
                {"event_id": evil_id, "event_name": "evil_event"},
                {"event_id": sensitive_id, "event_name": "search_started",
                 "fields": {"keyword": "敏感词"}},
                {"event_id": good_id2, "event_name": "school_viewed",
                 "fields": {"source": "home"}},
            ],
            school_id=test_school["id"],
            environment="test",
        )

        assert len(results) == 4
        # good1 inserted
        assert results[0]["event_id"] == good_id1
        assert results[0]["inserted"] is True
        assert results[0]["error"] is None
        # evil rejected
        assert results[1]["event_id"] == evil_id
        assert results[1]["inserted"] is False
        assert "非白名单" in results[1]["error"]
        # sensitive rejected
        assert results[2]["event_id"] == sensitive_id
        assert results[2]["inserted"] is False
        assert "敏感字段" in results[2]["error"]
        # good2 inserted
        assert results[3]["event_id"] == good_id2
        assert results[3]["inserted"] is True

        # 数据库只有 2 条合法事件
        rows = (await db_session.execute(select(ProductEvent))).scalars().all()
        event_ids = {r.event_id for r in rows}
        assert good_id1 in event_ids
        assert good_id2 in event_ids
        assert evil_id not in event_ids
        assert sensitive_id not in event_ids

    async def test_batch_idempotent(self, db_session: AsyncSession, test_school: dict):
        """批量中重复 event_id 不重复入库。"""
        eid = str(uuid.uuid4())
        results = await track_events_batch(
            db_session,
            [
                {"event_id": eid, "event_name": "post_viewed",
                 "fields": {"post_id": 1, "source": "list"}},
                {"event_id": eid, "event_name": "post_viewed",
                 "fields": {"post_id": 1, "source": "list"}},
            ],
            school_id=test_school["id"],
            environment="test",
        )
        assert results[0]["inserted"] is True
        assert results[1]["inserted"] is False  # 幂等命中

        rows = (await db_session.execute(
            select(ProductEvent).where(ProductEvent.event_id == eid)
        )).scalars().all()
        assert len(rows) == 1


# ============================================================
# ANA-01.3: API 端点
# ============================================================
class TestAnalyticsAPI:
    """POST /api/v1/analytics/events 批量上报 API。"""

    async def test_guest_can_report_events(
        self, client: AsyncClient, test_school: dict,
    ):
        """游客（无 token）携带 X-School-Code 可上报事件。"""
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_name": "school_viewed",
                        "fields": {"source": "home"},
                    },
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_name": "post_viewed",
                        "fields": {"post_id": 1, "source": "list"},
                    },
                ]
            },
            headers={"X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 2
        assert data["inserted"] == 2
        assert data["idempotent"] == 0
        assert data["rejected"] == 0

    async def test_logged_in_user_reports_with_user_id(
        self, client: AsyncClient, test_school: dict, auth_headers: dict,
    ):
        """登录用户上报，user_id 自动从 token 解析（不依赖载荷）。"""
        event_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": event_id,
                        "event_name": "post_viewed",
                        "fields": {"post_id": 5, "source": "search"},
                        # 普通用户上报载荷里的 user_id 应被忽略
                        "user_id": 99999,
                    }
                ]
            },
            headers={**auth_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["inserted"] == 1

    async def test_non_whitelist_event_rejected_via_api(
        self, client: AsyncClient, test_school: dict,
    ):
        """非白名单事件被 Pydantic 校验拒绝（422）。"""
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_name": "evil_tracking",
                    }
                ]
            },
            headers={"X-School-Code": test_school["code"]},
        )
        assert response.status_code == 422, response.text

    async def test_idempotent_via_api(
        self, client: AsyncClient, test_school: dict,
    ):
        """API 重复上报同 event_id：第二次返回 inserted=0, idempotent=1。"""
        eid = str(uuid.uuid4())
        payload = {
            "events": [
                {
                    "event_id": eid,
                    "event_name": "post_viewed",
                    "fields": {"post_id": 1, "source": "list"},
                }
            ]
        }
        headers = {"X-School-Code": test_school["code"]}

        r1 = await client.post("/api/v1/analytics/events", json=payload, headers=headers)
        assert r1.status_code == 200
        assert r1.json()["inserted"] == 1

        r2 = await client.post("/api/v1/analytics/events", json=payload, headers=headers)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["inserted"] == 0
        assert d2["idempotent"] == 1
        assert d2["rejected"] == 0

    async def test_sensitive_field_rejected_via_api(
        self, client: AsyncClient, test_school: dict,
    ):
        """API 上报含敏感字段的事件：该事件被拒，其他事件正常入库。"""
        good_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": good_id,
                        "event_name": "school_viewed",
                        "fields": {"source": "home"},
                    },
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_name": "search_started",
                        # 注意：API schema 允许任意 dict 字段；track_event 内部拒绝
                        "fields": {"keyword": "敏感搜索词"},
                    },
                ]
            },
            headers={"X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 2
        assert data["inserted"] == 1
        assert data["rejected"] == 1

    async def test_environment_recorded_via_api(
        self, client: AsyncClient, test_school: dict, db_session: AsyncSession,
    ):
        """API 上报的事件 environment 字段正确写入。"""
        eid = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": eid,
                        "event_name": "school_viewed",
                        "fields": {"source": "map"},
                    }
                ]
            },
            headers={"X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        # 查库验证 environment
        row = (await db_session.execute(
            select(ProductEvent).where(ProductEvent.event_id == eid)
        )).scalar_one_or_none()
        assert row is not None
        # 测试环境（TEST_DATABASE_URL 已设置）→ environment 应为 test
        assert row.environment == "test"

    async def test_trace_id_from_x_request_id(
        self, client: AsyncClient, test_school: dict, db_session: AsyncSession,
    ):
        """API 上报时 X-Request-ID 头被记录到 trace_id 字段。"""
        eid = str(uuid.uuid4())
        custom_trace = "trace-ana-01-test-" + uuid.uuid4().hex
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": eid,
                        "event_name": "school_viewed",
                        "fields": {"source": "home"},
                    }
                ]
            },
            headers={
                "X-School-Code": test_school["code"],
                "X-Request-ID": custom_trace,
            },
        )
        assert response.status_code == 200
        row = (await db_session.execute(
            select(ProductEvent).where(ProductEvent.event_id == eid)
        )).scalar_one_or_none()
        assert row is not None
        assert row.trace_id == custom_trace

    async def test_guest_without_school_code_rejected(
        self, client: AsyncClient,
    ):
        """游客未携带 X-School-Code / ?school= → 404（TenantContext 约束）。"""
        response = await client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_name": "school_viewed",
                    }
                ]
            },
        )
        assert response.status_code == 404

    async def test_empty_events_list_rejected(self, client: AsyncClient, test_school: dict):
        """空事件列表被 Pydantic 拒绝（min_length=1）。"""
        response = await client.post(
            "/api/v1/analytics/events",
            json={"events": []},
            headers={"X-School-Code": test_school["code"]},
        )
        assert response.status_code == 422
