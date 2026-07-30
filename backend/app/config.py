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
    # 默认放行 Vite 默认端口 5173 及其自动递增的回退端口 5174/5175（避免端口被占用切换后 CORS 拒绝）
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]

    # 日志
    LOG_LEVEL: str = "INFO"

    # ANA-01: 产品事件环境标记
    # 值域：production / demo / test / seed
    # 未显式配置时按 APP_ENV 推导：APP_ENV=opengauss → demo；APP_ENV=test → test；其余按字面值
    ANALYTICS_ENV: str = ""

    # ============================================================
    # AI-01: AI Provider 配置
    # 本地开发默认 mock（不依赖外部 API Key）；生产用 openai。
    # 密钥仅服务端环境变量，不进前端、不进日志、不进 git。
    # ============================================================
    # Provider 类型：mock / openai（默认 mock，确保无 API Key 也能运行测试）
    AI_PROVIDER: str = "mock"
    # OpenAI API Key（仅 openai 模式需要，mock 模式可留空）
    AI_API_KEY: str = ""
    # OpenAI API Base URL（可选，用于兼容代理/自建网关）
    AI_API_BASE: str = ""
    # 模型名
    AI_MODEL: str = "gpt-4o-mini"
    # 超时（秒，单次请求）
    AI_TIMEOUT: float = 15.0
    # 单次请求最大输出 Token
    AI_MAX_TOKENS: int = 1024
    # 最大重试次数（指数退避：1s, 2s, 4s）；不含首次调用
    AI_MAX_RETRIES: int = 3
    # 熔断：连续失败次数达到阈值后熔断
    AI_CIRCUIT_FAILURE_THRESHOLD: int = 5
    # 熔断恢复时间（秒）
    AI_CIRCUIT_RESET_SECONDS: int = 60

    # ============================================================
    # 微信小程序配置
    # AppID 和 AppSecret 用于 code2Session 换取 openid/session_key
    # AppSecret 仅存服务端环境变量，不进前端/Git
    # ============================================================
    WECHAT_APPID: str = ""
    WECHAT_APPSECRET: str = ""
    # binding_ticket 有效期（秒），默认 300 秒 = 5 分钟
    BINDING_TICKET_EXPIRE_SECONDS: int = 300

    class Config:
        env_file = _env_file
        extra = "ignore"


settings = Settings()
