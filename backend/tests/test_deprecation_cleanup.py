import warnings

from app.core.security import create_access_token, create_refresh_token
from app.main import app


def test_token_creation_does_not_use_deprecated_utcnow():
    """访问与刷新令牌签发不应触发 datetime.utcnow 弃用警告。"""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert create_access_token({"sub": "1"})
        assert create_refresh_token({"sub": "1"})


def test_password_reset_source_does_not_use_deprecated_utcnow():
    """密码重置后的令牌失效时间不应再调用 datetime.utcnow。"""
    import inspect

    from app.api.auth import reset_password

    assert "datetime.utcnow()" not in inspect.getsource(reset_password)


def test_fastapi_startup_uses_lifespan_instead_of_on_event():
    """应用启动逻辑应通过 lifespan 注册，而非已弃用的 on_event。"""
    assert app.router.on_startup == []
