"""REV-01: 附近地点接口测试。

覆盖：距离升序排序、半径过滤、距离字段、跨校隔离。
"""
import pytest
import pytest_asyncio

from app.models.location import Location
from app.models.school import School


@pytest_asyncio.fixture
async def locations_with_distance(db_session, test_school: dict) -> dict:
    """在测试学校创建 3 个不同距离的地点（参考点 31.0, 120.0）。"""
    coords = [
        ("近处打印店", 31.001, 120.001),   # ~157m
        ("中距离食堂", 31.01, 120.01),     # ~1.57km
        ("远处图书馆", 31.1, 120.1),       # ~15.7km
    ]
    for name, lat, lng in coords:
        db_session.add(Location(
            school_id=test_school["id"], name=name,
            latitude=lat, longitude=lng, is_deleted=False,
        ))
    await db_session.commit()
    return {"ref_lat": 31.0, "ref_lng": 120.0}


@pytest.mark.asyncio
async def test_nearby_sorted_by_distance(client, auth_headers, locations_with_distance: dict):
    resp = await client.get(
        "/api/v1/locations/nearby",
        params={
            "lat": locations_with_distance["ref_lat"],
            "lng": locations_with_distance["ref_lng"],
            "radius": 30000,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    names = [i["name"] for i in body["items"]]
    assert names == ["近处打印店", "中距离食堂", "远处图书馆"]
    # 距离升序
    distances = [i["distance"] for i in body["items"]]
    assert distances == sorted(distances)
    assert all(d is not None for d in distances)


@pytest.mark.asyncio
async def test_nearby_radius_filter(client, auth_headers, locations_with_distance: dict):
    resp = await client.get(
        "/api/v1/locations/nearby",
        params={
            "lat": locations_with_distance["ref_lat"],
            "lng": locations_with_distance["ref_lng"],
            "radius": 2000,
        },
        headers=auth_headers,
    )
    body = resp.json()
    names = [i["name"] for i in body["items"]]
    assert names == ["近处打印店", "中距离食堂"]  # 远处图书馆超出 2km 被过滤


@pytest.mark.asyncio
async def test_nearby_tenant_isolation(
    client, auth_headers, db_session, test_school: dict
):
    """其他学校的地点不出现在本学校签名后的附近结果中。"""
    # 本学校地点
    db_session.add(Location(
        school_id=test_school["id"], name="本校地点",
        latitude=31.0, longitude=120.0, is_deleted=False,
    ))
    # 其他学校地点（更近也在其它学校）
    school2 = School(name="别校", code="other2", is_active=True)
    db_session.add(school2)
    await db_session.flush()
    db_session.add(Location(
        school_id=school2.id, name="别校地点",
        latitude=31.0, longitude=120.0, is_deleted=False,
    ))
    await db_session.commit()

    resp = await client.get(
        "/api/v1/locations/nearby",
        params={"lat": 31.0, "lng": 120.0, "radius": 5000},
        headers=auth_headers,
    )
    body = resp.json()
    names = [i["name"] for i in body["items"]]
    assert "本校地点" in names
    assert "别校地点" not in names


@pytest.mark.asyncio
async def test_nearby_returns_rating_fields(client, auth_headers, test_school: dict, db_session):
    db_session.add(Location(
        school_id=test_school["id"], name="文印店",
        latitude=31.0, longitude=120.0, is_deleted=False,
    ))
    await db_session.commit()

    resp = await client.get(
        "/api/v1/locations/nearby",
        params={"lat": 31.0, "lng": 120.0, "radius": 5000},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    # 附近场景返回评分汇总 + 距离
    assert "avg_score" in item
    assert "rating_count" in item
    assert "review_count" in item
    assert item["distance"] is not None


@pytest.mark.asyncio
async def test_nearby_requires_school_for_guest(client, test_school: dict):
    """游客未提供 X-School-Code 时返回 404（get_tenant_context 约束）。"""
    resp = await client.get(
        "/api/v1/locations/nearby",
        params={"lat": 31.0, "lng": 120.0, "radius": 5000},
    )
    assert resp.status_code == 404