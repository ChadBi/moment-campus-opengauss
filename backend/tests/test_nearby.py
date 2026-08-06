"""已废弃的实时定位/距离接口边界测试。

历史版本曾提供 /locations/nearby；当前产品只保留学校静态地图与地点坐标，
因此该入口必须不可访问。
"""

import pytest


@pytest.mark.asyncio
async def test_nearby_endpoint_removed(client, auth_headers, test_school: dict):
    response = await client.get(
        "/api/v1/locations/nearby",
        params={"lat": 31.5, "lng": 120.3},
        headers=auth_headers,
    )
    assert response.status_code in {404, 405, 422}
