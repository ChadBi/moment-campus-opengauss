"""FND-03.5: 中间件——限流 + 请求 ID + 日志脱敏

包含：
1. RequestIDMiddleware: 接受/生成 X-Request-ID，贯穿日志与响应头
2. RateLimitMiddleware: 基于内存的滑动窗口限流，覆盖登录/注册/发布/评论/验证/举报/AI 搜索等关键接口
3. RequestLoggingMiddleware: 记录方法/路径/状态码/耗时，并对敏感参数脱敏

设计原则：
- 不引入新依赖（不使用 slowapi），自实现内存限流（适合本地开发单实例）
- 日志不输出 password/token/secret 等敏感字段
- 限流策略按 (client_ip, path_pattern) 维度，固定窗口 60 秒
"""
import os
import time
import uuid
import logging
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def _is_test_env() -> bool:
    """检测是否在测试环境（TEST_DATABASE_URL 存在即视为测试）

    测试时禁用限流以避免 fixture 频繁调用 /auth/register 等接口触发误拦。
    """
    return bool(os.environ.get("TEST_DATABASE_URL"))


def _is_production_env() -> bool:
    """检测是否在生产环境（APP_ENV=production）

    非生产环境（默认 opengauss，包含 dev / demo / seed / pytest）放宽限流 4 倍：
    - 登录 5 → 20 次/60 秒（避免 API 验证脚本 verify_*.py 频繁登录触发 429）
    - 注册 5 → 20 次/60 秒
    - 发布 / 评论 20 → 80 次/60 秒
    - AI 搜索 / AI 建议 10 → 40 次/60 秒
    """
    return os.environ.get("APP_ENV", "opengauss") == "production"


def _get_rate_limit_multiplier() -> int:
    """获取限流倍率（生产=1，非生产=4）"""
    return 1 if _is_production_env() else 4


# ============================================================
# FND-03.5.1: 请求 ID 中间件
# ============================================================
class RequestIDMiddleware(BaseHTTPMiddleware):
    """接受/生成 X-Request-ID，贯穿日志与响应头

    - 若请求头包含 X-Request-ID 则沿用（截断到 128 字符防滥用）
    - 否则生成 uuid4 hex
    - 注入到 request.state.request_id 供后续日志/审计使用
    - 在响应头返回 X-Request-ID
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        # 截断防止恶意超长 ID
        if len(request_id) > 128:
            request_id = request_id[:128]
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ============================================================
# FND-03.5.2: 限流中间件
# ============================================================
# 限流策略：(path_prefix, method) → (max_requests, window_seconds)
# 覆盖任务要求的：登录/注册/发布/评论/验证/举报/AI 搜索
# 单位：次/分钟（60 秒窗口）
RATE_LIMIT_RULES: list[tuple[str, str, int, int]] = [
    # 认证类：5 次/分钟（防爆破）
    ("/api/v1/auth/login", "POST", 5, 60),
    ("/api/v1/auth/register", "POST", 5, 60),
    ("/api/v1/auth/refresh", "POST", 10, 60),
    # AI-03: AI 辅助发布建议（10 次/分钟，与 AI 搜索一致）
    # 必须放在通用 /api/v1/posts 规则之前（startswith 匹配按声明顺序）
    ("/api/v1/posts/ai-suggest", "POST", 10, 60),
    # 发布信息 / 协同验证 / 举报（统一前缀 /api/v1/posts）：20 次/分钟
    ("/api/v1/posts", "POST", 20, 60),
    # 评论：20 次/分钟
    ("/api/v1/comments", "POST", 20, 60),
    # AI 搜索：10 次/分钟
    ("/api/v1/search/ai", "POST", 10, 60),
    # 普通上传：20 次/分钟
    ("/api/v1/upload", "POST", 20, 60),
]


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP（反向代理场景取 X-Forwarded-For 首个）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _match_rate_limit_rule(path: str, method: str) -> Optional[tuple[int, int]]:
    """匹配限流规则，返回 (max_requests, window_seconds) 或 None"""
    if method != "POST":
        return None
    for prefix, rule_method, max_req, window in RATE_LIMIT_RULES:
        if rule_method == method and path.startswith(prefix):
            return max_req, window
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于内存的固定窗口限流（适合本地开发单实例）

    维护 (client_ip, path) → [window_start, count] 计数器，
    窗口过期后自动重置。窗口内超过限额返回 429 Too Many Requests。
    """

    # 类变量：所有实例共享同一计数器（单进程）
    _counters: dict[tuple[str, str], list] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        # 测试环境禁用限流（避免 fixture 频繁调用 /auth/register 等触发误拦）
        if _is_test_env():
            return await call_next(request)

        path = request.url.path
        method = request.method

        rule = _match_rate_limit_rule(path, method)
        if rule is None:
            return await call_next(request)

        max_req, window = rule
        # 非生产环境放宽限流（dev / demo / seed / pytest 等）：倍率 ×4
        # - 登录 5 → 20 次/60 秒，避免 verify_*.py 脚本频繁登录触发 429
        max_req = max_req * _get_rate_limit_multiplier()
        client_ip = _get_client_ip(request)
        key = (client_ip, path)

        now = time.time()
        counter = self._counters.get(key)
        if counter is None or now - counter[0] >= window:
            # 窗口过期或首次访问，重置计数
            self._counters[key] = [now, 1]
        else:
            counter[1] += 1
            if counter[1] > max_req:
                request_id = getattr(request.state, "request_id", "")
                logger.warning(
                    f"rate_limit_exceeded ip={client_ip} path={path} "
                    f"count={counter[1]}/{max_req} request_id={request_id}"
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"请求过于频繁，请稍后再试（{max_req} 次/{window}秒）",
                        "request_id": request_id,
                    },
                    headers={
                        "X-Request-ID": request_id,
                        "Retry-After": str(window),
                    },
                )

        return await call_next(request)


# ============================================================
# FND-03.5.3: 日志脱敏
# ============================================================
# 敏感字段名（小写匹配）：出现在 query 参数 / 路径中时脱敏
SENSITIVE_PARAM_NAMES = {
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "authorization",
    "secret", "secret_key", "api_key", "apikey",
    "credit_card", "card_number",
}

# 日志中需要脱敏的字段值（出现在 query string 中）
_SENSITIVE_VALUE_PLACEHOLDER = "***REDACTED***"


def _sanitize_path(path: str) -> str:
    """对 URL path 中的敏感 query 参数值做脱敏

    例如：/api/v1/auth/login?password=abc123 → /api/v1/auth/login?password=***
    """
    if "?" not in path:
        return path
    base, query = path.split("?", 1)
    if not query:
        return path

    parts = []
    for kv in query.split("&"):
        if "=" in kv:
            key, _ = kv.split("=", 1)
            if key.lower() in SENSITIVE_PARAM_NAMES:
                parts.append(f"{key}={_SENSITIVE_VALUE_PLACEHOLDER}")
            else:
                parts.append(kv)
        else:
            parts.append(kv)
    return f"{base}?{'&'.join(parts)}"


def _should_log_body(path: str) -> bool:
    """判断该路径的请求体是否需要记录（默认不记录，避免泄露密码等）

    登录/注册/认证类接口的请求体绝不记录（含密码）。
    """
    sensitive_paths = (
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    )
    return not path.startswith(sensitive_paths)


# ============================================================
# FND-03.5.4: 请求日志中间件（增强版）
# ============================================================
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件

    记录每个请求的方法、路径（脱敏）、状态码和耗时，并关联 request_id。
    不输出请求体（含 password 等敏感字段）。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        method = request.method
        raw_path = request.url.path
        sanitized_path = _sanitize_path(str(request.url))
        request_id = getattr(request.state, "request_id", "")

        try:
            response = await call_next(request)
        except Exception as e:
            # REL-02.2: BaseHTTPMiddleware 中 call_next 抛出的异常可能绕过 FastAPI 的
            # 全局 Exception handler（已知 Starlette 问题），此处兜底返回 500，
            # 不泄露堆栈，仅记录异常类型 + request_id 便于追踪。
            process_time_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"{method} {sanitized_path} - 500 - {process_time_ms}ms "
                f"request_id={request_id} exception={type(e).__name__} "
                f"detail={str(e)[:200]}"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "服务器内部错误，请稍后重试",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        process_time = time.time() - start_time
        process_time_ms = round(process_time * 1000, 2)

        # 记录日志：method / 脱敏 path / 状态码 / 耗时 / request_id
        # 不记录请求体（含 password/token/密钥等敏感参数）
        logger.info(
            f"{method} {sanitized_path} - {response.status_code} - "
            f"{process_time_ms}ms request_id={request_id}"
        )

        response.headers["X-Process-Time"] = str(process_time_ms)
        return response
