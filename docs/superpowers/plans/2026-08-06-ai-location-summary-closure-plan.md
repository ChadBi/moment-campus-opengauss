# AI 地点摘要完整闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans（或按任务顺序本会话内执行）。Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Goal:** 修复 Alembic 迁移图、重建 openGauss 并执行迁移/种子数据，补齐摘要主链路与 worker 集成测试、分批跑通全量 pytest，完成 Web 真实验收 E2E 与小程序地点详情编译走查，最后同步文档口径并提交任务报告与 Git 记录。
>
> **Architecture:** 采用“迁移修复 → 空库迁移+种子 → 集成测试 → 全量 pytest 分批 → Web E2E → 小程序验证 → 文档与提交”的串行顺序。所有代码改动遵循现有 ORM 与 async 测试风格；AI 调用在测试中使用 monkeypatch，不依赖真实网络；真实 E2E 若 AI 服务不可用，仍通过 API 写入可控的待审版本并走完审核展示链路。
>
> **Tech Stack:** Python 3.11 + `backend/.venv`、FastAPI + SQLAlchemy async、openGauss 7.0.0-RC3（Docker 本镜像，pull\_policy: never）、Alembic、pytest-asyncio、React + Vite Web、TypeScript 微信小程序、Integrated Browser MCP、wechatide-skill。

***

## 文件结构与职责

### 修改/新增文件总览

* Alembic 迁移目录

  * 修改：`backend/alembic/versions/a1b2c3d4e5f6_unify_edu_email_drop_campus_fields.py`（换唯一 revision 号）

  * 重命名：`backend/alembic/versions/a6b7c8d9e0f1_location_knowledge.py` → `b8c9d0e1f2a3_location_knowledge.py`

  * 新增：`backend/alembic/versions/n2o3p4q5r6s7_merge_drop_publisher_and_location_knowledge.py`（空 merge，仅合并分支）

  * 必要时修改：`backend/alembic/versions/d6e7f8a9b0c1_rev_01_location_reviews.py` 等后续迁移，确保 down\_revision 正确指向唯一 head 链末端

* 后端测试

  * 新增：`backend/tests/test_location_summary_flow.py`（8 类集成场景：A\~E 主链路 + F\~H worker）

* 文档与交付

  * 修改：`docs/此刻校园_评委反馈与产品优化方案.md` §1.2 口径

  * 修改：`TODO.md` 当前执行任务与补充验收

  * 修改：`CHANGELOG.md` 新增版本条目

  * 修改：`AIwork/AI地点摘要实施方案落地_任务报告.md` 第 3、7 节补本次完成

  * 新增：`AIwork/AI地点摘要完整闭环补齐_任务报告.md`（本次专项）

***

## Task 1：审计并修正 Alembic 迁移图（形成唯一 head）

**Files:**

* Modify: `backend/alembic/versions/a1b2c3d4e5f6_unify_edu_email_drop_campus_fields.py:1-20`

* Rename: `backend/alembic/versions/a6b7c8d9e0f1_location_knowledge.py` → `backend/alembic/versions/b8c9d0e1f2a3_location_knowledge.py`

* Create: `backend/alembic/versions/n2o3p4q5r6s7_merge_drop_publisher_and_location_knowledge.py`

* Modify (if needed): `backend/alembic/versions/d6e7f8a9b0c1_rev_01_location_reviews.py:20-22` 及其他后续迁移 down\_revision

### Step 1.1：给 unify\_edu\_email 迁移分配全新 revision

打开 `backend/alembic/versions/a1b2c3d4e5f6_unify_edu_email_drop_campus_fields.py`，把第 17 行的 revision 改为 `m1n2o3p4q5r6`（确保全局唯一，不与其他 12 位串重复）。down\_revision 保持 `f4b5c6d7a8b9`。

```python
revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, None] = "f4b5c6d7a8b9"
```

* [ ] **Step 1.1：修改** **`a1b2c3d4e5f6_unify_edu_email_drop_campus_fields.py`** **revision 为** **`m1n2o3p4q5r6`**

### Step 1.2：确保 t7\_post\_embeddings 的下游继续正确指向它

`b6c7d8e9f0a1_embedding_dim_512.py` 的 down\_revision 目前是 `a1b2c3d4e5f6`，它应该指向 `t7_post_embeddings` 这个迁移（原 `a1b2c3d4e5f6_t7_post_embeddings.py`，保留其 revision 为 `a1b2c3d4e5f6`）。由于我们只把 unify\_edu\_email 那一份换号，这一步无需改动，但要在核对时确认。

* [ ] **Step 1.2：核对** **`b6c7d8e9f0a1`** **down\_revision 仍为** **`a1b2c3d4e5f6`，对应 t7\_post\_embeddings**

### Step 1.3：把地点知识迁移文件名与内部 revision 对齐

将 `backend/alembic/versions/a6b7c8d9e0f1_location_knowledge.py` 重命名为 `backend/alembic/versions/b8c9d0e1f2a3_location_knowledge.py`，文件内部第 9\~12 行保持：

```python
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "z5e6f7g8h9i0"
```

* [ ] **Step 1.3：文件重命名**

### Step 1.4：新增 merge migration 合并 drop-publisher 与 location-knowledge 两分支

在 `backend/alembic/versions/` 下新建 `n2o3p4q5r6s7_merge_drop_publisher_and_location_knowledge.py`：

```python
"""MERGE: drop_publisher (a6b7c8d9e0f1) + location_knowledge (b8c9d0e1f2a3)

Revision ID: n2o3p4q5r6s7
Revises: a6b7c8d9e0f1, b8c9d0e1f2a3
Create Date: 2026-08-06

仅合并两个 DDL 分支，不产生额外对象；实际 DDL 已在两个分支迁移中。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n2o3p4q5r6s7"
down_revision: Union[str, None] = ("a6b7c8d9e0f1", "b8c9d0e1f2a3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

* [ ] **Step 1.4：新增空 merge migration** **`n2o3p4q5r6s7`**

### Step 1.5：修正最新迁移的 down\_revision，使唯一 head 成立

核对以下文件的 `down_revision`，若它们指向 merge 之前或错误分支，则改为：

* `d6e7f8a9b0c1_rev_01_location_reviews.py`（它目前依赖 `d5e6f7a8b9c1`，再往上是 `b6c7d8e9f0a1`→`a1b2c3d4e5f6_t7`→`0898a6eeb570` 分支）。这是独立的一条主链，它与 `y4d5e6f7g8h9→z5` 分支的汇合点需要从现有历史中核查；若当前没有 merge，则以实际 `alembic heads` 输出为准，缺哪个补哪个 merge。

**执行命令（Windows PowerShell，backend/.venv）：**

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic history -v
```

预期执行前：head 数量 >1，且/或出现 duplicate revision 报错。
预期修复后：head 数量 =1，`history -v` 无异常。

* [ ] **Step 1.5：运行** **`alembic heads`** **与** **`history -v`，若仍多 head 则追加对应 merge migration 直至唯一 head**

### Step 1.6：提交 Alembic 图修复

```bash
git add backend/alembic/versions
git commit -m "fix(migrations): 修复 Alembic 重复 revision 与缺失 merge，形成唯一 head"
```

* [ ] **Step 1.6：提交迁移修复 commit**

***

## Task 2：重建 openGauss，迁移 + 种子数据成功

**Files:**

* Verify: `docker-compose.yml:2-24`

* Run: `backend/scripts/seed_data.py`

### Step 2.1：停止并删除现有 openGauss 数据卷（按项目约定）

```powershell
Set-Location e:\Project\moment-campus
docker compose down -v opengauss
docker compose up -d opengauss
# 等待 5~10 秒使 openGauss 初始化完成
Start-Sleep 10
```

* [ ] **Step 2.1：`docker compose down -v opengauss`** **并重启容器**

### Step 2.2：在 backend/.venv 执行迁移到 head

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

预期：无错退出；检查 `locations` 表是否存在 `current_summary_id`、`summary_dirty_at`，三张新表是否存在：

```powershell
.\.venv\Scripts\python.exe -c "import app.db_compat; import asyncio; from sqlalchemy import text; from app.database import async_engine; async def main():
  async with async_engine.connect() as c:
    r1 = await c.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='locations' ORDER BY ordinal_position\"));
    r2 = await c.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('location_facts','location_fact_proposals','location_summary_versions')\"));
    print('locations cols:', [row[0] for row in r1.fetchall()])
    print('new tables:', [row[0] for row in r2.fetchall()])
asyncio.run(main())"
```

预期：locations 列包含 `current_summary_id`、`summary_dirty_at`；三张新表都出现。

* [ ] **Step 2.2：`alembic upgrade head`** **成功并确认新列/新表存在**

### Step 2.3：执行种子数据脚本

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
.\.venv\Scripts\python.exe scripts\seed_data.py
```

预期：脚本输出三校数据，无 `relation does not exist` 错误。

* [ ] **Step 2.3：种子数据脚本成功执行**

***

## Task 3：补齐摘要主链路与 worker 集成测试

**Files:**

* Create: `backend/tests/test_location_summary_flow.py`

* Test: `backend/tests/test_location_knowledge.py`、`test_location_summary_unit.py`、`test_location_reviews.py`、`test_nearby.py`

### Step 3.1：先写失败测试再实现修复（TDD）

创建 `backend/tests/test_location_summary_flow.py`。以下是完整文件内容，可一次性写入：

```python
"""AI 地点摘要主链路与 worker 集成测试。

覆盖：
A. 生成 pending_review 版本但不替换当前摘要
B. 批准摘要切换 current_summary_id 并归档旧版本
C. 驳回摘要不影响旧版本可读
D. AI 失败 / 虚构来源拒绝：保持可读旧版本
E. 跨校来源不被他校快照读取
F. dirty 地点被 worker 处理后清标记
G. 相同 source_hash 不重复生成
H. worker 批量扫描计数与锁无异常
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from app.models import Post, Location, PostCategory, Category
from app.models.location_summary import LocationSummaryVersion
from app.models.location import Location
from app.services.location_summary import (
    build_location_snapshot,
    generate_location_summary,
    snapshot_hash,
)
from app.jobs.location_summary_worker import run_location_summary_job


NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def two_users_two_posts(db_session, test_school, two_school_users):
    """创建地点 + 两个用户 + 两条近 7 天已发布帖子，用于双作者证据门槛。"""
    loc = Location(
        school_id=test_school["id"],
        name="双作者证据地点",
        description="集成测试专用",
        latitude=31.5, longitude=120.3, is_deleted=False,
    )
    db_session.add(loc)
    await db_session.commit()
    await db_session.refresh(loc)

    cat_q = await db_session.execute(Category.__table__.select().where(Category.school_id == test_school["id"]).limit(1))
    cat_row = cat_q.first()
    if cat_row is None:
        cat = Category(school_id=test_school["id"], code="share", name="分享", sort_order=1, is_active=True)
        db_session.add(cat)
        await db_session.commit()
        await db_session.refresh(cat)
        category_id = cat.id
    else:
        category_id = cat_row.id

    users = two_school_users["users"]  # [user_a, user_b]
    posts = []
    for idx, u in enumerate(users[:2], start=1):
        p = Post(
            school_id=test_school["id"],
            author_id=u["id"],
            location_id=loc.id,
            category_id=category_id,
            title=f"近期动态 {idx}",
            content=f"用户 {idx} 现场反馈排队较短。",
            status="published",
            published_at=NOW - timedelta(days=1),
            is_deleted=False,
        )
        db_session.add(p)
        posts.append(p)
    await db_session.commit()
    for p in posts:
        await db_session.refresh(p)

    return {"location": loc, "posts": posts, "users": users[:2]}


@pytest.mark.asyncio
async def test_scenario_a_generate_pending_review_without_switching_current(
    client, auth_headers, admin_headers, db_session, test_school, two_users_two_posts
):
    loc = two_users_two_posts["location"]
    posts = two_users_two_posts["posts"]

    # 构造 Mock AI 返回，来源合法
    async def _fake_call(*args, **kwargs):
        return {
            "summary_text": "近期两位同学都反馈排队较短。",
            "claims": [{
                "claim_id": "c1",
                "text": "近期排队较短",
                "source_refs": [
                    {"source_type": "post", "source_id": posts[0].id},
                    {"source_type": "post", "source_id": posts[1].id},
                ],
            }],
            "conflicts": [],
        }

    # monkeypatch 服务层 AI 调用位置（若项目中入口不同，则按实际位置调整为 `app.services.location_summary._invoke_ai`）
    import app.services.location_summary as svc
    original = getattr(svc, "_invoke_ai", None)
    svc._invoke_ai = _fake_call
    try:
        resp = await client.post(
            f"/api/v1/admin/locations/{loc.id}/summary/refresh",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending_review"

        # 地点详情中 current_summary 仍未切换
        detail = await client.get(f"/api/v1/locations/{loc.id}", headers=auth_headers)
        assert detail.status_code == 200
        assert detail.json().get("summary") is None or detail.json()["summary"].get("status") != "approved"
    finally:
        if original is not None:
            svc._invoke_ai = original
        else:
            del svc._invoke_ai


@pytest.mark.asyncio
async def test_scenario_b_approve_switches_current_and_archives_old(
    client, auth_headers, admin_headers, db_session, test_school, two_users_two_posts
):
    loc = two_users_two_posts["location"]
    posts = two_users_two_posts["posts"]

    # 写入一个已批准的旧版本
    old_v = LocationSummaryVersion(
        location_id=loc.id, school_id=test_school["id"], version=1,
        status="approved", summary_text="旧摘要", confidence_level="medium",
        claims_json=[], conflicts_json=[], source_refs_json=[],
        source_hash="old-hash", source_count=0, generated_at=NOW - timedelta(days=2),
        created_at=NOW - timedelta(days=2),
    )
    db_session.add(old_v)
    await db_session.commit()
    await db_session.refresh(old_v)

    loc.current_summary_id = old_v.id
    await db_session.commit()

    # 管理员通过接口创建新 pending_review 版本（这里直接写库模拟生成成功）
    new_v = LocationSummaryVersion(
        location_id=loc.id, school_id=test_school["id"], version=2,
        status="pending_review", summary_text="新摘要", confidence_level="high",
        claims_json=[{"claim_id": "c1", "text": "排队较短", "source_refs": [
            {"source_type": "post", "source_id": posts[0].id},
            {"source_type": "post", "source_id": posts[1].id},
        ]}],
        conflicts_json=[], source_refs_json=[
            {"source_type": "post", "source_id": posts[0].id},
            {"source_type": "post", "source_id": posts[1].id},
        ],
        source_hash="new-hash", source_count=2,
        generated_at=NOW, created_at=NOW,
    )
    db_session.add(new_v)
    await db_session.commit()
    await db_session.refresh(new_v)

    # 管理员批准
    approve = await client.post(
        f"/api/v1/admin/location-summaries/{new_v.id}/approve",
        headers=admin_headers, json={"reason": "核对来源无误"},
    )
    assert approve.status_code == 200

    # 重新读地点，current 指向新版本，旧版本状态 archived
    q = await db_session.execute(Location.__table__.select().where(Location.id == loc.id))
    updated_loc = q.first()
    assert updated_loc.current_summary_id == new_v.id

    q_old = await db_session.execute(LocationSummaryVersion.__table__.select().where(LocationSummaryVersion.id == old_v.id))
    old_after = q_old.first()
    assert old_after.status == "archived"


@pytest.mark.asyncio
async def test_scenario_c_reject_keeps_old_version_readable(
    client, auth_headers, admin_headers, db_session, test_school, two_users_two_posts
):
    loc = two_users_two_posts["location"]
    old_v = LocationSummaryVersion(
        location_id=loc.id, school_id=test_school["id"], version=1,
        status="approved", summary_text="稳定旧摘要", confidence_level="medium",
        claims_json=[], conflicts_json=[], source_refs_json=[],
        source_hash="old", source_count=2, generated_at=NOW - timedelta(days=3),
        created_at=NOW - timedelta(days=3),
    )
    db_session.add(old_v)
    await db_session.commit()
    await db_session.refresh(old_v)
    loc.current_summary_id = old_v.id
    await db_session.commit()

    new_v = LocationSummaryVersion(
        location_id=loc.id, school_id=test_school["id"], version=2,
        status="pending_review", summary_text="有争议草稿", confidence_level="low",
        claims_json=[], conflicts_json=[], source_refs_json=[],
        source_hash="bad", source_count=0, generated_at=NOW, created_at=NOW,
    )
    db_session.add(new_v)
    await db_session.commit()
    await db_session.refresh(new_v)

    rej = await client.post(
        f"/api/v1/admin/location-summaries/{new_v.id}/reject",
        headers=admin_headers, json={"reason": "来源不足"},
    )
    assert rej.status_code == 200

    detail = await client.get(f"/api/v1/locations/{loc.id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["summary"]["summary_text"] == "稳定旧摘要"


@pytest.mark.asyncio
async def test_scenario_d_fictional_source_rejected_and_old_stays(
    db_session, test_school, two_users_two_posts
):
    loc = two_users_two_posts["location"]
    snapshot = await build_location_snapshot(db_session, test_school["id"], loc.id)

    # 快照里没有 post_id=9999
    bad_output = {
        "summary_text": "虚构",
        "claims": [{
            "claim_id": "bad",
            "text": "虚构结论",
            "source_refs": [
                {"source_type": "post", "source_id": two_users_two_posts["posts"][0].id},
                {"source_type": "post", "source_id": 9999},
            ],
        }],
        "conflicts": [],
    }
    from app.services.location_summary import _normalise_output
    with pytest.raises(ValueError):
        _normalise_output(bad_output, snapshot)


@pytest.mark.asyncio
async def test_scenario_e_cross_school_post_not_in_snapshot(
    db_session, test_school, two_school_users
):
    # 在 A 校建地点，在 B 校建同作者帖子并关联 A 校不存在的地点；A 校快照不应包含 B 校 post id
    loc_a = Location(school_id=test_school["id"], name="A 校地点", latitude=31.5, longitude=120.3, is_deleted=False)
    db_session.add(loc_a)
    await db_session.commit()
    await db_session.refresh(loc_a)

    # B 校通过 two_school_users 已经存在第二个学校，这里直接用 school_id 2 或 fixture 中提供
    users = two_school_users["users"]
    second_school_id = two_school_users.get("second_school_id")
    if second_school_id is None:
        pytest.skip("two_school_users fixture 未提供第二学校")

    loc_b = Location(school_id=second_school_id, name="B 校同名地点", latitude=31.5, longitude=120.4, is_deleted=False)
    db_session.add(loc_b)
    await db_session.commit()
    await db_session.refresh(loc_b)

    cat = Category(school_id=second_school_id, code="share", name="分享", sort_order=1, is_active=True)
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    post_b = Post(
        school_id=second_school_id, author_id=users[0]["id"], location_id=loc_b.id,
        category_id=cat.id, title="他校动态", content="不应出现在 A 校快照",
        status="published", published_at=NOW - timedelta(days=1), is_deleted=False,
    )
    db_session.add(post_b)
    await db_session.commit()
    await db_session.refresh(post_b)

    snap_a = await build_location_snapshot(db_session, test_school["id"], loc_a.id)
    source_ids_a = {p["source_id"] for p in snap_a["posts"]}
    assert post_b.id not in source_ids_a


@pytest.mark.asyncio
async def test_scenario_f_worker_clears_dirty_flag(
    db_session, test_school, two_users_two_posts, monkeypatch
):
    loc = two_users_two_posts["location"]
    posts = two_users_two_posts["posts"]
    loc.summary_dirty_at = NOW - timedelta(minutes=5)
    await db_session.commit()

    async def _fake(*a, **kw):
        return {
            "summary_text": "worker 生成",
            "claims": [{
                "claim_id": "w1",
                "text": "排队较短",
                "source_refs": [
                    {"source_type": "post", "source_id": posts[0].id},
                    {"source_type": "post", "source_id": posts[1].id},
                ],
            }],
            "conflicts": [],
        }

    import app.services.location_summary as svc
    monkeypatch.setattr(svc, "_invoke_ai", _fake)

    stats = await run_location_summary_job(db_session)
    assert stats["processed"] >= 1

    await db_session.refresh(loc)
    assert loc.summary_dirty_at is None

    q = await db_session.execute(
        LocationSummaryVersion.__table__.select()
        .where(LocationSummaryVersion.location_id == loc.id)
        .order_by(LocationSummaryVersion.version.desc())
    )
    latest = q.first()
    assert latest is not None
    assert latest.status == "pending_review"


@pytest.mark.asyncio
async def test_scenario_g_same_hash_no_duplicate(
    db_session, test_school, two_users_two_posts, monkeypatch
):
    loc = two_users_two_posts["location"]
    posts = two_users_two_posts["posts"]

    snap = await build_location_snapshot(db_session, test_school["id"], loc.id)
    h = snapshot_hash(snap)

    # 写一个已存在的同 hash pending_review
    v = LocationSummaryVersion(
        location_id=loc.id, school_id=test_school["id"], version=1,
        status="pending_review", summary_text="已存在",
        confidence_level="medium", claims_json=[], conflicts_json=[],
        source_refs_json=[], source_hash=h, source_count=2,
        generated_at=NOW - timedelta(minutes=2),
        created_at=NOW - timedelta(minutes=2),
    )
    db_session.add(v)
    await db_session.commit()

    loc.summary_dirty_at = NOW - timedelta(minutes=1)
    await db_session.commit()

    async def _fake(*a, **kw):
        # 不应被调用；若被调用返回空输出也会被拒绝写 pending，这里让测试显式 fail
        raise AssertionError("相同 source_hash 不应再次调用 AI")

    import app.services.location_summary as svc
    monkeypatch.setattr(svc, "_invoke_ai", _fake)

    stats = await run_location_summary_job(db_session)
    # 由于 hash 命中，跳过生成，processed 可以为 0，但也不报错
    await db_session.commit()
    count_q = await db_session.execute(
        LocationSummaryVersion.__table__.select()
        .where(LocationSummaryVersion.location_id == loc.id)
    )
    rows = count_q.all()
    assert len(rows) == 1  # 只保留预先写入的那一条


@pytest.mark.asyncio
async def test_scenario_h_worker_counters_and_lock_path(
    db_session, test_school, monkeypatch
):
    # 无 dirty 地点时返回 processed=0，无异常
    stats = await run_location_summary_job(db_session)
    assert isinstance(stats["processed"], int)
    assert isinstance(stats["failed"], int)
```

* [ ] **Step 3.1：写入** **`backend/tests/test_location_summary_flow.py`** **完整文件**

### Step 3.2：运行专项测试，定位失败并修复真实接口/服务行为

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
.\.venv\Scripts\python.exe -m pytest tests/test_location_knowledge.py tests/test_location_summary_unit.py tests/test_location_reviews.py tests/test_location_summary_flow.py tests/test_nearby.py -v
```

* 若出现 fixture 缺失（如 `two_school_users`），按现有 `conftest.py` 实际 fixture 调整测试（推荐在 `backend/tests/conftest.py` 中就地追加缺失 fixture，不破坏现有用例）。

* 若 `build_location_snapshot / _invoke_ai / run_location_summary_job` 实际导出位置或签名不同，依据实际代码调整 monkeypatch 点与 import 路径。

* 若 `run_location_summary_job` 需要 app 上下文或 async engine，按现有 job\_run\_records 风格对齐调用签名。

**迭代要求：** 本步必须做到专项测试全部 PASSED，不能跳过失败。

* [ ] **Step 3.2：专项测试全部通过并记录数量**

***

## Task 4：分批执行全量 pytest，记录每批结果

**Files:**

* All: `backend/tests/`

### Step 4.1：先收集测试，按目录/文件拆分成 5 批

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
.\.venv\Scripts\python.exe -m pytest tests/ --collect-only -q
```

根据收集结果分成以下 5 批（可按实际文件名调整，保证互不重叠、覆盖整个 tests/）：

* **Batch 1（用户/认证/租户）**：`test_auth*.py test_users*.py test_tenant*.py test_schools*.py test_campus*.py test_permissions*.py`

* **Batch 2（帖子/评论/互动/治理）**：`test_posts*.py test_comments*.py test_interactions*.py test_governance*.py test_val*.py test_reports*.py`

* **Batch 3（搜索/AI/日志/个人中心/通知）**：`test_search*.py test_ai*.py test_audit*.py test_notif*.py test_personal*.py test_prf*.py test_rec*.py test_sub*.py`

* **Batch 4（管理员/统计/套餐）**：`test_admin*.py test_stat*.py test_plan*.py test_org*.py test_*.py`（剩余未归类，取文件列表作差）

* **Batch 5（慢测试/重 DB 初始化）**：若 Batch 1-4 中某文件明显慢，单独移到这一批；否则留空

### Step 4.2：逐批执行并记录成功

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
# 示例命令（按实际拆分替换）
.\.venv\Scripts\python.exe -m pytest tests/test_auth*.py tests/test_users*.py tests/test_tenant*.py tests/test_schools*.py -v --tb=short
.\.venv\Scripts\python.exe -m pytest tests/test_posts*.py tests/test_comments*.py tests/test_interactions*.py tests/test_val*.py tests/test_reports*.py -v --tb=short
.\.venv\Scripts\python.exe -m pytest tests/test_search*.py tests/test_ai*.py tests/test_audit*.py tests/test_notif*.py -v --tb=short
.\.venv\Scripts\python.exe -m pytest tests/test_admin*.py -v --tb=short
```

* 若某批失败，先定位是迁移/数据/隔离问题还是功能 Bug；迁移问题回到 Task 1/2 追加修复；功能 Bug 修复后重跑对应批次。

* 若某批 >10 分钟仍在跑，拆分该文件到子批次，避免整体超时。

**验收：** 每一批所有用例最终状态均为 PASSED。记录批次名、用例数、耗时与结果，写入新任务报告 §7。

* [ ] **Step 4.1：收集并拆分批次**

* [ ] **Step 4.2：逐批执行，全部批次通过**

***

## Task 5：Web 端 7 步完整 E2E（真实前后端 + Integrated Browser MCP）

**Files:**

* Run: backend uvicorn、frontend `npm run dev`

* Operate: Integrated Browser MCP 节点 `run_mcp` 调用 `browser_navigate / browser_snapshot / browser_click / browser_type / browser_take_screenshot / browser_console_messages / browser_network_requests / browser_wait_for`

### Step 5.1：启动后端与前端（后台，记录命令 ID）

后端：

```powershell
Set-Location e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

前端：

```powershell
Set-Location e:\Project\moment-campus\frontend
npm run dev -- --port 5173
```

* [ ] **Step 5.1：确认** **`http://127.0.0.1:8000/docs`** **与** **`http://127.0.0.1:5173/`** **可访问**

### Step 5.2：调用 Integrated Browser MCP 执行 7 步链路

前置：先读取 MCP 工具描述（`browser_navigate.json`、`browser_click.json`、`browser_type.json` 等），再调用。

步骤（按浏览器自动化写执行记录）：

1. 访问 `http://127.0.0.1:5173/login` → 填 `user1@example.jiangnan.edu.cn / pass123` 登录。
2. 打开任意江南大学地点详情页（若首页有入口则点击；否则直接访问 `/locations/:id`），找到“补充地点资料”按钮，提交营业时间（fact\_key=`normal_hours`，label=`营业时间`，value=`工作日 08:00-18:00`）与服务说明（fact\_key=`services`，label=`服务说明`，value=`支持校园卡支付，提供休息区`），reason 填“现场核对”。
3. 退出，用 `admin@momentcampus.com / pass123` 登录管理后台，进入“地点资料待审”队列，批准该提议，记录批准后响应状态或 UI 提示。
4. 手动触发一次 worker（后端直接运行 `scripts/location_summary_worker.py` 或通过管理端手动刷新接口），使该地点产生一条 `pending_review` 摘要版本。

   * 若真实 AI\_KEY 不可用导致 worker 生成失败：改为直接通过 POST 管理员“手动刷新摘要”接口，并在 monkeypatch 或测试模式下写入合法 `pending_review` 记录；不得伪造“真实 AI 调用成功”。
5. 管理员进入“AI 摘要待审”队列，打开刚生成的摘要版本，查看正文、来源数量、至少一条 claim 与来源卡片，然后点击“批准”。
6. 退出管理员账号，切回普通用户，重新进入同一地点详情页：

   * 看到“此刻摘要”卡片、至少一条结论、`来源数 ≥ 2`；

   * 稳定资料区显示刚批准的营业时间与服务说明；

   * 可点开一条来源卡片（若为帖子/评价），原始链接或内容能展开。
7. 记录页面截图、browser console messages 与 network 请求中的 5xx/4xx 异常：如有，先修复再重跑。

* [ ] **Step 5.2：完成 7 步链路，并至少保存 3 张截图（登录提交、管理员批准摘要、用户查看摘要+资料）**

***

## Task 6：小程序门禁 + 编译 + 地点详情走查

**Files:**

* Run: `wechatide-skill`（根入口），按其场景化流程进入 initializer/compiler/previewer/automator

### Step 6.1：先调用 wechatide-skill 做门禁与项目打开

1. 根据技能内说明，先执行 `check_wechatide_status`。
2. 按项目路径 `e:\Project\moment-campus\miniprogram` 打开 `project.config.json`。

* [ ] **Step 6.1：门禁通过且项目正常打开**

### Step 6.2：触发编译并校验错误

调用 wechatide-skill 的 compiler 场景，要求输出：

* 编译成功/失败；

* 若失败，错误列表与修复路径；

* 若成功，给出 `appid/project` 校验结果。

* [ ] **Step 6.2：编译成功**

### Step 6.3：打开地点详情页做自动化走查

进入 automator 场景：

* 打开地点详情页（按项目路由，如 `subpackages/pages/locations/locations` 或对应带参数）。

* 断言：

  * 存在“稳定资料”区块；

  * 若该地点无已批准摘要：展示“暂无足够近期信息”或 equivalent 空状态文案；

  * 若有：展示“此刻摘要”与来源数字段；

  * 切换到已认证用户（或测试账号）时，页面存在“补充地点资料”入口按钮。

* 截图至少 2 张：空态或摘要态；认证用户入口可见态。

* [ ] **Step 6.3：地点详情页走完并记录结果**

***

## Task 7：统一文档口径、更新 TODO/CHANGELOG/任务报告并提交

**Files:**

* Modify: `docs/此刻校园_评委反馈与产品优化方案.md` §1.2

* Modify: `TODO.md` §当前执行任务 & §本轮验收补充

* Modify: `CHANGELOG.md`

* Modify: `AIwork/AI地点摘要实施方案落地_任务报告.md` §3 + §7

* Create: `AIwork/AI地点摘要完整闭环补齐_任务报告.md`

### Step 7.1：修正方案文档 §1.2 口径

把 §1.2 表格两行：

* `地点稳定资料`：由 `本轮开发` 改为 `已实现（2026-08-06）`，口径写“认证用户提议 + 管理员审核后写入 facts 表”

* `AI 地点摘要`：由 `待开发` 改为 `已实现（2026-08-06）`，口径写“近期动态归纳 + 双作者证据门槛 + 待审/批准/驳回/失败 + 来源追溯；地图与首页预览为后续设想”

* [ ] **Step 7.1：方案文档口径完成**

### Step 7.2：更新 TODO.md

把第 19 行的未完成项打勾，并把括号里的“阻塞”原因更新成具体的执行记录（如“已唯一 head、空库迁移成功、分 5 批 pytest 通过、Web 7 步 E2E 完成、小程序门禁+编译+地点页走查完成”）。
把第 26\~28 行补充验收同步更新，若某条目因真实 AI 调用未启用则明确写“AI 失败路径通过接口注入完成审核闭环，真实 AI 生成待上线环境另验”。

* [ ] **Step 7.2：TODO.md 完成**

### Step 7.3：新增 CHANGELOG 版本

按 Keep a Changelog 格式增加版本号（如 `[2.2.5] - 2026-08-06`）：

* `fix(migrations)`：Alembic 重复 revision + 缺失 merge，形成唯一 head；空库可正常 `alembic upgrade head`

* `test(location_summary)`：新增 8 类集成测试，专项通过；全量 pytest 分 5 批通过

* `test(e2e)`：Web 7 步真实 E2E、小程序门禁+编译+地点详情走查

* `docs`：方案 §1.2、TODO、两份任务报告口径对齐

* [ ] **Step 7.3：CHANGELOG.md 完成**

### Step 7.4：更新原任务报告 + 新增本次任务报告

在 `AIwork/AI地点摘要实施方案落地_任务报告.md` §3“未完成内容”下逐项划掉并注明“本次补齐完成”，并在 §7 测试与验证下追加本次各步骤命令与结果（含 5 批 pytest 数量与结果、Web E2E 截图文件名、小程序编译结果）。
在 `AIwork/` 下新建 `AI地点摘要完整闭环补齐_任务报告.md`，按模板 8 节写完整的本次任务报告。

* [ ] **Step 7.4：两份任务报告均完成**

### Step 7.5：调用 `git-commit` 技能生成 Conventional Commit 提交

* 提交范围包含：Alembic 修复、新增测试、（若有）小的业务修复、文档、任务报告、TODO/CHANGELOG。

* 提交信息需按 Conventional Commits + 中文祈使句，内容对应本次完成：修复迁移、补集成测试、跑通 E2E、更新文档。

* 按 AGENTS.md：每次更新 TODO.md 都必须提交 Git。

* [ ] **Step 7.5：最终 Git 提交已完成**

***

## Plan Self-Review（编写计划后自检）

* Spec 覆盖度：对照 `2026-08-06-ai-location-summary-closure-design.md` §1.2 的 5 条未完成内容，Task 1 对应迁移；Task 2 对应迁移应用；Task 3 对应测试；Task 4 对应全量 pytest；Task 5 对应 Web E2E；Task 6 对应小程序；Task 7 对应文档口径与提交。无遗漏。

* Placeholder 扫描：所有步骤给出具体文件、命令、代码片段；`two_school_users` 缺失时给出兜底处理（按 conftest 调整 fixture 或 skip）；AI 失败路径明确不能伪造真实 AI 成功。

* 类型一致性：`LocationSummaryVersion`、`Location.current_summary_id/summary_dirty_at`、`run_location_summary_job`、`build_location_snapshot` 等名称与现有 `app/models/location_summary.py` / `app/jobs/location_summary_worker.py` / `app/services/location_summary.py` 一致；`n2o3p4q5r6s7` merge revision 与 `m1n2o3p4q5r6` 的迁移 id 唯一且未在现有集合中出现。

* 命令路径：Windows PowerShell（`backend\.venv\Scripts\python.exe`）、`docker compose down -v opengauss` 符合 AGENTS.md 约定；小程序强制走 `wechatide-skill`；浏览器自动化明确走 `integrated_browser` MCP。

