"""REL-03.5: 本地开发辅助接口——健康检查与版本

提供三个根级端点（不在 /api/v1 前缀下）：
- GET /health/live  : 进程可响应（始终返回 alive）
- GET /health/ready : DB 连接 + /uploads 目录 + AI 配置检查；AI 故障标 degraded 而非全站不可用
- GET /version      : 提交 SHA / 构建时间 / 迁移版本 / 应用环境

重要约束（依据 REL-03.5）：
- 这些接口仅作本地开发辅助，不作为生产发布门禁。
- 不做公网部署，因此不引入 Nginx/HTTPS 相关逻辑。
- AI 配置缺失只降级不阻断：AI 故障时全站仍可用，仅 AI 搜索相关能力退化为普通搜索。
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["健康检查"])


@router.get("/health/live")
async def health_live():
    """存活探针：进程可响应即返回 alive。

    不检查任何依赖（DB/磁盘/AI），仅证明 FastAPI 事件循环可调度。
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    """就绪探针：检查 DB 连接 + /uploads 目录 + AI 配置。

    判定规则：
        - DB 或 /uploads 任一失败 → 503 unavailable（关键依赖不可用）
        - AI 配置缺失但 DB/uploads 正常 → 200 degraded（不阻断，AI 搜索降级为普通搜索）
        - 全部正常 → 200 ready

    本接口仅作本地开发辅助，不作为生产发布门禁。
    """
    checks = {}
    all_critical_ok = True

    # 1. DB 连接（SELECT 1）
    try:
        result = await db.execute(text("SELECT 1"))
        row = result.scalar_one_or_none()
        if row == 1:
            checks["db"] = "ok"
        else:
            checks["db"] = "fail: unexpected result"
            all_critical_ok = False
    except Exception as e:
        checks["db"] = f"fail: {type(e).__name__}"
        all_critical_ok = False
        logger.warning(f"health_ready db check failed: {type(e).__name__}: {e}")

    # 2. /uploads 目录存在且可写（跨平台：实际尝试写入临时文件）
    try:
        upload_dir = os.path.abspath(settings.UPLOAD_DIR)
        if not os.path.isdir(upload_dir):
            checks["uploads"] = "fail: directory not found"
            all_critical_ok = False
        else:
            # 用实际写入测试可写性（Windows 下 os.access 不可靠）
            test_file = os.path.join(upload_dir, f".health_check_{os.getpid()}.tmp")
            try:
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write("ok")
                os.remove(test_file)
                checks["uploads"] = "ok"
            except OSError as e:
                checks["uploads"] = f"fail: not writable ({type(e).__name__})"
                all_critical_ok = False
    except Exception as e:
        checks["uploads"] = f"fail: {type(e).__name__}"
        all_critical_ok = False

    # 3. AI 配置（非阻断：缺失只标 degraded，不影响就绪判定）
    ai_provider = os.environ.get("AI_PROVIDER", "").strip()
    if ai_provider:
        checks["ai"] = "ok"
        ai_ok = True
    else:
        checks["ai"] = "degraded: AI_PROVIDER not configured"
        ai_ok = False

    # 状态汇总
    if not all_critical_ok:
        status = "unavailable"
        http_status = 503
    elif not ai_ok:
        status = "degraded"
        http_status = 200
    else:
        status = "ready"
        http_status = 200

    return JSONResponse(
        status_code=http_status,
        content={
            "status": status,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get("/version")
async def version():
    """版本信息：提交 SHA / 构建时间 / 迁移版本 / 应用环境。

    字段来源：
        - commit_sha: 环境变量 GIT_COMMIT_SHA（本地开发默认 "local"）
        - build_time: 环境变量 BUILD_TIME（缺失则用当前时间）
        - migration_version: 查询 alembic_version 表当前版本
        - app_env: settings.APP_ENV

    本接口仅作本地开发辅助，非生产发布门禁。
    """
    # commit_sha: 优先环境变量，本地开发默认 "local"
    commit_sha = os.environ.get("GIT_COMMIT_SHA", "local") or "local"
    # build_time: 优先环境变量，否则用当前时间
    build_time = os.environ.get("BUILD_TIME") or datetime.now(timezone.utc).isoformat()

    # migration_version: 从 alembic_version 表读取当前版本
    migration_version = "unknown"
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.scalar_one_or_none()
            if row:
                migration_version = str(row)
    except Exception as e:
        logger.warning(f"version migration_version query failed: {type(e).__name__}: {e}")
        migration_version = f"error: {type(e).__name__}"

    return {
        "commit_sha": commit_sha,
        "build_time": build_time,
        "migration_version": migration_version,
        "app_env": settings.APP_ENV,
        "app_name": settings.APP_NAME,
    }
