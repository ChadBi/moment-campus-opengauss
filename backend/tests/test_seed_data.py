"""手机号体系演示数据的静态配置校验。"""

from scripts.seed_data import SCHOOLS_REGISTRY


def _all_users():
    return [user for school in SCHOOLS_REGISTRY for user in school["users"]]


def test_seed_users_use_unique_phone_accounts_and_consistent_campus_state():
    users = _all_users()
    phones = [user["phone"] for user in users]

    assert len(phones) == len(set(phones))
    assert all(len(phone) == 11 and phone.isdigit() for phone in phones)
    assert all("email" not in user for user in users)
    assert all(
        user.get("campus_verified", False) == bool(user.get("education_email"))
        for user in users
    )


def test_seed_wechat_demo_account_is_passwordless_with_fixed_identity():
    wechat_users = [user for user in _all_users() if user.get("auth_mode") == "wechat"]

    assert len(wechat_users) == 1
    account = wechat_users[0]
    assert account["phone"] == "13800138000"
    assert account.get("password") is None
    assert account["wechat_openid"] == "MOCK_OPENID_STATIC_20260808_LOCAL_DEV"
    assert not account.get("campus_verified", False)
    assert "education_email" not in account


def test_seed_content_references_existing_phone_accounts():
    phones = {user["phone"] for user in _all_users()}

    for school in SCHOOLS_REGISTRY:
        for post in [*school["posts"], *school.get("status_samples", [])]:
            assert post["user_phone"] in phones
            assert all(comment["user_phone"] in phones for comment in post.get("comments", []))
            assert all(validation["user_phone"] in phones for validation in post.get("validations", []))
        assert all(topic[2] in phones for topic in school["topics"])
