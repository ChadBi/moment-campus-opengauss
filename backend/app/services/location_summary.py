"""地点知识层：稳定资料、AI 摘要、来源校验与刷新标记。"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.ai.location_summary import LOCATION_SUMMARY_SCHEMA
from app.ai.provider import AIInvokeOptions, AIProvider
from app.ai.service import invoke_ai
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.tenant import TenantContext, check_resource_in_tenant
from app.models.location import Location
from app.models.location_fact import LocationFact
from app.models.location_summary import LocationSummaryVersion
from app.models.location_review import LocationReview
from app.models.post import Post
from app.models.user import User
from app.schemas.location_knowledge import LocationSummaryResponse

logger = logging.getLogger(__name__)

SUMMARY_SCENE = "location_summary"
SUMMARY_POST_DAYS = 7
SUMMARY_REVIEW_DAYS = 30
SUMMARY_MAX_POSTS = 20
SUMMARY_MAX_REVIEWS = 20


def summary_response(summary: Optional[LocationSummaryVersion], sources: list[dict[str, Any]]) -> LocationSummaryResponse:
    """将已批准摘要转换为统一公开响应；没有摘要时返回证据不足空状态。"""
    if summary is None:
        return LocationSummaryResponse(status="insufficient", confidence_level="insufficient", sources=[])
    return LocationSummaryResponse(
        id=summary.id,
        version=summary.version,
        status=summary.status,
        summary_text=summary.summary_text,
        confidence_level=summary.confidence_level,
        claims=summary.claims_json or [],
        conflicts=summary.conflicts_json or [],
        source_count=summary.source_count,
        generated_at=summary.generated_at,
        stale_at=summary.stale_at,
        sources=sources,
    )


def _source_key(source_type: str, source_id: int) -> str:
    return f"{source_type}:{source_id}"


async def mark_location_summary_dirty(db: AsyncSession, location_id: Optional[int]) -> None:
    """标记地点需要刷新摘要；没有地点关联的内容直接忽略。"""
    if location_id is None:
        return
    location = await db.get(Location, location_id)
    if location is not None and location.is_deleted is False:
        location.summary_dirty_at = location.summary_dirty_at or datetime.now()


async def _load_location(db: AsyncSession, location_id: int, tenant: TenantContext) -> Location:
    location = await db.scalar(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    if location is None:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(location.school_id, tenant)
    return location


async def load_location_facts(db: AsyncSession, location_id: int, school_id: int) -> list[LocationFact]:
    result = await db.execute(
        select(LocationFact)
        .where(
            LocationFact.location_id == location_id,
            LocationFact.school_id == school_id,
            LocationFact.is_active == True,
        )
        .order_by(LocationFact.sort_order.asc(), LocationFact.id.asc())
    )
    return list(result.scalars().all())


async def load_current_summary(db: AsyncSession, location: Location) -> Optional[LocationSummaryVersion]:
    if location.current_summary_id is None:
        return None
    summary = await db.get(LocationSummaryVersion, location.current_summary_id)
    if summary is None or summary.status != "approved" or summary.school_id != location.school_id:
        return None
    return summary


async def build_source_snapshot(
    db: AsyncSession,
    location: Location,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    now = now or datetime.now()
    post_cutoff = now - timedelta(days=SUMMARY_POST_DAYS)
    review_cutoff = now - timedelta(days=SUMMARY_REVIEW_DAYS)

    post_result = await db.execute(
        select(Post)
        .options(joinedload(Post.user))
        .where(
            Post.location_id == location.id,
            Post.school_id == location.school_id,
            Post.status == "published",
            Post.is_deleted == False,
            Post.created_at >= post_cutoff,
            or_(Post.expire_at.is_(None), Post.expire_at > now),
            Post.invalid_count <= Post.valid_count,
        )
        .order_by(Post.created_at.desc())
        .limit(SUMMARY_MAX_POSTS)
    )
    posts = list(post_result.unique().scalars().all())

    review_result = await db.execute(
        select(LocationReview)
        .options(joinedload(LocationReview.user))
        .where(
            LocationReview.location_id == location.id,
            LocationReview.school_id == location.school_id,
            LocationReview.status == "published",
            LocationReview.is_deleted == False,
            LocationReview.created_at >= review_cutoff,
        )
        .order_by(LocationReview.created_at.desc())
        .limit(SUMMARY_MAX_REVIEWS)
    )
    reviews = list(review_result.unique().scalars().all())
    facts = await load_location_facts(db, location.id, location.school_id)

    return {
        "location": {
            "id": location.id,
            "name": location.name,
            "description": location.description,
            "building": location.building,
            "floor": location.floor,
        },
        "facts": [
            {
                "source_type": "fact",
                "source_id": fact.id,
                "fact_key": fact.fact_key,
                "label": fact.label,
                "value": fact.value,
                "updated_at": fact.updated_at.isoformat(),
            }
            for fact in facts
        ],
        "posts": [
            {
                "source_type": "post",
                "source_id": post.id,
                "title": post.title,
                "content": post.content[:1500],
                "created_at": post.created_at.isoformat(),
                "author_id": post.user_id,
                "author_name": None if post.is_anonymous else (post.user.nickname if post.user else None),
                "confirmation_count": post.valid_count,
                "refutation_count": post.invalid_count,
            }
            for post in posts
        ],
        "reviews": [
            {
                "source_type": "review",
                "source_id": review.id,
                "content": review.content or "",
                "score": review.score,
                "created_at": review.created_at.isoformat(),
                "author_id": review.user_id,
                "author_name": None if review.is_anonymous else (review.user.nickname if review.user else None),
            }
            for review in reviews
        ],
    }


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _candidate_sources(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group in ("facts", "posts", "reviews"):
        for item in snapshot[group]:
            result[_source_key(item["source_type"], item["source_id"])] = item
    return result


def _distinct_authors(snapshot: dict[str, Any]) -> set[int]:
    authors: set[int] = set()
    for item in snapshot["posts"] + snapshot["reviews"]:
        if item.get("author_id") is not None:
            authors.add(int(item["author_id"]))
    return authors


def _confidence(snapshot: dict[str, Any], conflicts: list[dict[str, Any]]) -> str:
    if conflicts:
        return "disputed"
    authors = _distinct_authors(snapshot)
    if len(authors) >= 3:
        return "high"
    if len(authors) >= 2:
        return "medium"
    return "insufficient"


def _normalise_output(parsed: Any, snapshot: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(parsed, dict):
        raise ValueError("AI 摘要输出不是对象")
    candidates = _candidate_sources(snapshot)
    claims = parsed.get("claims") or []
    conflicts = parsed.get("conflicts") or []
    valid_claims: list[dict[str, Any]] = []
    all_refs: dict[str, dict[str, Any]] = {}
    for claim in claims:
        refs = claim.get("source_refs") if isinstance(claim, dict) else None
        if not isinstance(refs, list) or not refs:
            continue
        normal_refs = []
        for ref in refs:
            if not isinstance(ref, dict):
                raise ValueError("摘要来源格式错误")
            key = _source_key(str(ref.get("source_type")), int(ref.get("source_id", 0)))
            if key not in candidates:
                raise ValueError("摘要引用了不在输入快照中的来源")
            clean = {"source_type": ref["source_type"], "source_id": int(ref["source_id"])}
            normal_refs.append(clean)
        unique_refs = {(r["source_type"], r["source_id"]) for r in normal_refs}
        dynamic_items = [
            candidates[_source_key(ref["source_type"], ref["source_id"])]
            for ref in normal_refs
            if ref["source_type"] != "fact"
        ]
        dynamic_authors = {
            int(item["author_id"])
            for item in dynamic_items
            if item.get("author_id") is not None
        }
        # 稳定资料可以单条引用；只要结论涉及动态内容，就必须来自两个不同用户。
        if dynamic_items and len(dynamic_authors) < 2:
            continue
        if not dynamic_items and len(unique_refs) < 1:
            continue
        for ref in normal_refs:
            all_refs[_source_key(ref["source_type"], ref["source_id"])] = ref
        valid_claims.append({
            "claim_id": str(claim.get("claim_id") or f"claim-{len(valid_claims) + 1}"),
            "text": str(claim.get("text") or "").strip()[:300],
            "confidence_level": "pending",
            "source_refs": normal_refs,
        })
    clean_conflicts: list[dict[str, Any]] = []
    for conflict in conflicts:
        refs = conflict.get("source_refs") if isinstance(conflict, dict) else None
        if not isinstance(refs, list) or len(refs) < 2:
            continue
        normal_refs = []
        for ref in refs:
            key = _source_key(str(ref.get("source_type")), int(ref.get("source_id", 0)))
            if key not in candidates:
                raise ValueError("摘要冲突引用了不在输入快照中的来源")
            clean = {"source_type": ref["source_type"], "source_id": int(ref["source_id"])}
            normal_refs.append(clean)
            all_refs[key] = clean
        clean_conflicts.append({"text": str(conflict.get("text") or "").strip()[:300], "source_refs": normal_refs})
    confidence = _confidence(snapshot, clean_conflicts)
    for claim in valid_claims:
        claim["confidence_level"] = confidence
    if not valid_claims and not clean_conflicts:
        confidence = "insufficient"
    summary_text = (parsed.get("summary_text") or "").strip()[:1200] or None
    if summary_text and not valid_claims and not clean_conflicts:
        summary_text = None
    return {
        "summary_text": summary_text,
        "claims": valid_claims,
        "conflicts": clean_conflicts,
        "confidence_level": confidence,
        "source_refs": list(all_refs.values()),
    }, list(all_refs.values())


def _build_prompt(snapshot: dict[str, Any]) -> str:
    return (
        "你是校园信息整理助手。只允许根据给定来源整理地点近期动态，不能补写来源中没有的事实。"
        "稳定资料可以作为背景，但任何动态结论都必须引用至少两个不同用户的来源。"
        "如果来源相互矛盾，请放入 conflicts，不能自行选择。输出严格符合 JSON Schema。\n\n"
        + json.dumps(snapshot, ensure_ascii=False, indent=2)
    )


async def generate_location_summary(
    db: AsyncSession,
    location_id: int,
    tenant: TenantContext,
    user: Optional[User] = None,
    provider: Optional[AIProvider] = None,
    trace_id: Optional[str] = None,
) -> Optional[LocationSummaryVersion]:
    location = await _load_location(db, location_id, tenant)
    snapshot = await build_source_snapshot(db, location)
    source_hash = snapshot_hash(snapshot)
    dynamic_count = len(snapshot["posts"]) + len(snapshot["reviews"])
    if dynamic_count < 2 or len(_distinct_authors(snapshot)) < 2:
        location.summary_dirty_at = None
        await db.commit()
        return None

    duplicate = await db.scalar(
        select(LocationSummaryVersion).where(
            LocationSummaryVersion.location_id == location.id,
            LocationSummaryVersion.school_id == location.school_id,
            LocationSummaryVersion.source_hash == source_hash,
            LocationSummaryVersion.status == "pending_review",
        )
    )
    if duplicate is not None:
        location.summary_dirty_at = None
        await db.commit()
        return duplicate

    outcome = await invoke_ai(
        prompt=_build_prompt(snapshot),
        schema=LOCATION_SUMMARY_SCHEMA,
        scene=SUMMARY_SCENE,
        tenant=tenant,
        db=db,
        user=user,
        options=AIInvokeOptions(temperature=0.1, max_tokens=1200),
        trace_id=trace_id,
        provider=provider,
    )
    if outcome.fallback or outcome.response is None:
        logger.warning("location summary AI fallback location_id=%s reason=%s", location.id, outcome.fallback_reason)
        return None

    try:
        normalised, refs = _normalise_output(outcome.response.parsed, snapshot)
    except (TypeError, ValueError, KeyError) as exc:
        logger.warning("location summary output rejected location_id=%s error=%s", location.id, exc)
        return None

    latest_version = await db.scalar(
        select(func.coalesce(func.max(LocationSummaryVersion.version), 0)).where(
            LocationSummaryVersion.location_id == location.id,
            LocationSummaryVersion.school_id == location.school_id,
        )
    )
    version = int(latest_version or 0) + 1
    now = datetime.now()
    summary = LocationSummaryVersion(
        location_id=location.id,
        school_id=location.school_id,
        version=version,
        status="pending_review",
        summary_text=normalised["summary_text"],
        confidence_level=normalised["confidence_level"],
        claims_json=normalised["claims"],
        conflicts_json=normalised["conflicts"],
        source_refs_json=refs,
        source_hash=source_hash,
        source_count=len(refs),
        generated_at=now,
        stale_at=now + timedelta(days=1),
        ai_log_id=outcome.log_id,
        created_at=now,
    )
    db.add(summary)
    location.summary_dirty_at = None
    await db.commit()
    await db.refresh(summary)
    return summary


async def approve_location_summary(
    db: AsyncSession, summary_id: int, tenant: TenantContext, reviewer: User, reason: Optional[str] = None
) -> LocationSummaryVersion:
    summary = await db.get(LocationSummaryVersion, summary_id)
    if summary is None:
        raise NotFoundException(detail="摘要版本不存在")
    check_resource_in_tenant(summary.school_id, tenant)
    if summary.status != "pending_review":
        raise BadRequestException(detail="该摘要版本不在待审核状态")
    location = await _load_location(db, summary.location_id, tenant)
    if location.current_summary_id:
        old = await db.get(LocationSummaryVersion, location.current_summary_id)
        if old and old.status == "approved":
            old.status = "archived"
    summary.status = "approved"
    summary.reviewer_id = reviewer.id
    summary.review_reason = reason
    summary.reviewed_at = datetime.now()
    location.current_summary_id = summary.id
    location.summary_dirty_at = None
    await db.commit()
    await db.refresh(summary)
    return summary


async def reject_location_summary(
    db: AsyncSession, summary_id: int, tenant: TenantContext, reviewer: User, reason: Optional[str] = None
) -> LocationSummaryVersion:
    summary = await db.get(LocationSummaryVersion, summary_id)
    if summary is None:
        raise NotFoundException(detail="摘要版本不存在")
    check_resource_in_tenant(summary.school_id, tenant)
    if summary.status != "pending_review":
        raise BadRequestException(detail="该摘要版本不在待审核状态")
    summary.status = "rejected"
    summary.reviewer_id = reviewer.id
    summary.review_reason = reason
    summary.reviewed_at = datetime.now()
    await db.commit()
    await db.refresh(summary)
    return summary


async def load_summary_sources(
    db: AsyncSession, summary: LocationSummaryVersion, tenant: TenantContext
) -> list[dict[str, Any]]:
    check_resource_in_tenant(summary.school_id, tenant)
    refs = summary.source_refs_json or []
    source_map = {_source_key(item["source_type"], int(item["source_id"])): item for item in refs}
    result: list[dict[str, Any]] = []
    for key, ref in source_map.items():
        source_type = ref["source_type"]
        source_id = int(ref["source_id"])
        if source_type == "post":
            post = await db.scalar(
                select(Post).options(joinedload(Post.user)).where(
                    Post.id == source_id,
                    Post.school_id == summary.school_id,
                    Post.location_id == summary.location_id,
                    Post.is_deleted == False,
                )
            )
            if post is None:
                continue
            result.append({
                "source_type": "post", "source_id": post.id, "title": post.title,
                "snippet": post.content[:240], "created_at": post.created_at,
                "author_name": None if post.is_anonymous else (post.user.nickname if post.user else None),
                "confirmation_count": post.valid_count, "refutation_count": post.invalid_count,
            })
        elif source_type == "review":
            review = await db.scalar(
                select(LocationReview).options(joinedload(LocationReview.user)).where(
                    LocationReview.id == source_id,
                    LocationReview.school_id == summary.school_id,
                    LocationReview.location_id == summary.location_id,
                    LocationReview.is_deleted == False,
                )
            )
            if review is None:
                continue
            result.append({
                "source_type": "review", "source_id": review.id,
                "snippet": review.content, "created_at": review.created_at,
                "author_name": None if review.is_anonymous else (review.user.nickname if review.user else None),
                "score": review.score,
            })
        elif source_type == "fact":
            fact = await db.scalar(
                select(LocationFact).where(
                    LocationFact.id == source_id,
                    LocationFact.school_id == summary.school_id,
                    LocationFact.location_id == summary.location_id,
                    LocationFact.is_active == True,
                )
            )
            if fact is not None:
                result.append({
                    "source_type": "fact", "source_id": fact.id,
                    "title": fact.label, "snippet": fact.value, "updated_at": fact.updated_at,
                })
    return result
