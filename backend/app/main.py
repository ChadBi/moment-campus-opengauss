import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.router import api_router
from app.middleware import RequestLoggingMiddleware

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)

# 请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_event():
    # openGauss 兼容 PostgreSQL 协议，SQLAlchemy 连接串使用 postgresql+asyncpg scheme，
    # 但实际连接的是 openGauss 数据库。这里基于 APP_ENV 显示真实数据库类型。
    if settings.APP_ENV == "opengauss":
        db_display = "openGauss (asyncpg)"
    else:
        db_display = settings.DATABASE_URL.split("://")[0]
    logger.info(f"启动 {settings.APP_NAME} | 环境: {settings.APP_ENV} | DB: {db_display}")


@app.get("/")
async def root():
    return {"message": "Welcome to 此刻校园 API"}


@app.get("/health")
async def health():
    return {"status": "ok"}
