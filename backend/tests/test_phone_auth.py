"""手机号主账号改造的定向接口测试。"""

import pytest
from sqlalchemy import select

from app.models.school import School
from app.models.school_domain import SchoolDomain
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity


async def _send_code(client, phone: str, purpose: str) -> str:
    response = await client.post(
        "/api/v1/auth/sms/send",
        json={"phone": phone, "purpose": purpose},
    )
    assert response.status_code == 200, response.text
    return response.json().get("code", "123456")


@pytest.mark.asyncio
async def test_phone_register_password_and_sms_login(client, test_school):
    phone = "13820000001"
    code = await _send_code(client, phone, "register")
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": phone,
            "sms_code": code,
            "password": "test1234",
            "password_confirm": "test1234",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["phone"] == phone
    assert user["education_email"] is None
    assert user["has_password"] is True
    assert "email" not in user
    assert user["campus_verified"] is False

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": phone,
            "sms_code": code,
            "password": "test1234",
            "password_confirm": "test1234",
            "school_id": test_school["id"],
        },
    )
    assert duplicate.status_code == 409

    password_login = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": "test1234"},
    )
    assert password_login.status_code == 200

    sms_code = await _send_code(client, phone, "login")
    sms_login = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "sms_code": sms_code},
    )
    assert sms_login.status_code == 200


@pytest.mark.asyncio
async def test_sms_send_interval_is_sixty_seconds(client):
    phone = "13820000002"
    assert await _send_code(client, phone, "login") == "123456"
    response = await client.post(
        "/api/v1/auth/sms/send",
        json={"phone": phone, "purpose": "login"},
    )
    assert response.status_code == 400
    assert "60" in response.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_phone_login_creates_passwordless_account_and_can_set_password(
    client, test_school
):
    response = await client.post(
        "/api/v1/auth/wechat/phone-login",
        json={"code": "mock-code", "phone_code": "mock-phone-code", "school_code": test_school["code"]},
    )
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["has_password"] is False
    assert user["campus_verified"] is False
    assert user["school_id"] == test_school["id"]
    assert user["registration_school_id"] == test_school["id"]
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    set_password = await client.post(
        "/api/v1/auth/password/set",
        json={"password": "wechat123", "password_confirm": "wechat123"},
        headers=headers,
    )
    assert set_password.status_code == 200, set_password.text
    second_set = await client.post(
        "/api/v1/auth/password/set",
        json={"password": "wechat456", "password_confirm": "wechat456"},
        headers=headers,
    )
    assert second_set.status_code == 409

    repeat = await client.post(
        "/api/v1/auth/wechat/phone-login",
        json={"code": "mock-code-2", "phone_code": "mock-phone-code", "school_code": test_school["code"]},
    )
    assert repeat.status_code == 200
    assert repeat.json()["user"]["id"] == user["id"]


@pytest.mark.asyncio
async def test_wechat_sms_login_creates_passwordless_account_and_binds_identity(
    client, test_school, db_session
):
    phone = "13820000012"
    sms_code = await _send_code(client, phone, "login")
    response = await client.post(
        "/api/v1/auth/wechat/sms-login",
        json={
            "code": "mock-sms-code",
            "phone": phone,
            "sms_code": sms_code,
            "school_code": test_school["code"],
        },
    )
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["phone"] == phone
    assert user["has_password"] is False
    assert user["campus_verified"] is False

    identity = (
        await db_session.execute(
            select(UserAuthIdentity).where(
                UserAuthIdentity.user_id == user["id"],
                UserAuthIdentity.identity_type == "wechat_miniprogram",
                UserAuthIdentity.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    assert identity is not None
    membership = (
        await db_session.execute(
            select(SchoolMembership).where(
                SchoolMembership.user_id == user["id"],
                SchoolMembership.status == "active",
            )
        )
    ).scalar_one()
    assert membership.school_id == test_school["id"]
    assert membership.is_default is True


@pytest.mark.asyncio
async def test_wechat_sms_login_reuses_existing_phone_account_without_switching_school(
    client, test_school, db_session
):
    phone = "13820000013"
    register_code = await _send_code(client, phone, "register")
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": phone,
            "sms_code": register_code,
            "password": "existing123",
            "password_confirm": "existing123",
            "school_id": test_school["id"],
        },
    )
    assert registered.status_code == 200, registered.text

    other_school = School(name="其他测试大学", code="other-test-uni", is_active=True)
    db_session.add(other_school)
    await db_session.commit()
    await db_session.refresh(other_school)

    login_code = await _send_code(client, phone, "login")
    response = await client.post(
        "/api/v1/auth/wechat/sms-login",
        json={
            "code": "mock-existing-code",
            "phone": phone,
            "sms_code": login_code,
            "school_code": other_school.code,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == registered.json()["user"]["id"]
    assert response.json()["user"]["has_password"] is True
    assert response.json()["user"]["school_id"] == test_school["id"]
    membership = (
        await db_session.execute(
            select(SchoolMembership).where(
                SchoolMembership.user_id == registered.json()["user"]["id"],
                SchoolMembership.status == "active",
            )
        )
    ).scalar_one()
    assert membership.school_id == test_school["id"]


@pytest.mark.asyncio
async def test_wechat_sms_login_rejects_invalid_sms_code(client, test_school, db_session):
    phone = "13820000014"
    await _send_code(client, phone, "login")
    response = await client.post(
        "/api/v1/auth/wechat/sms-login",
        json={
            "code": "mock-invalid-code",
            "phone": phone,
            "sms_code": "654321",
            "school_code": test_school["code"],
        },
    )
    assert response.status_code == 400
    assert "验证码错误" in response.json()["detail"]
    user = (await db_session.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
    assert user is None


@pytest.mark.asyncio
async def test_education_email_unique_confirm_and_unbind(client, test_school, db_session):
    db_session.add(SchoolDomain(school_id=test_school["id"], domain="test-uni.edu.cn", is_primary=True))
    await db_session.commit()

    first_phone = "13820000003"
    first_code = await _send_code(client, first_phone, "register")
    first = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": first_phone,
            "sms_code": first_code,
            "password": "first123",
            "password_confirm": "first123",
            "school_id": test_school["id"],
        },
    )
    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    send = await client.post(
        "/api/v1/users/me/education-email/send",
        json={"education_email": "student@test-uni.edu.cn"},
        headers=first_headers,
    )
    assert send.status_code == 200
    confirm = await client.post(
        "/api/v1/users/me/education-email/confirm",
        json={"code": send.json().get("code", "123456")},
        headers=first_headers,
    )
    assert confirm.status_code == 200

    second_phone = "13820000004"
    second_code = await _send_code(client, second_phone, "register")
    second = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": second_phone,
            "sms_code": second_code,
            "password": "second123",
            "password_confirm": "second123",
            "school_id": test_school["id"],
        },
    )
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
    duplicate_email = await client.post(
        "/api/v1/users/me/education-email/send",
        json={"education_email": "STUDENT@test-uni.edu.cn"},
        headers=second_headers,
    )
    assert duplicate_email.status_code == 409

    unbind_send = await client.post(
        "/api/v1/users/me/education-email/unbind/send",
        json={},
        headers=first_headers,
    )
    assert unbind_send.status_code == 200
    unbind = await client.request(
        "DELETE",
        "/api/v1/users/me/education-email",
        json={"sms_code": unbind_send.json().get("code", "123456")},
        headers=first_headers,
    )
    assert unbind.status_code == 200
    assert unbind.json()["education_email"] is None
    assert unbind.json()["campus_verified"] is False
