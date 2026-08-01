"""为缺失向量的历史帖子批量回填 Embedding。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update

from app.database import async_session_maker
from app.models.post import Post
from app.models.school import School
from app.services.embedding_service import generate_post_embedding


STAT_KEYS = (
    "scanned",
    "updated",
    "generation_failed",
    "skipped_existing",
    "dry_run",
    "write_conflict",
    "school_not_found",
)


def empty_stats() -> dict[str, int]:
    return {key: 0 for key in STAT_KEYS}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="回填历史帖子 512 维 Embedding")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--school-code", type=str)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def build_batch_query(*, last_id: int, batch_size: int, school_code: str | None = None):
    statement = (
        select(Post)
        .where(Post.id > last_id, Post.embedding.is_(None))
        .order_by(Post.id)
        .limit(batch_size)
    )
    if school_code:
        statement = statement.join(School, School.id == Post.school_id).where(School.code == school_code)
    return statement


def print_stats(stats: dict[str, int]) -> None:
    print(" ".join(f"{key}={stats[key]}" for key in STAT_KEYS))


async def backfill_embeddings(
    posts: Iterable[Post],
    *,
    generate: Callable[[str, str], Awaitable[list[float] | None]] = generate_post_embedding,
    dry_run: bool = False,
) -> dict[str, int]:
    stats = empty_stats()
    for post in posts:
        stats["scanned"] += 1
        if post.embedding is not None:
            stats["skipped_existing"] += 1
            continue
        if dry_run:
            stats["dry_run"] += 1
            continue
        try:
            vector = await generate(post.title, post.content)
        except Exception:  # 单条外部调用失败不阻断后续帖子，且不记录文本或密钥
            stats["generation_failed"] += 1
            continue
        if vector is None:
            stats["generation_failed"] += 1
            continue
        post.embedding = vector
        stats["updated"] += 1
    return stats


async def _school_exists(school_code: str) -> bool:
    async with async_session_maker() as session:
        return await session.scalar(select(School.id).where(School.code == school_code)) is not None


async def _load_batch(last_id: int, batch_size: int, school_code: str | None) -> list[Post]:
    async with async_session_maker() as session:
        posts = list((await session.execute(build_batch_query(
            last_id=last_id,
            batch_size=batch_size,
            school_code=school_code,
        ))).scalars().all())
        for post in posts:
            session.expunge(post)
        return posts


async def _persist_batch(posts: Iterable[Post], stats: dict[str, int]) -> None:
    async with async_session_maker() as session:
        for post in posts:
            if post.embedding is None:
                continue
            result = await session.execute(
                update(Post)
                .where(
                    Post.id == post.id,
                    Post.school_id == post.school_id,
                    Post.embedding.is_(None),
                )
                .values(embedding=post.embedding)
            )
            if result.rowcount != 1:
                stats["updated"] -= 1
                stats["write_conflict"] += 1
        await session.commit()


async def run(
    batch_size: int,
    *,
    school_code: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    totals = empty_stats()
    if school_code and not await _school_exists(school_code):
        totals["school_not_found"] = 1
        return totals

    last_id = 0
    while limit is None or totals["scanned"] < limit:
        current_size = batch_size if limit is None else min(batch_size, limit - totals["scanned"])
        posts = await _load_batch(last_id, current_size, school_code)
        if not posts:
            break
        stats = await backfill_embeddings(posts, dry_run=dry_run)
        if not dry_run:
            await _persist_batch(posts, stats)
        for key, value in stats.items():
            totals[key] += value
        last_id = posts[-1].id
    return totals


if __name__ == "__main__":
    args = build_parser().parse_args()
    result = asyncio.run(run(
        max(1, args.batch_size),
        school_code=args.school_code,
        limit=None if args.limit is None else max(0, args.limit),
        dry_run=args.dry_run,
    ))
    print_stats(result)
