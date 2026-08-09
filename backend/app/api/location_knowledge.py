"""地点稳定资料提议与 AI 摘要审核接口。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.permissions import Role, require_campus_verified, require_role
from app.core.tenant import TenantContext, check_resource_in_tenant, get_tenant_context
from app.database import get_db
from app.dependencies import get_current_user
from app.models.admin_operation_log import AdminOperationLog
from app.models.location import Location
from app.models.location_fact import LocationFact, LocationFactProposal
from app.models.location_summary import LocationSummaryVersion
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.location_knowledge import (
    LocationFactProposalCreate,
    LocationFactProposalResponse,
    LocationFactResponse,
    LocationProposalReview,
    LocationSummaryResponse,
    LocationSummaryReview,
)
from app.services.location_summary import (
    approve_location_summary,
    load_current_summary,
    load_summary_sources,
    mark_location_summary_dirty,
    reject_location_summary,
    summary_response,
)

router = APIRouter(tags=["地点知识"])
AdminDep = Depends(require_role(Role.ADMIN))


async def _get_location(db: AsyncSession, location_id: int, tenant: TenantContext) -> Location:
    location = await db.scalar(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    if location is None:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(location.school_id, tenant)
    return location


@router.post(
    "/locations/{location_id}/fact-proposals",
    response_model=LocationFactProposalResponse,
    status_code=201,
    summary="提交地点稳定资料提议",
    dependencies=[Depends(require_campus_verified())],
)
async def create_location_fact_proposal(
    location_id: int,
    data: LocationFactProposalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    location = await _get_location(db, location_id, tenant)
    pending = await db.scalar(
        select(LocationFactProposal).where(
            LocationFactProposal.location_id == location.id,
            LocationFactProposal.school_id == tenant.school_id,
            LocationFactProposal.proposer_id == current_user.id,
            LocationFactProposal.status == "pending",
        )
    )
    if pending is not None:
        raise ConflictException(detail="你已提交过该地点的待审核资料提议")
    proposal = LocationFactProposal(
        location_id=location.id,
        school_id=tenant.school_id,
        proposer_id=current_user.id,
        changes_json=data.model_dump(mode="json"),
        reason=data.reason,
        status="pending",
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.get(
    "/me/location-fact-proposals",
    response_model=PaginatedResponse[LocationFactProposalResponse],
    summary="查看我的地点资料提议",
)
async def list_my_location_fact_proposals(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    filters = [
        LocationFactProposal.proposer_id == current_user.id,
        LocationFactProposal.school_id == tenant.school_id,
    ]
    if status:
        filters.append(LocationFactProposal.status == status)
    total = await db.scalar(select(func.count(LocationFactProposal.id)).where(*filters)) or 0
    result = await db.execute(
        select(LocationFactProposal)
        .where(*filters)
        .order_by(LocationFactProposal.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return PaginatedResponse.create(list(result.scalars().all()), page, page_size, int(total))


@router.get(
    "/admin/location-fact-proposals",
    summary="地点资料提议审核队列",
    dependencies=[AdminDep],
)
async def list_location_fact_proposals(
    status: str = Query(default="pending"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    filters = [
        LocationFactProposal.school_id == tenant.school_id,
        LocationFactProposal.status == status,
    ]
    total = await db.scalar(select(func.count(LocationFactProposal.id)).where(*filters)) or 0
    result = await db.execute(
        select(LocationFactProposal, Location.name, User.nickname)
        .join(Location, Location.id == LocationFactProposal.location_id)
        .join(User, User.id == LocationFactProposal.proposer_id)
        .where(*filters)
        .order_by(LocationFactProposal.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for proposal, loc_name, proposer_name in result.all():
        item = {
            "id": proposal.id,
            "location_id": proposal.location_id,
            "location_name": loc_name,
            "school_id": proposal.school_id,
            "proposer_id": proposal.proposer_id,
            "proposer_name": proposer_name,
            "changes_json": proposal.changes_json,
            "reason": proposal.reason,
            "status": proposal.status,
            "reviewer_id": proposal.reviewer_id,
            "review_reason": proposal.review_reason,
            "reviewed_at": proposal.reviewed_at,
            "created_at": proposal.created_at,
            "updated_at": proposal.updated_at,
        }
        items.append(item)
    return PaginatedResponse.create(items, page, page_size, int(total))


@router.post(
    "/admin/location-fact-proposals/{proposal_id}/approve",
    response_model=LocationFactProposalResponse,
    summary="批准地点资料提议",
    dependencies=[AdminDep],
)
async def approve_location_fact_proposal(
    proposal_id: int,
    data: LocationProposalReview | None = None,
    reviewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    proposal = await db.get(LocationFactProposal, proposal_id)
    if proposal is None:
        raise NotFoundException(detail="资料提议不存在")
    check_resource_in_tenant(proposal.school_id, tenant)
    if proposal.status != "pending":
        raise BadRequestException(detail="该提议不在待审核状态")
    location = await _get_location(db, proposal.location_id, tenant)
    changes = proposal.changes_json or {}
    for raw in changes.get("upserts", []):
        key = raw.get("fact_key")
        fact = await db.scalar(
            select(LocationFact).where(
                LocationFact.location_id == location.id,
                LocationFact.school_id == tenant.school_id,
                LocationFact.fact_key == key,
                LocationFact.is_active == True,
            )
        )
        values = {
            "label": raw.get("label") or key,
            "value": raw.get("value", ""),
            "sort_order": raw.get("sort_order", 0),
            "source_note": raw.get("source_note"),
            "approved_by": reviewer.id,
            "approved_at": datetime.now(),
            "is_active": True,
        }
        if fact is None:
            db.add(LocationFact(location_id=location.id, school_id=tenant.school_id, fact_key=key, **values))
        else:
            for name, value in values.items():
                setattr(fact, name, value)
    if changes.get("remove_keys"):
        await db.execute(
            LocationFact.__table__.update()
            .where(
                LocationFact.location_id == location.id,
                LocationFact.school_id == tenant.school_id,
                LocationFact.fact_key.in_(changes["remove_keys"]),
                LocationFact.is_active == True,
            )
            .values(is_active=False, approved_by=reviewer.id, approved_at=datetime.now())
        )
    proposal.status = "approved"
    proposal.reviewer_id = reviewer.id
    proposal.review_reason = data.reason if data else None
    proposal.reviewed_at = datetime.now()
    await mark_location_summary_dirty(db, location.id)
    db.add(AdminOperationLog(
        admin_id=reviewer.id,
        action="approve_location_fact_proposal",
        target_type="location_fact_proposal",
        target_id=proposal.id,
        detail=json.dumps({"location_id": location.id}, ensure_ascii=False),
    ))
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.post(
    "/admin/location-fact-proposals/{proposal_id}/reject",
    response_model=LocationFactProposalResponse,
    summary="驳回地点资料提议",
    dependencies=[AdminDep],
)
async def reject_location_fact_proposal(
    proposal_id: int,
    data: LocationProposalReview | None = None,
    reviewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    proposal = await db.get(LocationFactProposal, proposal_id)
    if proposal is None:
        raise NotFoundException(detail="资料提议不存在")
    check_resource_in_tenant(proposal.school_id, tenant)
    if proposal.status != "pending":
        raise BadRequestException(detail="该提议不在待审核状态")
    proposal.status = "rejected"
    proposal.reviewer_id = reviewer.id
    proposal.review_reason = data.reason if data else None
    proposal.reviewed_at = datetime.now()
    db.add(AdminOperationLog(
        admin_id=reviewer.id,
        action="reject_location_fact_proposal",
        target_type="location_fact_proposal",
        target_id=proposal.id,
        detail=json.dumps({"location_id": proposal.location_id}, ensure_ascii=False),
    ))
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.get(
    "/locations/{location_id}/summary",
    response_model=LocationSummaryResponse,
    summary="查看地点 AI 摘要与来源",
)
async def get_location_summary(
    location_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    location = await _get_location(db, location_id, tenant)
    summary = await load_current_summary(db, location)
    sources = await load_summary_sources(db, summary, tenant) if summary else []
    return summary_response(summary, sources)


@router.get(
    "/admin/location-summaries",
    summary="地点 AI 摘要审核队列",
    dependencies=[AdminDep],
)
async def list_location_summaries(
    status: str = Query(default="pending_review"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    query = (
        select(LocationSummaryVersion, Location.name)
        .join(Location, Location.id == LocationSummaryVersion.location_id)
        .where(
            LocationSummaryVersion.school_id == tenant.school_id,
            LocationSummaryVersion.status == status,
            Location.is_deleted == False,
        )
        .order_by(LocationSummaryVersion.generated_at.asc())
    )
    count_query = select(func.count(LocationSummaryVersion.id)).where(
        LocationSummaryVersion.school_id == tenant.school_id,
        LocationSummaryVersion.status == status,
    )
    total = await db.scalar(count_query) or 0
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()
    items = []
    for summary, name in rows:
        items.append({
            "id": summary.id,
            "location_id": summary.location_id,
            "location_name": name,
            "version": summary.version,
            "status": summary.status,
            "summary_text": summary.summary_text,
            "confidence_level": summary.confidence_level,
            "claims": summary.claims_json or [],
            "conflicts": summary.conflicts_json or [],
            "source_count": summary.source_count,
            "generated_at": summary.generated_at,
            "stale_at": summary.stale_at,
        })
    return PaginatedResponse.create(items, page, page_size, int(total))


@router.post(
    "/admin/location-summaries/{summary_id}/approve",
    response_model=LocationSummaryResponse,
    summary="批准地点 AI 摘要",
    dependencies=[AdminDep],
)
async def approve_location_summary_endpoint(
    summary_id: int,
    data: LocationSummaryReview | None = None,
    reviewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    summary = await approve_location_summary(db, summary_id, tenant, reviewer, data.reason if data else None)
    sources = await load_summary_sources(db, summary, tenant)
    return summary_response(summary, sources)


@router.post(
    "/admin/location-summaries/{summary_id}/reject",
    response_model=LocationSummaryResponse,
    summary="驳回地点 AI 摘要",
    dependencies=[AdminDep],
)
async def reject_location_summary_endpoint(
    summary_id: int,
    data: LocationSummaryReview | None = None,
    reviewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    summary = await reject_location_summary(db, summary_id, tenant, reviewer, data.reason if data else None)
    sources = await load_summary_sources(db, summary, tenant)
    return summary_response(summary, sources)


@router.post(
    "/admin/locations/{location_id}/summary/refresh",
    summary="标记地点 AI 摘要刷新",
    dependencies=[AdminDep],
)
async def refresh_location_summary(
    location_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    location = await _get_location(db, location_id, tenant)
    await mark_location_summary_dirty(db, location.id)
    await db.commit()
    return {"message": "已加入摘要刷新队列", "location_id": location.id}

