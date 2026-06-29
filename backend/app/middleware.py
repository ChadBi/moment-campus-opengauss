import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    记录每个请求的方法、路径和耗时
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # 记录请求开始时间
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        
        # 处理请求
        response = await call_next(request)
        
        # 计算耗时
        process_time = time.time() - start_time
        process_time_ms = round(process_time * 1000, 2)
        
        # 记录日志
        logger.info(
            f"{method} {path} - {response.status_code} - {process_time_ms}ms"
        )
        
        # 在响应头中添加耗时信息
        response.headers["X-Process-Time"] = str(process_time_ms)
        
        return response
