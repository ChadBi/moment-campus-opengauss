"""UX-01.5: 通知偏好 API 测试

Task 2.2 调整：移除 site_digest_enabled / digest_time / email_enabled 字段，
        「每日摘要」「邮件通知」功能下线，相关测试用例同步删除。

覆盖：
1. GET /notifications/preferences 首次访问自动 upsert 默认偏好（6 类全部开启）
2. GET /notifications/preferences 需登录（401）
3. PUT /notifications/preferences 部分更新（仅更新提供的字段）
4. PUT /notifications/preferences 安全约束：system/audit/instant 全关时拒绝 (400)
5. PUT /notifications/preferences 需登录（401）
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_preferences_first_time_creates_default(
    client: AsyncClient, auth_headers: dict, test_school: dict
):
    """UX-01.5: 首次访问 GET /notifications/preferences 自动写入默认偏好"""
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 默认值校验：6 类开关全部开启
    assert data["instant_enabled"] is True
    assert data["subscription_enabled"] is True
    assert data["interaction_enabled"] is True
    assert data["audit_enabled"] is True
    assert data["governance_enabled"] is True
    assert data["system_enabled"] is True
    # Task 2.2: 已下线字段不应出现在响应中
    assert "site_digest_enabled" not in data
    assert "digest_time" not in data
    assert "email_enabled" not in data


@pytest.mark.asyncio
async def test_get_preferences_requires_auth(
    client: AsyncClient, test_school: dict
):
    """UX-01.5: 未登录访问 GET /notifications/preferences 返回 401"""
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_preferences_partial_update(
    client: AsyncClient, auth_headers: dict, test_school: dict
):
    """UX-01.5: PUT 部分更新——仅更新提供的字段，其余保持原值"""
    # 先 GET 触发默认偏好创建
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200

    # 仅更新 governance_enabled 与 interaction_enabled（Task 2.2: 改用未下线字段验证部分更新）
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={
            "governance_enabled": False,
            "interaction_enabled": False,
        },
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 更新的字段
    assert data["governance_enabled"] is False
    assert data["interaction_enabled"] is False
    # 未更新的字段保持默认
    assert data["instant_enabled"] is True
    assert data["subscription_enabled"] is True
    assert data["audit_enabled"] is True
    assert data["system_enabled"] is True


@pytest.mark.asyncio
async def test_update_preferences_security_constraint_rejects_all_off(
    client: AsyncClient, auth_headers: dict, test_school: dict
):
    """UX-01.5: 安全账号通知不可全关——system/audit/instant 全关时拒绝 (400)

    安全约束：保证至少有一个安全通道（instant 站内通知）。
    """
    # 先 GET 触发默认偏好创建
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200

    # 尝试同时关闭 system/audit/instant → 应被拒绝
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={
            "instant_enabled": False,
            "system_enabled": False,
            "audit_enabled": False,
        },
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 400
    # 错误信息提及安全约束
    assert "安全" in resp.json()["detail"] or "不可" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_preferences_allows_closing_system_when_instant_on(
    client: AsyncClient, auth_headers: dict, test_school: dict
):
    """UX-01.5: instant 开启时可以关闭 system/audit（不触发安全约束）"""
    # 先 GET 触发默认偏好创建
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200

    # instant 保持开启，关闭 system 与 audit → 应允许
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={
            "system_enabled": False,
            "audit_enabled": False,
        },
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["system_enabled"] is False
    assert data["audit_enabled"] is False
    assert data["instant_enabled"] is True  # 保持开启


@pytest.mark.asyncio
async def test_update_preferences_requires_auth(
    client: AsyncClient, test_school: dict
):
    """UX-01.5: 未登录访问 PUT /notifications/preferences 返回 401"""
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={"instant_enabled": False},
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_preferences_isolated_per_user(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict,
    test_school: dict,
):
    """UX-01.5: 通知偏好按 user_id 隔离——用户 A 的更新不影响用户 B"""
    # 用户 A 先 GET 触发默认偏好创建（与前端实际使用流程一致）
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200

    # 用户 A 更新偏好
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={"subscription_enabled": False, "interaction_enabled": False},
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200

    # 用户 B 查询偏好——应为默认值，不受 A 影响
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**second_auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subscription_enabled"] is True  # 默认值
    assert data["interaction_enabled"] is True   # 默认值
