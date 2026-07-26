"""PUB-02: 草稿—编辑—提交—审核—通知—公开 完整闭环测试

覆盖 PUB-02.1 / PUB-02.2 两个子任务的后端契约：

1. **驳回 = pending → draft**（不再是 archived 终态）：
   - 管理员单个驳回 / 批量驳回后帖子状态为 draft
   - 作者收到 audit 通知，内容包含驳回原因（"备注：xxx"）与下一步动作（"已退回草稿，可修改后重新提交"）

2. **重新提交**：
   - 驳回后作者可继续编辑（PUT 修改 draft 帖子，状态保持 draft）
   - 作者重新提交 draft → pending
   - 管理员再次审核通过 → published

3. **我的发布按状态筛选**：
   - GET /users/me/posts?status=draft/pending/published 只返回对应状态
   - 列表项携带 status 字段（前端按状态分组展示）
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post


# ============================================================
# PUB-02.1: 驳回 = pending → draft + 审核通知含原因与下一步动作
# ============================================================
@pytest.mark.asyncio
async def test_admin_reject_returns_post_to_draft_not_archived(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
):
    """PUB-02.1: 管理员驳回 pending 帖子 → 状态为 draft（可重新提交），不是 archived 终态"""
    response = await client.put(
        f"/api/v1/admin/posts/{test_post['id']}/reject",
        json={"reason": "图片模糊，请补充清晰照片"},
        headers=admin_headers,
    )
    assert response.status_code == 200

    # 作者视角查看帖子状态（作者可见自己所有状态）
    detail = await client.get(f"/api/v1/posts/{test_post['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "draft"
    assert detail.json()["status"] != "archived"


@pytest.mark.asyncio
async def test_admin_reject_creates_audit_notification_with_reason(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
):
    """PUB-02.1: 驳回后作者收到 audit 通知，含驳回原因（备注：）与下一步动作文案"""
    reason = "缺少联系方式，请补充后重新提交"
    response = await client.put(
        f"/api/v1/admin/posts/{test_post['id']}/reject",
        json={"reason": reason},
        headers=admin_headers,
    )
    assert response.status_code == 200

    notifications = await client.get("/api/v1/notifications", headers=auth_headers)
    assert notifications.status_code == 200
    items = notifications.json()["items"]
    audit = next(
        (
            n
            for n in items
            if n["type"] == "audit"
            and n["target_type"] == "post"
            and n["target_id"] == test_post["id"]
        ),
        None,
    )
    assert audit is not None, "作者应收到该帖子的审核通知"
    assert "审核未通过" in audit["title"]
    # 通知含下一步动作提示（已退回草稿，可修改后重新提交）
    assert "退回草稿" in audit["content"]
    assert "重新提交" in audit["content"]
    # 通知含驳回原因（"备注：xxx" 格式，前端从中提取原因展示）
    assert f"备注：{reason}" in audit["content"]


@pytest.mark.asyncio
async def test_batch_reject_returns_posts_to_draft(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
    db_session: AsyncSession,
):
    """PUB-02.1: 批量驳回同样走 pending → draft"""
    response = await client.post(
        "/api/v1/admin/posts/batch-reject",
        json={"post_ids": [test_post["id"]], "reason": "批量驳回测试原因"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 1
    assert data["failed"] == 0

    result = await db_session.execute(select(Post).where(Post.id == test_post["id"]))
    post = result.scalar_one()
    assert post.status == "draft"


# ============================================================
# PUB-02.1 + PUB-02.2: 驳回后编辑 → 重新提交 → 审核通过 → 公开
# ============================================================
@pytest.mark.asyncio
async def test_full_draft_edit_submit_review_publish_cycle(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
    test_school: dict,
):
    """PUB-02.2 完整闭环：提交审核 → 驳回(回草稿) → 编辑 → 重新提交 → 通过 → 公开可见"""
    post_id = test_post["id"]

    # 1. 管理员驳回（pending → draft）
    r = await client.put(
        f"/api/v1/admin/posts/{post_id}/reject",
        json={"reason": "标题不明确"},
        headers=admin_headers,
    )
    assert r.status_code == 200

    # 2. 作者在草稿状态继续编辑（PUT 修改，状态保持 draft，不回 pending）
    r = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"title": "修改后的明确标题：图书馆失物招领"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"

    # 3. 作者重新提交审核（draft → pending，作者对自己帖子的合法流转）
    r = await client.post(
        f"/api/v1/posts/{post_id}/transition",
        json={"target_status": "pending"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["previous_status"] == "draft"
    assert r.json()["current_status"] == "pending"

    # 4. 重新出现在管理员待审核队列
    pending = await client.get("/api/v1/admin/posts/pending", headers=admin_headers)
    assert pending.status_code == 200
    assert any(p["id"] == post_id for p in pending.json()["items"])

    # 5. 管理员审核通过（pending → published）
    r = await client.put(
        f"/api/v1/admin/posts/{post_id}/approve",
        json={"reason": "修改后符合要求"},
        headers=admin_headers,
    )
    assert r.status_code == 200

    # 6. 作者收到审核通过通知
    notifications = await client.get("/api/v1/notifications", headers=auth_headers)
    assert notifications.status_code == 200
    assert any(
        n["type"] == "audit"
        and n["target_id"] == post_id
        and "审核通过" in n["title"]
        for n in notifications.json()["items"]
    )

    # 7. 公开列表可见（闭环完成；公开列表需学校上下文）
    public_list = await client.get(
        "/api/v1/posts",
        headers={"X-School-Code": test_school["code"]},
    )
    assert any(p["id"] == post_id for p in public_list.json()["items"])


@pytest.mark.asyncio
async def test_rejected_draft_can_be_edited_and_resubmitted(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
):
    """PUB-02.1: 驳回后的 draft 帖子作者可正常编辑内容并重新提交"""
    post_id = test_post["id"]

    await client.put(
        f"/api/v1/admin/posts/{post_id}/reject",
        json={"reason": "内容不完整"},
        headers=admin_headers,
    )

    # 编辑草稿（修改内容）
    r = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"content": "补充完整后的内容：丢失校园卡，卡号尾号 1234，拾到请联系。"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"

    # 重新提交
    r = await client.post(
        f"/api/v1/posts/{post_id}/transition",
        json={"target_status": "pending"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["current_status"] == "pending"


# ============================================================
# PUB-02.1: 我的发布按状态筛选（GET /users/me/posts?status=）
# ============================================================
@pytest.mark.asyncio
async def test_my_posts_filter_by_status(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_post: dict,
):
    """PUB-02.1: ?status= 筛选只返回对应状态，列表项携带 status 字段"""
    post_id = test_post["id"]

    # test_post 默认 pending：status=pending 能查到，status=draft 查不到
    r = await client.get("/api/v1/users/me/posts", params={"status": "pending"}, headers=auth_headers)
    assert r.status_code == 200
    assert any(p["id"] == post_id for p in r.json()["items"])
    # 列表项携带 status 字段（前端按状态分组展示中文状态）
    item = next(p for p in r.json()["items"] if p["id"] == post_id)
    assert item["status"] == "pending"

    r = await client.get("/api/v1/users/me/posts", params={"status": "draft"}, headers=auth_headers)
    assert r.status_code == 200
    assert not any(p["id"] == post_id for p in r.json()["items"])

    # 驳回后 → status=draft 能查到，status=pending 查不到
    await client.put(
        f"/api/v1/admin/posts/{post_id}/reject",
        json={"reason": "测试驳回"},
        headers=admin_headers,
    )
    r = await client.get("/api/v1/users/me/posts", params={"status": "draft"}, headers=auth_headers)
    assert r.status_code == 200
    item = next((p for p in r.json()["items"] if p["id"] == post_id), None)
    assert item is not None
    assert item["status"] == "draft"

    # 不传 status 返回全部状态
    r = await client.get("/api/v1/users/me/posts", headers=auth_headers)
    assert r.status_code == 200
    assert any(p["id"] == post_id for p in r.json()["items"])


@pytest.mark.asyncio
async def test_my_posts_invalid_status_rejected(
    client: AsyncClient, auth_headers: dict
):
    """PUB-02.1: 非法 status 值返回 422（pattern 校验，只允许 6 态）"""
    r = await client.get(
        "/api/v1/users/me/posts",
        params={"status": "deleted"},
        headers=auth_headers,
    )
    assert r.status_code == 422
