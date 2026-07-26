"""GOV-01: 五类协同治理完整语义与聚合详情测试

5 类协同验证 = 2 类互斥投票(validation_records: confirmation/refutation)
            + 3 类问题报告(post_change_reports: update/expiration_report/conflict_report)

覆盖 GOV-01.1 ~ GOV-01.4：
- GOV-01.1: post_change_reports 表（3 类报告）；validation_records 保留 2 类投票
- GOV-01.2: 禁止作者给自己投票；作者可响应报告（resolved）；管理员可处理全部状态；
            详情显示验证数量/时间/说明/处理状态
- GOV-01.3: 重复举报限制（同用户同类型未结案时拒绝）
- GOV-01.4: 五类 E2E 通过；管理员处理后状态/前端一致
"""
import pytest
from httpx import AsyncClient


# ============================================================
# GOV-01.1 + GOV-01.2: 2 类互斥投票（POST /posts/{id}/validations）
# ============================================================

@pytest.mark.asyncio
async def test_create_confirmation_vote(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 第二用户对帖子投 confirmation（证实）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation", "comment": "信息属实"},
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["validation_type"] == "confirmation"
    assert data["comment"] == "信息属实"
    assert data["user"]["nickname"] == "第二用户"


@pytest.mark.asyncio
async def test_create_refutation_vote(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 第二用户对帖子投 refutation（证伪）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "refutation", "comment": "信息有误"},
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["validation_type"] == "refutation"
    assert data["comment"] == "信息有误"


@pytest.mark.asyncio
async def test_author_cannot_vote_own_post(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """GOV-01.2: 禁止作者给自己的帖子投票（403）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert response.status_code == 403
    assert "不能为自己的帖子投票" in response.json()["detail"]


@pytest.mark.asyncio
async def test_vote_legacy_alias_normalized(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 旧别名 valid→confirmation / invalid→refutation 归一化"""
    # valid → confirmation
    resp1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "valid"},
        headers=second_auth_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["validation_type"] == "confirmation"

    # invalid → refutation（替换）
    resp2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "invalid"},
        headers=second_auth_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["validation_type"] == "refutation"


@pytest.mark.asyncio
async def test_vote_replaces_existing(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 每用户每帖一条，第二次提交替换原记录（不新增）"""
    # 先投 confirmation
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation", "comment": "第一次"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 200
    first_id = r1.json()["id"]

    # 切换到 refutation（替换）
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "refutation", "comment": "第二次"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == first_id  # 同一条记录，id 不变
    assert data["validation_type"] == "refutation"
    assert data["comment"] == "第二次"


@pytest.mark.asyncio
async def test_get_validation_aggregation(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2 + GOV-01.4: 聚合投票统计 GET /posts/{id}/validations"""
    # 先投 confirmation
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )

    response = await client.get(
        f"/api/v1/posts/{test_post['id']}/validations",
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["confirmation_count"] >= 1
    assert data["refutation_count"] >= 0
    assert data["total_count"] >= 1
    assert data["validity_status"] in ("valid", "invalid", "uncertain")
    assert data["user_validation_type"] == "confirmation"
    assert len(data["recent_records"]) >= 1


@pytest.mark.asyncio
async def test_vote_unauthenticated(client: AsyncClient, test_post: dict):
    """GOV-01.2: 未登录用户投票返回 401"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vote_nonexistent_post(client: AsyncClient, second_auth_headers: dict):
    """GOV-01.2: 不存在的帖子投票返回 404"""
    response = await client.post(
        "/api/v1/posts/99999/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    assert response.status_code == 404


# ============================================================
# GOV-01.1 + GOV-01.2: 3 类问题报告（POST /posts/{id}/change-reports）
# ============================================================

@pytest.mark.asyncio
async def test_create_update_report(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.1: 提交 update（更新建议）报告"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={
            "report_type": "update",
            "description": "建议补充活动地点详情",
            "evidence_url": "https://example.com/evidence",
        },
        headers=second_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["report_type"] == "update"
    assert data["description"] == "建议补充活动地点详情"
    assert data["evidence_url"] == "https://example.com/evidence"
    assert data["status"] == "open"
    assert data["handler_id"] is None
    assert data["reporter"]["nickname"] == "第二用户"


@pytest.mark.asyncio
async def test_create_expiration_report(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.1: 提交 expiration_report（过期报告）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={
            "report_type": "expiration_report",
            "description": "活动已结束，信息过期",
        },
        headers=second_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["report_type"] == "expiration_report"
    assert data["status"] == "open"


@pytest.mark.asyncio
async def test_create_conflict_report(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.1: 提交 conflict_report（冲突报告）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={
            "report_type": "conflict_report",
            "description": "与其他帖子信息冲突",
        },
        headers=second_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["report_type"] == "conflict_report"
    assert data["status"] == "open"


@pytest.mark.asyncio
async def test_duplicate_report_rejected(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.3: 同一用户对同一帖子同一类型，存在未结案报告时拒绝（400）"""
    # 第一次提交 update 报告
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "第一次报告"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 201

    # 第二次提交同类型 update 报告（仍 open）→ 拒绝
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "第二次报告"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 400
    assert "已提交过" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_report_different_type_allowed(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.3: 同一用户可对不同类型的报告分别提交（不视为重复）"""
    # update 报告
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "更新建议"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 201

    # expiration_report 报告（不同类型，允许）
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "expiration_report", "description": "已过期"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 201

    # conflict_report 报告（不同类型，允许）
    r3 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "conflict_report", "description": "有冲突"},
        headers=second_auth_headers,
    )
    assert r3.status_code == 201


@pytest.mark.asyncio
async def test_list_change_reports(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 获取问题报告列表"""
    # 提交 3 类报告
    for rtype, desc in [
        ("update", "更新建议"),
        ("expiration_report", "过期报告"),
        ("conflict_report", "冲突报告"),
    ]:
        await client.post(
            f"/api/v1/posts/{test_post['id']}/change-reports",
            json={"report_type": rtype, "description": desc},
            headers=second_auth_headers,
        )

    response = await client.get(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["total"] >= 3
    assert data["open_count"] >= 3
    assert len(data["items"]) >= 3
    # 验证报告类型都在
    report_types = {item["report_type"] for item in data["items"]}
    assert {"update", "expiration_report", "conflict_report"}.issubset(report_types)


@pytest.mark.asyncio
async def test_list_change_reports_status_filter(
    client: AsyncClient, admin_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 按状态筛选问题报告列表"""
    # 提交报告
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "待处理"},
        headers=second_auth_headers,
    )
    report_id = r.json()["id"]

    # 管理员解决该报告
    await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "resolved", "reason": "已更新"},
        headers=admin_headers,
    )

    # 查询 open 状态的报告（不含已解决的）
    resp_open = await client.get(
        f"/api/v1/posts/{test_post['id']}/change-reports?status_filter=open",
        headers=admin_headers,
    )
    assert resp_open.status_code == 200
    open_data = resp_open.json()
    for item in open_data["items"]:
        assert item["status"] == "open"

    # 查询 resolved 状态的报告
    resp_resolved = await client.get(
        f"/api/v1/posts/{test_post['id']}/change-reports?status_filter=resolved",
        headers=admin_headers,
    )
    assert resp_resolved.status_code == 200
    resolved_data = resp_resolved.json()
    assert any(item["status"] == "resolved" for item in resolved_data["items"])


@pytest.mark.asyncio
async def test_create_report_unauthenticated(client: AsyncClient, test_post: dict):
    """GOV-01.2: 未登录用户提交报告返回 401"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "test"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_report_nonexistent_post(
    client: AsyncClient, second_auth_headers: dict
):
    """GOV-01.2: 不存在的帖子提交报告返回 404"""
    response = await client.post(
        "/api/v1/posts/99999/change-reports",
        json={"report_type": "update", "description": "test"},
        headers=second_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_report_invalid_type(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.1: 无效的报告类型返回 422"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "invalid_type", "description": "test"},
        headers=second_auth_headers,
    )
    assert response.status_code == 422


# ============================================================
# GOV-01.2 + GOV-01.4: 报告处理（PUT /governance/reports/{id}）
# ============================================================

@pytest.mark.asyncio
async def test_admin_resolve_report(
    client: AsyncClient, admin_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 管理员解决报告（resolved）"""
    # 第二用户提交报告
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "需要更新"},
        headers=second_auth_headers,
    )
    assert r.status_code == 201
    report_id = r.json()["id"]

    # 管理员解决
    resp = await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "resolved", "reason": "已更新信息"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["handler_id"] is not None
    assert data["handler_note"] == "已更新信息"
    assert data["handled_at"] is not None


@pytest.mark.asyncio
async def test_admin_dismiss_report(
    client: AsyncClient, admin_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 管理员驳回报告（dismissed）"""
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "conflict_report", "description": "冲突"},
        headers=second_auth_headers,
    )
    report_id = r.json()["id"]

    resp = await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "dismissed", "reason": "无实际冲突"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"
    assert resp.json()["handled_at"] is not None


@pytest.mark.asyncio
async def test_admin_in_review_report(
    client: AsyncClient, admin_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 管理员受理报告（in_review）"""
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "expiration_report", "description": "已过期"},
        headers=second_auth_headers,
    )
    report_id = r.json()["id"]

    resp = await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "in_review", "reason": "核查中"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"
    # in_review 不属于结案状态，handled_at 应为 None
    assert resp.json()["handled_at"] is None


@pytest.mark.asyncio
async def test_author_resolve_report(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 作者可响应报告（标记 resolved）"""
    # 第二用户提交报告
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "建议更新"},
        headers=second_auth_headers,
    )
    report_id = r.json()["id"]

    # 作者标记已处理（resolved）
    resp = await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "resolved", "reason": "作者标记已处理"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["handler_id"] is not None


@pytest.mark.asyncio
async def test_author_cannot_dismiss_report(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 作者不能驳回报告（仅管理员可 dismissed），返回 403"""
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "建议更新"},
        headers=second_auth_headers,
    )
    report_id = r.json()["id"]

    resp = await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "dismissed", "reason": "试图驳回"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_author_non_admin_cannot_handle(
    client: AsyncClient, second_auth_headers: dict, test_post: dict, test_school: dict
):
    """GOV-01.2: 非作者非管理员不能处理报告（403）"""
    # second_user 提交报告
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "建议"},
        headers=second_auth_headers,
    )
    report_id = r.json()["id"]

    # 注册第三个用户（非作者非管理员）
    third = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "thirduser@example.com",
            "nickname": "第三用户",
            "password": "thirdpassword789",
            "school_id": test_school["id"],
        },
    )
    assert third.status_code == 200
    third_token = third.json()["access_token"]
    third_headers = {"Authorization": f"Bearer {third_token}"}

    resp = await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "resolved", "reason": "试图处理"},
        headers=third_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_handle_nonexistent_report(
    client: AsyncClient, admin_headers: dict
):
    """GOV-01.2: 处理不存在的报告返回 404"""
    resp = await client.put(
        "/api/v1/governance/reports/99999",
        json={"status": "resolved", "reason": "test"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolved_report_allows_resubmit(
    client: AsyncClient, admin_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.3: 报告被 resolved 后，同用户可再次提交同类型报告（不视为重复）"""
    # 第一次提交
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "第一次"},
        headers=second_auth_headers,
    )
    report_id = r1.json()["id"]

    # 管理员解决
    await client.put(
        f"/api/v1/governance/reports/{report_id}",
        json={"status": "resolved", "reason": "已处理"},
        headers=admin_headers,
    )

    # 再次提交同类型（已 resolved，不视为重复）
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "第二次"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 201


# ============================================================
# GOV-01.4: 详情聚合（GET /posts/{id} 返回 governance 字段）
# ============================================================

@pytest.mark.asyncio
async def test_post_detail_includes_governance_summary(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 帖子详情返回 governance 聚合（验证数量/报告数/最近报告）"""
    # 第二用户投票
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    # 第二用户提交报告
    await client.post(
        f"/api/v1/posts/{test_post['id']}/change-reports",
        json={"report_type": "update", "description": "建议更新"},
        headers=second_auth_headers,
    )

    # 获取详情
    resp = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "governance" in data
    gov = data["governance"]
    assert gov is not None
    assert gov["confirmation_count"] >= 1
    assert gov["refutation_count"] >= 0
    assert gov["total_validation_count"] >= 1
    assert gov["validity_status"] in ("valid", "invalid", "uncertain")
    assert gov["change_reports_total"] >= 1
    assert gov["change_reports_open"] >= 1
    assert len(gov["recent_change_reports"]) >= 1
    # 验证最近报告字段
    recent = gov["recent_change_reports"][0]
    assert recent["report_type"] == "update"
    assert recent["status"] == "open"
    assert recent["reporter"]["nickname"] == "第二用户"


@pytest.mark.asyncio
async def test_post_detail_governance_empty_when_no_activity(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """GOV-01.4: 无投票无报告时 governance 聚合返回零值"""
    resp = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    assert gov["confirmation_count"] == 0
    assert gov["refutation_count"] == 0
    assert gov["total_validation_count"] == 0
    assert gov["change_reports_total"] == 0
    assert gov["change_reports_open"] == 0
    assert len(gov["recent_change_reports"]) == 0


# ============================================================
# GOV-01.4: 五类 E2E 完整链路（2 投票 + 3 报告 一次性验证）
# ============================================================

@pytest.mark.asyncio
async def test_five_types_full_e2e(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict,
    admin_headers: dict, test_post: dict
):
    """GOV-01.4: 五类协同验证完整 E2E

    2 类投票：confirmation + refutation（由 second_user 替换切换）
    3 类报告：update + expiration_report + conflict_report（均由 second_user 提交）
    管理员处理：受理 → 解决
    作者响应：标记 resolved
    详情聚合：验证数量/报告数/最近报告均正确
    """
    post_id = test_post["id"]

    # === 2 类投票 ===
    # 1) confirmation
    r1 = await client.post(
        f"/api/v1/posts/{post_id}/validations",
        json={"validation_type": "confirmation", "comment": "证实"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["validation_type"] == "confirmation"

    # 2) refutation（替换 confirmation）
    r2 = await client.post(
        f"/api/v1/posts/{post_id}/validations",
        json={"validation_type": "refutation", "comment": "证伪"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["validation_type"] == "refutation"

    # === 3 类报告 ===
    # 3) update
    r3 = await client.post(
        f"/api/v1/posts/{post_id}/change-reports",
        json={"report_type": "update", "description": "更新建议"},
        headers=second_auth_headers,
    )
    assert r3.status_code == 201
    update_report_id = r3.json()["id"]

    # 4) expiration_report
    r4 = await client.post(
        f"/api/v1/posts/{post_id}/change-reports",
        json={"report_type": "expiration_report", "description": "已过期"},
        headers=second_auth_headers,
    )
    assert r4.status_code == 201
    expiration_report_id = r4.json()["id"]

    # 5) conflict_report
    r5 = await client.post(
        f"/api/v1/posts/{post_id}/change-reports",
        json={"report_type": "conflict_report", "description": "有冲突"},
        headers=second_auth_headers,
    )
    assert r5.status_code == 201
    conflict_report_id = r5.json()["id"]

    # === 管理员处理 ===
    # 受理 update 报告
    r_admin1 = await client.put(
        f"/api/v1/governance/reports/{update_report_id}",
        json={"status": "in_review", "reason": "受理中"},
        headers=admin_headers,
    )
    assert r_admin1.status_code == 200
    assert r_admin1.json()["status"] == "in_review"

    # 解决 update 报告
    r_admin2 = await client.put(
        f"/api/v1/governance/reports/{update_report_id}",
        json={"status": "resolved", "reason": "已更新"},
        headers=admin_headers,
    )
    assert r_admin2.status_code == 200
    assert r_admin2.json()["status"] == "resolved"

    # === 作者响应 ===
    # 作者标记 conflict_report 为 resolved
    r_author = await client.put(
        f"/api/v1/governance/reports/{conflict_report_id}",
        json={"status": "resolved", "reason": "作者已处理冲突"},
        headers=auth_headers,
    )
    assert r_author.status_code == 200
    assert r_author.json()["status"] == "resolved"

    # === 详情聚合验证 ===
    resp = await client.get(
        f"/api/v1/posts/{post_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    # 投票：second_user 最终是 refutation（替换了 confirmation）
    assert gov["total_validation_count"] == 1
    assert gov["refutation_count"] == 1
    assert gov["confirmation_count"] == 0
    # 报告：3 条总数，2 条已解决，1 条待处理（expiration_report 仍 open）
    assert gov["change_reports_total"] == 3
    assert gov["change_reports_open"] == 1
    assert len(gov["recent_change_reports"]) == 3
