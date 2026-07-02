import os
from pydantic_settings import BaseSettings
from typing import List

# backend/ 目录（config.py 位于 backend/app/config.py）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 根据 APP_ENV 环境变量选择加载哪个 .env 文件（使用绝对路径，避免受 CWD 影响）
_env_file = os.path.join(
    _BASE_DIR,
    ".env.opengauss" if os.environ.get("APP_ENV") == "opengauss" else ".env.development",
)


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "此刻校园"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
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
