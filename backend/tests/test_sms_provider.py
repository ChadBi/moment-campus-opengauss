"""阿里云短信用途模板映射测试。"""

import pytest

from app.config import settings
from app.services.sms import AliyunSmsProvider


@pytest.mark.parametrize(
    ("purpose", "setting_name"),
    [
        ("register", "ALIYUN_SMS_REGISTER_TEMPLATE_CODE"),
        ("login", "ALIYUN_SMS_LOGIN_TEMPLATE_CODE"),
        ("set_password", "ALIYUN_SMS_SET_PASSWORD_TEMPLATE_CODE"),
        ("education_unbind", "ALIYUN_SMS_EDUCATION_UNBIND_TEMPLATE_CODE"),
    ],
)
def test_aliyun_sms_template_is_selected_by_purpose(monkeypatch, purpose, setting_name):
    monkeypatch.setattr(settings, "ALIYUN_SMS_TEMPLATE_CODE", "legacy-template")
    monkeypatch.setattr(settings, setting_name, f"{purpose}-template")

    assert AliyunSmsProvider._template_code(purpose) == f"{purpose}-template"


def test_aliyun_sms_template_falls_back_to_legacy_setting(monkeypatch):
    monkeypatch.setattr(settings, "ALIYUN_SMS_TEMPLATE_CODE", "legacy-template")
    for setting_name in (
        "ALIYUN_SMS_REGISTER_TEMPLATE_CODE",
        "ALIYUN_SMS_LOGIN_TEMPLATE_CODE",
        "ALIYUN_SMS_SET_PASSWORD_TEMPLATE_CODE",
        "ALIYUN_SMS_EDUCATION_UNBIND_TEMPLATE_CODE",
    ):
        monkeypatch.setattr(settings, setting_name, "")

    assert AliyunSmsProvider._template_code("login") == "legacy-template"


def test_aliyun_sms_template_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "ALIYUN_SMS_TEMPLATE_CODE", "")
    monkeypatch.setattr(settings, "ALIYUN_SMS_LOGIN_TEMPLATE_CODE", "")

    with pytest.raises(RuntimeError, match="login"):
        AliyunSmsProvider._template_code("login")
