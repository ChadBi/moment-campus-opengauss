import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.api.router import api_router
from app.api.health import router as health_router
from app.middleware import (
    RequestLoggingMiddleware,
    RequestIDMiddleware,
    RateLimitMiddleware,
)

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

# ============================================================
# FND-03.5: 中间件注册（顺序：最先 add 的最外层）
# 真实请求处理顺序：CORS → RequestLogging → RateLimit → RequestID → 路由
# 1. RequestIDMiddleware 注入 X-Request-ID（最内层，最先执行，确保后续中间件能拿到）
# 2. RateLimitMiddleware 限流（在 RequestID 之后，可读取 request_id）
# 3. RequestLoggingMiddleware 日志（在最外层，能记录完整耗时）
# 4. CORSMiddleware（最外层）
# ============================================================
# 注意 add_middleware 后注册的先执行（栈结构），所以这里注册顺序反过来写：
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FND-03.5: 统一异常响应——所有异常返回 {detail, request_id}，不泄露堆栈
# ============================================================
def _get_request_id(request: Request) -> str:
    """从 request.state 获取 request_id，缺失则空串"""
    return getattr(request.state, "request_id", "") or ""


def _build_error_response(status_code: int, detail: str, request: Request) -> JSONResponse:
    """构造统一错误响应 JSON"""
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "request_id": _get_request_id(request),
        },
        headers={"X-Request-ID": _get_request_id(request)},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """统一 HTTP 异常响应（含 NotFound/Forbidden/BadRequest/Unauthorized/Conflict 等）

    FastAPI 的 HTTPException.detail 可能是字符串或 list（422 校验错误），
    统一封装为 {detail, request_id}，不泄露堆栈。
    """
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _build_error_response(exc.status_code, detail, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求参数校验失败（422）统一返回 {detail, request_id}"""
    # detail 用 exc.errors() 的字符串表示，便于前端调试但不泄露堆栈
    detail = f"请求参数校验失败：{exc.errors()}"
    return _build_error_response(422, detail, request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底：返回 500，不泄露堆栈信息

    日志中记录完整异常类型与 request_id 便于追踪，但响应只返回通用提示。
    """
    request_id = _get_request_id(request)
    logger.error(
        f"unhandled_exception request_id={request_id} "
        f"path={request.url.path} method={request.method} "
        f"exception={type(exc).__name__} detail={str(exc)[:200]}",
        exc_info=True,  # 日志中保留完整堆栈便于排查
    )
    return _build_error_response(
        500,
        "服务器内部错误，请稍后重试",
        request,
    )


# 路由
# REL-03.5: /health/live、/health/ready、/version 为根级端点（不在 /api/v1 前缀下）
app.include_router(health_router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ============================================================
# REL-03.2: 挂载 /uploads 静态目录（本地与容器行为一致）
# 启动时确保目录存在，避免 StaticFiles 挂载失败；
# 上传逻辑（app/api/upload.py）写入此目录，前端通过 /uploads/<filename> 访问。
# 不做公网部署，故不引入 Nginx 静态服务，由 FastAPI 直接提供静态文件。
# ============================================================
_upload_dir = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(_upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_upload_dir), name="uploads")


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
