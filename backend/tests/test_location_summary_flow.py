"""AI 地点摘要主链路 + Worker 集成测试。

覆盖 8 个场景（A~H）：
  A. 直接调用 generate_location_summary：Mock AI 响应 → 生成 pending_review 版本
  B. 证据不足场景：单条帖子 → 返回 None，摘要公开接口 status=insufficient
  C. Worker 全链路：标记 dirty → run_location_summary_job（Mock AI）
     → 审核队列出现 → 管理员 approve → 地点详情显示摘要
  D. 摘要被 reject：worker 生成 → 管理员 reject → 详情仍显示 insufficient
  E. 跨校隔离：A 校地点摘要，B 校管理员队列不可见，详情 404
  F. 旧版本归档：批准新版本后，旧版本 status=archived，current_summary_id 更新
  G. 重复快照幂等：同一 snapshot 两次 generate → 只产生一条 pending_review
  H. Admin refresh 接口：标记 dirty，worker 拉取处理
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.models.location import Location
from app.models.location_summary import LocationSummaryVersion
from app.models.category import Category
from app.models.post import Post
from app.models.user import User
from app.services.location_summary import generate_location_summary
from app.jobs.location_summary_worker import run_location_summary_job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ai_response_for(post_ids: list[int], review_ids: list[int] | None = None):
    """构造一个符合 LOCATION_SUMMARY_SCHEMA 的 AI 结构化响应。

    要求 post_ids 至少 2 条（来自不同作者），否则 _normalise_output 会把
    claim 全部过滤掉，导致 summary_text 被清空、confidence=insufficient。
    """
    review_ids = review_ids or []
    refs = [{"source_type": "post", "source_id": pid} for pid in post_ids]
    refs += [{"source_type": "review", "source_id": rid} for rid in review_ids]
    return {
        "summary_text": "近期多位同学反馈该地点服务不错，排队时间短。",
        "claims": [{
            "claim_id": "c1",
            "text": "近期多位同学反馈该地点服务不错，排队时间短。",
            "source_refs": refs,
        }],
        "conflicts": [],
    }


async def _make_location(db: AsyncSession, school_id: int, name: str = "测试食堂") -> Location:
    loc = Location(
        school_id=school_id, name=name,
        description="校园餐饮地点",
        latitude=31.5, longitude=120.3,
        is_deleted=False,
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


async def _make_category(db: AsyncSession, school_id: int) -> Category:
    cat = Category(
        school_id=school_id, name="校园生活", code="campus-life",
        icon="🏫", default_validity_days=30, is_active=True,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def _make_post(
    db: AsyncSession, school_id: int, user_id: int,
    category_id: int, location_id: int, *,
    title: str, content: str,
) -> Post:
    post = Post(
        user_id=user_id, school_id=school_id,
        category_id=category_id, location_id=location_id,
        title=title, content=content,
        is_anonymous=False, status="published",
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


def _tenant(school_id: int, school_code: str) -> TenantContext:
    return TenantContext(
        school_id=school_id, school_code=school_code,
        user=None, effective_role="super_admin",
        is_guest=False, membership=None,
    )


# =======================================================================
# Scenario A: 直接调用 generate_location_summary，Mock AI 生成 pending_review
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_A_generate_makes_pending_review_version(
    db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]

    loc = await _make_location(db_session, school_a["id"])
    cat = await _make_category(db_session, school_a["id"])

    await db_session.execute(select(User).where(User.id == u1["id"]))
    second_user_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="一食堂体验", content="今天排队很快，十五分钟就打到了饭菜，味道不错",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_user_a.id, cat.id, loc.id,
        title="食堂打卡", content="排队短，出餐快，价格合适，强烈推荐",
    )

    class _FakeParsed:
        parsed = _ai_response_for([p1.id, p2.id])

    class _FakeOutcome:
        fallback = False
        fallback_reason = None
        response = _FakeParsed()
        log_id = None

    async def _fake_invoke(*args, **kwargs):
        return _FakeOutcome()

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    tenant = _tenant(school_a["id"], school_a["code"])
    result = await generate_location_summary(db_session, loc.id, tenant)

    assert result is not None, "两条独立作者帖子应生成摘要版本"
    assert result.status == "pending_review"
    assert result.version == 1
    assert result.confidence_level in {"medium", "high"}
    assert result.summary_text is not None
    assert len(result.claims_json or []) >= 1
    assert result.location_id == loc.id
    assert result.school_id == school_a["id"]


# =======================================================================
# Scenario B: 证据不足（单条帖子）→ 返回 None，公开接口 insufficient
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_B_insufficient_evidence_returns_none(
    client, db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]
    headers_a = two_school_users["headers_a"]

    loc = await _make_location(db_session, school_a["id"], "证据不足测试点")
    cat = await _make_category(db_session, school_a["id"])

    await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="单点内容", content="只有一条帖子，不够两位独立作者",
    )

    called = {"n": 0}

    async def _fake_invoke(*args, **kwargs):
        called["n"] += 1
        pytest.fail("证据不足时不应调用 invoke_ai")

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    tenant = _tenant(school_a["id"], school_a["code"])
    result = await generate_location_summary(db_session, loc.id, tenant)
    assert result is None

    summary_resp = await client.get(
        f"/api/v1/locations/{loc.id}/summary", headers=headers_a,
    )
    assert summary_resp.status_code == 200
    body = summary_resp.json()
    assert body["status"] == "insufficient"
    assert body["confidence_level"] == "insufficient"
    assert body["claims"] == []
    assert body["summary_text"] is None


# =======================================================================
# Scenario C: Worker 全链路（dirty → job → 队列 → approve → 详情展示）
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_C_worker_full_flow_approve_and_expose(
    client, db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]
    admin_a = two_school_users["admin_a"]
    admin_h_a = two_school_users["admin_headers_a"]
    headers_a = two_school_users["headers_a"]

    loc = await _make_location(db_session, school_a["id"], "全链路测试食堂")
    cat = await _make_category(db_session, school_a["id"])

    second_user_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="食堂饭香", content="窗口阿姨手不抖，菜量很大，味道好",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_user_a.id, cat.id, loc.id,
        title="好评", content="排队短，环境整洁，推荐糖醋排骨",
    )

    loc.summary_dirty_at = datetime.now()
    await db_session.commit()

    ai_out = {"ids": None}

    class _FakeParsed:
        @property
        def parsed(self):
            return _ai_response_for(ai_out["ids"] or [p1.id, p2.id])

    class _FakeOutcome:
        fallback = False
        fallback_reason = None
        response = _FakeParsed()
        log_id = None

    async def _fake_invoke(*args, **kwargs):
        return _FakeOutcome()

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    job = await run_location_summary_job(
        db_session, batch_size=10, triggered_by="test",
        triggered_user_id=admin_a["id"],
    )
    assert job.status == "success", f"worker 失败: {job.error_message}"
    assert job.processed_count >= 1

    queue = await client.get(
        "/api/v1/admin/location-summaries?status=pending_review",
        headers=admin_h_a,
    )
    assert queue.status_code == 200
    qbody = queue.json()
    assert qbody["total"] >= 1
    summary_id = None
    for it in qbody["items"]:
        if it["location_id"] == loc.id:
            summary_id = it["id"]
            break
    assert summary_id is not None, "审核队列应包含该地点的待审核摘要"

    approve_resp = await client.post(
        f"/api/v1/admin/location-summaries/{summary_id}/approve",
        json={"reason": "内容属实，批准上线"},
        headers=admin_h_a,
    )
    assert approve_resp.status_code == 200
    approve_body = approve_resp.json()
    assert approve_body["status"] == "approved"
    assert approve_body["id"] == summary_id

    await db_session.refresh(loc)
    assert loc.current_summary_id == summary_id

    detail = await client.get(
        f"/api/v1/locations/{loc.id}", headers=headers_a,
    )
    assert detail.status_code == 200
    dbody = detail.json()
    assert dbody["summary"]["status"] == "approved"
    assert dbody["summary"]["summary_text"] is not None
    assert dbody["summary"]["source_count"] >= 2
    assert len(dbody["summary"]["sources"]) >= 2


# =======================================================================
# Scenario D: 摘要被 reject → 详情仍显示 insufficient
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_D_rejected_summary_not_exposed(
    client, db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]
    admin_h_a = two_school_users["admin_headers_a"]
    headers_a = two_school_users["headers_a"]

    loc = await _make_location(db_session, school_a["id"], "驳回测试点")
    cat = await _make_category(db_session, school_a["id"])

    second_user_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="A帖", content="这是第一条测试内容，足够长",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_user_a.id, cat.id, loc.id,
        title="B帖", content="这是第二条来自另一作者的内容，足够长",
    )

    ai_calls = {"n": 0}

    class _FakeParsed:
        parsed = _ai_response_for([p1.id, p2.id])

    class _FakeOutcome:
        fallback = False
        fallback_reason = None
        response = _FakeParsed()
        log_id = None

    async def _fake_invoke(*args, **kwargs):
        ai_calls["n"] += 1
        return _FakeOutcome()

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    loc.summary_dirty_at = datetime.now()
    await db_session.commit()
    job = await run_location_summary_job(db_session, batch_size=5)
    assert job.status == "success"

    q = await client.get(
        "/api/v1/admin/location-summaries?status=pending_review",
        headers=admin_h_a,
    )
    items = [i for i in q.json()["items"] if i["location_id"] == loc.id]
    assert len(items) == 1
    summary_id = items[0]["id"]

    rej = await client.post(
        f"/api/v1/admin/location-summaries/{summary_id}/reject",
        json={"reason": "来源可信度不足，需要更直接的证据"},
        headers=admin_h_a,
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"

    summary = await db_session.get(LocationSummaryVersion, summary_id)
    assert summary is not None and summary.status == "rejected"
    assert summary.reviewer_id is not None
    assert summary.review_reason == "来源可信度不足，需要更直接的证据"

    pub = await client.get(
        f"/api/v1/locations/{loc.id}/summary", headers=headers_a,
    )
    assert pub.status_code == 200
    assert pub.json()["status"] == "insufficient"
    assert pub.json()["summary_text"] is None


# =======================================================================
# Scenario E: 跨校隔离（A 校内容，B 校看不到）
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_E_cross_tenant_isolation(
    client, db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    school_b = two_school_users["school_b"]
    u1 = two_school_users["user_a"]
    admin_h_a = two_school_users["admin_headers_a"]
    admin_h_b = two_school_users["admin_headers_b"]
    headers_b = two_school_users["headers_b"]

    loc_a = await _make_location(db_session, school_a["id"], "A 校独有地点")
    cat_a = await _make_category(db_session, school_a["id"])

    second_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat_a.id, loc_a.id,
        title="A1", content="A 校帖子 1，内容足够长",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_a.id, cat_a.id, loc_a.id,
        title="A2", content="A 校帖子 2，另一作者，足够长",
    )

    class _FakeParsed:
        parsed = _ai_response_for([p1.id, p2.id])

    class _FakeOutcome:
        fallback = False
        fallback_reason = None
        response = _FakeParsed()
        log_id = None

    async def _fake_invoke(*args, **kwargs):
        return _FakeOutcome()

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    tenant_a = _tenant(school_a["id"], school_a["code"])
    summary = await generate_location_summary(db_session, loc_a.id, tenant_a)
    assert summary is not None and summary.status == "pending_review"
    sid = summary.id

    queue_a = await client.get(
        "/api/v1/admin/location-summaries?status=pending_review",
        headers=admin_h_a,
    )
    assert queue_a.status_code == 200
    assert any(i["id"] == sid for i in queue_a.json()["items"])

    queue_b = await client.get(
        "/api/v1/admin/location-summaries?status=pending_review",
        headers=admin_h_b,
    )
    assert queue_b.status_code == 200
    assert not any(i["id"] == sid for i in queue_b.json()["items"])

    approve_from_b = await client.post(
        f"/api/v1/admin/location-summaries/{sid}/approve",
        json={}, headers=admin_h_b,
    )
    assert approve_from_b.status_code in {403, 404}, (
        "B 校管理员不应能批准 A 校摘要"
    )

    detail_from_b = await client.get(
        f"/api/v1/locations/{loc_a.id}", headers=headers_b,
    )
    assert detail_from_b.status_code == 404, "B 校用户访问 A 校地点必须 404"


# =======================================================================
# Scenario F: 批准新版本时，旧版本被归档
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_F_new_version_archives_old(
    client, db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]
    admin_h_a = two_school_users["admin_headers_a"]

    loc = await _make_location(db_session, school_a["id"], "版本归档测试点")
    cat = await _make_category(db_session, school_a["id"])

    second_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="V1帖子1", content="v1 第一帖，内容足够长足够长",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_a.id, cat.id, loc.id,
        title="V1帖子2", content="v1 第二帖，另一作者，内容足够长",
    )

    class _FP:
        def __init__(self, ids): self._ids = ids
        @property
        def parsed(self): return _ai_response_for(self._ids)

    class _FO:
        def __init__(self, ids):
            self.fallback = False
            self.fallback_reason = None
            self.response = _FP(ids)
            self.log_id = None

    ai_responses = iter([
        _FO([p1.id, p2.id]),
        _FO([p1.id, p2.id]),
    ])

    async def _fake_invoke(*args, **kwargs):
        return next(ai_responses)

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    tenant = _tenant(school_a["id"], school_a["code"])
    v1 = await generate_location_summary(db_session, loc.id, tenant)
    assert v1 is not None and v1.version == 1

    appr1 = await client.post(
        f"/api/v1/admin/location-summaries/{v1.id}/approve",
        json={}, headers=admin_h_a,
    )
    assert appr1.status_code == 200
    await db_session.refresh(loc)
    assert loc.current_summary_id == v1.id

    await db_session.refresh(v1)
    assert v1.status == "approved"

    p3 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="新帖触发V2", content="v2 新帖子，让快照发生变化",
    )
    # 修改 source_hash：手动标记 dirty + 手动调 generate（此时帖子集合变了）
    # 但 generate 会根据真实 DB 构造 snapshot，所以直接调用即可
    v2 = await generate_location_summary(db_session, loc.id, tenant)
    # 如果 snapshot_hash 相同（p3 不在 SUMMARY_POST_DAYS 外），可能返回 duplicate
    if v2 is None or v2.id == v1.id:
        # 强制创建 v2：手动调整 v1 的 source_hash，然后再 generate
        v1.source_hash = "fake_old_hash_for_v1_test_only"
        await db_session.commit()
        v2 = await generate_location_summary(db_session, loc.id, tenant)
    assert v2 is not None, f"应创建 v2，但 v2={v2}; v1_id={v1.id}"
    assert v2.version == 2
    assert v2.status == "pending_review"

    appr2 = await client.post(
        f"/api/v1/admin/location-summaries/{v2.id}/approve",
        json={"reason": "新版本信息更全"},
        headers=admin_h_a,
    )
    assert appr2.status_code == 200, f"approve v2 失败: {appr2.status_code} {appr2.text}"

    await db_session.refresh(v1)
    await db_session.refresh(v2)
    await db_session.refresh(loc)

    assert v2.status == "approved"
    assert v1.status == "archived", "旧版本批准新版本后应被归档"
    assert loc.current_summary_id == v2.id


# =======================================================================
# Scenario G: 同一 snapshot 两次 generate → 幂等，只一条 pending_review
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_G_duplicate_snapshot_is_idempotent(
    db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]

    loc = await _make_location(db_session, school_a["id"], "幂等测试点")
    cat = await _make_category(db_session, school_a["id"])

    second_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="幂等帖1", content="幂等测试第一帖内容足够长",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_a.id, cat.id, loc.id,
        title="幂等帖2", content="幂等测试第二帖另一作者足够长",
    )

    invoke_count = {"n": 0}

    class _FP:
        parsed = _ai_response_for([p1.id, p2.id])

    class _FO:
        fallback = False
        fallback_reason = None
        response = _FP()
        log_id = None

    async def _fake_invoke(*args, **kwargs):
        invoke_count["n"] += 1
        return _FO()

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    tenant = _tenant(school_a["id"], school_a["code"])
    r1 = await generate_location_summary(db_session, loc.id, tenant)
    r2 = await generate_location_summary(db_session, loc.id, tenant)

    assert r1 is not None
    assert r2 is not None
    assert r1.id == r2.id, "同 snapshot 第二次 generate 应返回同一条 pending_review"

    rows = (await db_session.execute(
        select(LocationSummaryVersion.id).where(
            LocationSummaryVersion.location_id == loc.id,
            LocationSummaryVersion.status == "pending_review",
        )
    )).all()
    assert len(rows) == 1, f"应只有 1 条 pending_review，实际 {len(rows)} 条"
    assert invoke_count["n"] == 1, f"AI 只应被调用 1 次，实际 {invoke_count['n']} 次"


# =======================================================================
# Scenario H: Admin refresh 接口标记 dirty，worker 消费
# =======================================================================

@pytest.mark.asyncio
async def test_scenario_H_admin_refresh_and_worker_pull(
    client, db_session: AsyncSession, two_school_users: dict, monkeypatch,
):
    school_a = two_school_users["school_a"]
    u1 = two_school_users["user_a"]
    admin_a = two_school_users["admin_a"]
    admin_h_a = two_school_users["admin_headers_a"]

    loc = await _make_location(db_session, school_a["id"], "Refresh 接口测试点")
    cat = await _make_category(db_session, school_a["id"])

    second_a = (await db_session.execute(
        select(User).where(User.email == "admin_a@example.com")
    )).scalar_one()

    p1 = await _make_post(
        db_session, school_a["id"], u1["id"], cat.id, loc.id,
        title="H-1", content="Refresh 前内容 1，足够长足够长",
    )
    p2 = await _make_post(
        db_session, school_a["id"], second_a.id, cat.id, loc.id,
        title="H-2", content="Refresh 前内容 2，另一作者，足够长",
    )

    class _FP:
        parsed = _ai_response_for([p1.id, p2.id])

    class _FO:
        fallback = False
        fallback_reason = None
        response = _FP()
        log_id = None

    async def _fake_invoke(*args, **kwargs):
        return _FO()

    monkeypatch.setattr("app.services.location_summary.invoke_ai", _fake_invoke)

    assert loc.summary_dirty_at is None

    refresh_resp = await client.post(
        f"/api/v1/admin/locations/{loc.id}/summary/refresh",
        headers=admin_h_a,
    )
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["location_id"] == loc.id

    await db_session.refresh(loc)
    assert loc.summary_dirty_at is not None, "refresh 接口应设置 summary_dirty_at"

    job = await run_location_summary_job(
        db_session, batch_size=5, triggered_by="admin",
        triggered_user_id=admin_a["id"],
    )
    assert job.status == "success", f"worker 失败: {job.error_message}"
    assert job.processed_count >= 1

    await db_session.refresh(loc)
    assert loc.summary_dirty_at is None, "worker 处理完后 dirty 标记应清空"

    v = await db_session.scalar(
        select(LocationSummaryVersion).where(
            LocationSummaryVersion.location_id == loc.id,
            LocationSummaryVersion.status == "pending_review",
        )
    )
    assert v is not None
    assert v.source_count >= 2
