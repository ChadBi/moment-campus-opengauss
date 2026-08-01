"""T7: 独立 OpenAI 兼容 Embedding 服务。"""
from __future__ import annotations

import logging
import math
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)
_client: Any = None


def build_post_embedding_text(title: str, content: str) -> str:
    """构造稳定且有上限的帖子向量输入。"""
    title = (title or "").strip()
    content = (content or "").strip()
    return f"{title}\n{content}"[:8000].strip()


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": settings.EMBEDDING_API_KEY,
            "timeout": settings.EMBEDDING_TIMEOUT,
            "max_retries": 1,
        }
        if settings.EMBEDDING_API_BASE:
            kwargs["base_url"] = settings.EMBEDDING_API_BASE
        _client = AsyncOpenAI(**kwargs)
    return _client


async def generate_embedding(text: str) -> list[float] | None:
    """生成 512 维向量；配置缺失或调用失败时安全返回 None。"""
    normalized = (text or "").strip()
    if not normalized or settings.EMBEDDING_PROVIDER != "openai" or not settings.EMBEDDING_API_KEY:
        return None
    try:
        response = await _get_client().embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=normalized,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        vector = [float(value) for value in response.data[0].embedding]
        if len(vector) != settings.EMBEDDING_DIMENSIONS:
            logger.warning("embedding_dimension_mismatch expected=%d actual=%d", settings.EMBEDDING_DIMENSIONS, len(vector))
            return None
        if not all(math.isfinite(value) for value in vector):
            logger.warning("embedding_non_finite_response")
            return None
        return vector
    except Exception as exc:  # 外部能力不得阻断帖子主链路
        logger.warning("embedding_generation_failed error_type=%s", type(exc).__name__)
        return None


async def generate_post_embedding(title: str, content: str) -> list[float] | None:
    return await generate_embedding(build_post_embedding_text(title, content))
