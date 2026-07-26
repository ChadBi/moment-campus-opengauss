"""UX-01.5: 通知偏好 API 测试

覆盖：
1. GET /notifications/preferences 首次访问自动 upsert 默认偏好（全部开启）
2. GET /notifications/preferences 需登录（401）
3. PUT /notifications/preferences 部分更新（仅更新提供的字段）
4. PUT /notifications/preferences 安全约束：system/audit/instant 全关时拒绝 (400)
5. PUT /notifications/preferences digest_time 格式校验
6. PUT /notifications/preferences 需登录（401）
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
    # 默认值校验：7 类开关 + digest_time + email_enabled
    assert data["instant_enabled"] is True
    assert data["site_digest_enabled"] is False
    assert data["subscription_enabled"] is True
    assert data["interaction_enabled"] is True
    assert data["audit_enabled"] is True
    assert data["governance_enabled"] is True
    assert data["system_enabled"] is True
    assert data["digest_time"] == "09:00"
    assert data["email_enabled"] is False


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

    # 仅更新 site_digest_enabled 与 digest_time
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={
            "site_digest_enabled": True,
            "digest_time": "18:30",
        },
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 更新的字段
    assert data["site_digest_enabled"] is True
    assert data["digest_time"] == "18:30"
    # 未更新的字段保持默认
    assert data["instant_enabled"] is True
    assert data["subscription_enabled"] is True
    assert data["interaction_enabled"] is True
    assert data["audit_enabled"] is True
    assert data["governance_enabled"] is True
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
async def test_update_preferences_invalid_digest_time_format(
    client: AsyncClient, auth_headers: dict, test_school: dict
):
    """UX-01.5: digest_time 格式校验——非 HH:MM 拒绝 (400)"""
    # 先 GET 触发默认偏好创建
    resp = await client.get(
        "/api/v1/notifications/preferences",
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200

    # 错误格式
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={"digest_time": "25:99"},
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 400

    # 非法字符串
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={"digest_time": "abcde"},
        headers={**auth_headers, "X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 400


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
