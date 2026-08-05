"""REV-01: 地点评分/评价接口测试。

覆盖：提交/更新/撤回评价、评分统计重算、未登录校验、跨校隔离、参数校验。
"""
import pytest
import pytest_asyncio
from typing import AsyncGenerator

from app.models.location import Location
from app.models.location_review import LocationReview
from app.models.school import School


@pytest_asyncio.fixture
async def test_location(db_session, test_school: dict) -> dict:
    """创建测试地点（打印店）。"""
    loc = Location(
        school_id=test_school["id"],
        name="测试打印店",
        description="校园打印店",
        latitude=31.5,
        longitude=120.3,
        is_deleted=False,
    )
    db_session.add(loc)
    await db_session.commit()
    await db_session.refresh(loc)
    return {"id": loc.id, "name": loc.name, "school_id": loc.school_id}


@pytest_asyncio.fixture
async def other_school(db_session) -> dict:
    """创建另一所学校（用于跨校隔离测试）。"""
    school = School(name="其他大学", code="other-uni", is_active=True)
    db_session.add(school)
    await db_session.commit()
    await db_session.refresh(school)
    return {"id": school.id, "code": school.code}


@pytest.mark.asyncio
async def test_submit_review_updates_rating(
    client, auth_headers, test_location: dict
):
    resp = await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 5, "content": "打印很快，老板人好"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["score"] == 5
    assert data["author"] is not None

    # 地点评分同步更新
    detail = await client.get(f"/api/v1/locations/{test_location['id']}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()["location"]
    assert body["avg_score"] == 5.0
    assert body["rating_count"] == 1
    assert body["review_count"] == 1


@pytest.mark.asyncio
async def test_update_review_recalculates_average(
    client, auth_headers, second_auth_headers, test_location: dict
):
    # 用户1 打 5 分
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 5},
        headers=auth_headers,
    )
    # 用户2 打 1 分
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 1, "content": "太贵了"},
        headers=second_auth_headers,
    )
    detail = (await client.get(
        f"/api/v1/locations/{test_location['id']}", headers=auth_headers
    )).json()["location"]
    assert detail["avg_score"] == 3.0
    assert detail["rating_count"] == 2

    # 用户2 更新为 5 分 → 平均分变为 5
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 5, "content": "改主意了，其实不错"},
        headers=second_auth_headers,
    )
    detail = (await client.get(
        f"/api/v1/locations/{test_location['id']}", headers=auth_headers
    )).json()["location"]
    assert detail["avg_score"] == 5.0
    assert detail["rating_count"] == 2


@pytest.mark.asyncio
async def test_delete_review_recalculates(
    client, auth_headers, second_auth_headers, test_location: dict
):
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 5},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 1},
        headers=second_auth_headers,
    )
    # 用户1 撤回 → 只剩用户2 的 1 分
    resp = await client.delete(
        f"/api/v1/locations/{test_location['id']}/reviews",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    detail = (await client.get(
        f"/api/v1/locations/{test_location['id']}", headers=auth_headers
    )).json()["location"]
    assert detail["avg_score"] == 1.0
    assert detail["rating_count"] == 1


@pytest.mark.asyncio
async def test_review_requires_auth(client, test_location: dict):
    resp = await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 5},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_review_score_validation(client, auth_headers, test_location: dict):
    resp = await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 6},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cross_tenant_review_returns_404(
    client, auth_headers, db_session, other_school: dict
):
    """跨校地点不可评分（资源级租户隔离 → 404）。"""
    loc = Location(
        school_id=other_school["id"],
        name="别校打印店",
        latitude=30.0,
        longitude=120.0,
        is_deleted=False,
    )
    db_session.add(loc)
    await db_session.commit()
    await db_session.refresh(loc)

    resp = await client.post(
        f"/api/v1/locations/{loc.id}/reviews",
        json={"score": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reviews_list(
    client, auth_headers, second_auth_headers, test_location: dict
):
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 5, "content": "很好"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 1, "content": "一般"},
        headers=second_auth_headers,
    )
    resp = await client.get(
        f"/api/v1/locations/{test_location['id']}/reviews", headers=second_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    contents = {r["content"] for r in body["items"]}
    assert contents == {"很好", "一般"}


@pytest.mark.asyncio
async def test_location_detail_returns_my_review(
    client, auth_headers, test_location: dict
):
    # 未评价时 my_review 为 None
    detail = (await client.get(
        f"/api/v1/locations/{test_location['id']}", headers=auth_headers
    )).json()
    assert detail["my_review"] is None
    assert detail["location"]["name"] == "测试打印店"

    # 评价后 my_review 返回
    await client.post(
        f"/api/v1/locations/{test_location['id']}/reviews",
        json={"score": 4, "content": "还不错"},
        headers=auth_headers,
    )
    detail = (await client.get(
        f"/api/v1/locations/{test_location['id']}", headers=auth_headers
    )).json()
    assert detail["my_review"]["score"] == 4