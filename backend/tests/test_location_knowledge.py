"""地点知识层：资料提议、管理员审核和摘要空状态。"""

import pytest
import pytest_asyncio

from app.models.location import Location


@pytest_asyncio.fixture
async def knowledge_location(db_session, test_school: dict) -> dict:
    location = Location(
        school_id=test_school["id"],
        name="知识层测试地点",
        description="用于资料审核测试",
        latitude=31.5,
        longitude=120.3,
        is_deleted=False,
    )
    db_session.add(location)
    await db_session.commit()
    await db_session.refresh(location)
    return {"id": location.id, "school_id": location.school_id}


@pytest.mark.asyncio
async def test_fact_proposal_duplicate_and_admin_approval(
    client, auth_headers, admin_headers, knowledge_location: dict
):
    path = f"/api/v1/locations/{knowledge_location['id']}/fact-proposals"
    payload = {
        "upserts": [{
            "fact_key": "normal_hours",
            "label": "营业时间",
            "value": "工作日 08:00-18:00",
        }],
        "reason": "现场公告核对",
    }
    created = await client.post(path, json=payload, headers=auth_headers)
    assert created.status_code == 201
    assert created.json()["status"] == "pending"

    duplicate = await client.post(path, json=payload, headers=auth_headers)
    assert duplicate.status_code == 409

    queue = await client.get(
        "/api/v1/admin/location-fact-proposals",
        headers=admin_headers,
    )
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    proposal_id = queue.json()["items"][0]["id"]

    approved = await client.post(
        f"/api/v1/admin/location-fact-proposals/{proposal_id}/approve",
        json={"reason": "公告已核对"},
        headers=admin_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    detail = await client.get(
        f"/api/v1/locations/{knowledge_location['id']}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["facts"][0]["value"] == "工作日 08:00-18:00"


@pytest.mark.asyncio
async def test_location_summary_without_evidence_is_explicit_empty_state(
    client, auth_headers, knowledge_location: dict
):
    response = await client.get(
        f"/api/v1/locations/{knowledge_location['id']}/summary",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient"
    assert body["confidence_level"] == "insufficient"
    assert body["claims"] == []

