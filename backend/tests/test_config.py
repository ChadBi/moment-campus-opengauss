"""T-E-01 单元测试：app/config.py

覆盖 Settings 配置加载、默认值、openGauss 连接串。
"""
import os
import pytest

from app.config import Settings, settings


class TestSettingsDefaults:
    """Settings 默认值"""

    def test_app_name(self):
        assert "此刻校园" in settings.APP_NAME

    def test_app_env_is_opengauss(self):
        """项目已完全迁移，APP_ENV 默认为 opengauss"""
        assert settings.APP_ENV == "opengauss"

    def test_api_v1_prefix(self):
        assert settings.API_V1_PREFIX == "/api/v1"

    def test_school_code_is_jiangnan(self):
        """硬约束：江南大学代号 'jiangnan'"""
        assert settings.SCHOOL_CODE == "jiangnan"

    def test_algorithm(self):
        assert settings.ALGORITHM == "HS256"

    def test_access_token_expire_minutes(self):
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_refresh_token_expire_days(self):
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7


class TestDatabaseConfig:
    """数据库配置（openGauss）"""

    def test_database_url_uses_asyncpg(self):
        """DATABASE_URL 必须使用 asyncpg 驱动"""
        assert "asyncpg" in settings.DATABASE_URL

    def test_database_url_is_postgresql(self):
        assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")

    def test_database_url_contains_opengauss_credentials(self):
        """连接串包含 openGauss 用户 gaussdb"""
        assert "gaussdb" in settings.DATABASE_URL

    def test_database_url_password_url_encoded(self):
        """密码 Gaussdb@123 中 @ 必须编码为 %40"""
        assert "Gaussdb%40123" in settings.DATABASE_URL

    def test_database_url_contains_port_5432(self):
        assert ":5432" in settings.DATABASE_URL

    def test_database_url_contains_database_name(self):
        assert "/moment_campus" in settings.DATABASE_URL

    def test_pool_config(self):
        """连接池配置合理"""
        assert settings.DB_POOL_SIZE > 0
        assert settings.DB_MAX_OVERFLOW >= 0
        assert settings.DB_POOL_RECYCLE > 0


class TestJwtConfig:
    """JWT 配置"""

    def test_secret_key_exists(self):
        assert settings.SECRET_KEY is not None
        assert len(settings.SECRET_KEY) > 0

    def test_secret_key_not_default_in_production_warning(self):
        """默认 SECRET_KEY 是 change-me，生产应替换（此处仅校验默认值存在）"""
        # 测试环境使用默认值，仅验证可访问
        assert isinstance(settings.SECRET_KEY, str)


class TestCorsConfig:
    """CORS 配置"""

    def test_cors_origins_is_list(self):
        assert isinstance(settings.CORS_ORIGINS, list)

    def test_cors_includes_frontend_default(self):
        """CORS 包含前端默认端口 5173"""
        assert "http://localhost:5173" in settings.CORS_ORIGINS


class TestFileUploadConfig:
    """文件上传配置"""

    def test_upload_dir(self):
        assert settings.UPLOAD_DIR == "./uploads"

    def test_max_upload_size(self):
        """默认 5MB"""
        assert settings.MAX_UPLOAD_SIZE == 5 * 1024 * 1024
