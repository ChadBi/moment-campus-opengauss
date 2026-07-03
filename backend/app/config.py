import os
from pydantic_settings import BaseSettings
from typing import List

# backend/ 目录（config.py 位于 backend/app/config.py）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 项目已完全迁移至 openGauss，统一加载 .env.opengauss 配置文件。
# 若需通过环境变量覆盖，可设置 APP_ENV=opengauss（默认即走 openGauss）。
_env_file = os.path.join(_BASE_DIR, ".env.opengauss")


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "此刻校园"
    APP_ENV: str = "opengauss"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库（openGauss，asyncpg 异步驱动）
    # 注意：scheme 必须用 postgresql+asyncpg —— openGauss 兼容 PostgreSQL 协议，
    # SQLAlchemy 据此选择 asyncpg 驱动；这不是 PostgreSQL 数据库，实际连接的是 openGauss。
    DATABASE_URL: str = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600

    # 学校代号
    SCHOOL_CODE: str = "jiangnan"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # 日志
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = _env_file
        extra = "ignore"


settings = Settings()
