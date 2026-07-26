"""TEN-03.1: 学校目录、加入、默认学校、切换 API

公开端点：
    GET  /api/v1/schools                公开学校目录（仅 is_active=true）
    GET  /api/v1/schools/current        当前学校（基于 TenantContext）

登录用户端点：
    GET  /api/v1/me/memberships         当前用户加入的学校列表（含角色/状态/是否默认）
    POST /api/v1/schools/{code}/join    加入学校（创建 active membership；幂等）
    PUT  /api/v1/me/default-school      设置默认学校

设计要点：
    - 学校目录公开访问，无需 Token 或 X-School-Code（游客也可选择学校）
    - /schools/current 复用 TenantContext，需带 X-School-Code 头
    - /me/* 需登录；POST /join 幂等：已有 active membership 直接返回，不报错
    - 设置默认学校时取消其它 membership 的 is_default（每用户仅一个默认）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException, NotFoundException, ConflictException,
)
from app.core.tenant import TenantContext, get_tenant_context
from app.database import get_db
from app.dependencies import get_current_user
from app.models.school import School
from app.models.school_invitation import SchoolInvitation
from app.models.school_membership import SchoolMembership
from app.models.user import User


# 两个路由前缀：/schools 与 /me，统一在一个 router 文件内通过两条 router 暴露
schools_router = APIRouter(prefix="/schools", tags=["学校"])
me_router = APIRouter(prefix="/me", tags=["用户-学校关系"])


# ============================================================
# Schemas
# ============================================================
class SchoolBrief(BaseModel):
    """学校简要信息（公开目录用）"""
    id: int
    code: str
    name: str
    logo_url: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    map_zoom: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CurrentSchoolResponse(BaseModel):
    """当前学校详情"""
    id: int
    code: str
    name: str
    logo_url: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    map_zoom: Optional[int] = None
    is_active: bool
    # ADM-02.1: 品牌字段（来自 school_settings 一对一）
    site_name: Optional[str] = Field(
        None, description="站点名称（来自 school_settings，跨浏览器生效）"
    )
    description: Optional[str] = Field(
        None, description="站点说明（来自 school_settings）"
    )
    brand_color: Optional[str] = Field(
        None, description="品牌色（来自 school_settings）"
    )


class MembershipSchoolBrief(BaseModel):
    """membership 内嵌的学校简要"""
    id: int
    code: str
    name: str
    logo_url: Optional[str] = None


class MembershipResponse(BaseModel):
    """用户在某学校的成员关系"""
    id: int
    school_id: int
    role: str
    status: str
    is_default: bool
    joined_at: datetime
    school: MembershipSchoolBrief

    model_config = ConfigDict(from_attributes=True)


class JoinSchoolRequest(BaseModel):
    """加入学校请求（可带邀请码）"""
    invitation_code: Optional[str] = Field(
        None, description="邀请码（可选，若提供需匹配该校未使用邀请）"
    )


class JoinSchoolResponse(BaseModel):
    """加入学校响应"""
    membership: MembershipResponse
    already_member: bool = Field(
        False, description="若用户已是该校 active 成员，返回 true 并幂等返回原 membership"
    )


class SetDefaultSchoolRequest(BaseModel):
    """设置默认学校请求"""
    school_id: int = Field(..., description="目标学校 ID（用户须为该校 active 成员）")


class SetDefaultSchoolResponse(BaseModel):
    """设置默认学校响应"""
    default_school_id: int
    membership: MembershipResponse


# ============================================================
# 公开学校目录
# ============================================================
@schools_router.get(
    "",
    response_model=list[SchoolBrief],
    summary="公开学校目录",
)
async def list_schools(
    db: AsyncSession = Depends(get_db),
):
    """列出全部 is_active=true 的学校（公开接口，无需登录、无需 X-School-Code）。

    用于：
    - 游客首次访问选择学校
    - 登录用户加入新学校前的目录浏览
    - 学校切换组件的下拉数据源
    """
    result = await db.execute(
        select(School)
        .where(School.is_active == True)  # noqa: E712
        .order_by(School.id.asc())
    )
    return result.scalars().all()


@schools_router.get(
    "/current",
    response_model=CurrentSchoolResponse,
    summary="当前学校（基于 TenantContext）",
)
async def get_current_school(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """返回当前请求所属学校详情。

    解析规则与 TenantContext 一致：
    - 游客：必须传 X-School-Code 或 ?school=
    - 登录用户：未传则取 user.school_id

    ADM-02.1: 同时返回 school_settings 中的品牌字段
    （site_name / description / brand_color），供前端 header/logo 等公开区域使用。
    """
    result = await db.execute(
        select(School).where(School.id == tenant.school_id)
    )
    school = result.scalar_one_or_none()
    if school is None:
        raise NotFoundException(detail="学校不存在")

    # ADM-02.1: 读取品牌字段（无 settings 行时返回 None，不影响公开访问）
    from app.models.school_settings import SchoolSettings
    settings = await db.scalar(
        select(SchoolSettings).where(SchoolSettings.school_id == school.id)
    )
    return CurrentSchoolResponse(
        id=school.id,
        code=school.code,
        name=school.name,
        logo_url=school.logo_url,
        province=school.province,
        city=school.city,
        address=school.address,
        center_lat=school.center_lat,
        center_lng=school.center_lng,
        map_zoom=school.map_zoom,
        is_active=school.is_active,
        site_name=settings.site_name if settings else None,
        description=settings.description if settings else None,
        brand_color=settings.brand_color if settings else None,
    )


# ============================================================
# /me/memberships：当前用户加入的学校列表
# ============================================================
@me_router.get(
    "/memberships",
    response_model=list[MembershipResponse],
    summary="当前用户加入的学校列表",
)
async def list_my_memberships(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户全部学校成员关系（含角色/状态/是否默认）。

    - 包含 active/invited/suspended 全部状态
    - 嵌套返回 school 简要信息
    - 按 is_default DESC, joined_at DESC 排序（默认校在前）
    """
    result = await db.execute(
        select(SchoolMembership)
        .options(selectinload(SchoolMembership.school))
        .where(SchoolMembership.user_id == current_user.id)
        .order_by(
            SchoolMembership.is_default.desc(),
            SchoolMembership.joined_at.desc(),
        )
    )
    return result.scalars().all()


# ============================================================
# POST /schools/{code}/join：加入学校
# ============================================================
@schools_router.post(
    "/{code}/join",
    response_model=JoinSchoolResponse,
    summary="加入学校（创建 active membership，幂等）",
)
async def join_school(
    code: str,
    body: JoinSchoolRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """加入指定学校。

    业务规则：
    1. 学校必须存在且 is_active=true，否则 404
    2. 若用户已是该校 active 成员：幂等返回 already_member=true，不修改
    3. 若用户在该校已有 invited/suspended 状态的 membership：升级为 active
    4. 若提供 invitation_code：必须匹配该校未使用邀请；匹配后标记为 accepted
    5. 若用户尚无任何默认学校，则将本次加入设为默认
    6. 若用户已有其它默认学校，则本次加入 is_default=false（不抢占默认）
    """
    # 1. 校验学校存在且启用
    school = (
        await db.execute(select(School).where(School.code == code))
    ).scalar_one_or_none()
    if school is None or not school.is_active:
        raise NotFoundException(detail="学校不存在或已停用")

    # 2. 校验邀请码（若提供）
    invitation: Optional[SchoolInvitation] = None
    if body.invitation_code:
        invitation = (
            await db.execute(
                select(SchoolInvitation).where(
                    SchoolInvitation.invitation_code == body.invitation_code,
                    SchoolInvitation.school_id == school.id,
                )
            )
        ).scalar_one_or_none()
        if invitation is None:
            raise BadRequestException(detail="邀请码无效")
        # 邀请码校验邮箱匹配
        if invitation.email and invitation.email != current_user.email:
            raise BadRequestException(detail="邀请码不适用于当前账号")
        if invitation.status == "accepted":
            raise ConflictException(detail="邀请码已被使用")

    # 3. 查找已有 membership
    existing = (
        await db.execute(
            select(SchoolMembership).where(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.school_id == school.id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.status == "active":
            # 幂等返回
            await db.refresh(existing, attribute_names=["school"])
            return JoinSchoolResponse(
                membership=_to_membership_response(existing),
                already_member=True,
            )
        # invited/suspended → 升级为 active
        existing.status = "active"
        existing.joined_at = datetime.now()
        existing.updated_at = datetime.now()
        await db.flush()
        # 标记邀请已接受（若提供）
        if invitation is not None:
            invitation.status = "accepted"
            invitation.accepted_at = datetime.now()
        await db.commit()
        await db.refresh(existing, attribute_names=["school"])
        return JoinSchoolResponse(
            membership=_to_membership_response(existing),
            already_member=False,
        )

    # 4. 新建 membership
    # 决定是否设为默认：用户当前无任何默认学校时设为默认
    default_count = (
        await db.execute(
            select(SchoolMembership).where(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.is_default == True,  # noqa: E712
            )
        )
    ).first()
    is_default = default_count is None

    # 邀请码指定角色（admin 邀请 → admin 角色）；否则 member
    role = "member"
    if invitation is not None and invitation.role == "admin":
        role = "admin"

    membership = SchoolMembership(
        user_id=current_user.id,
        school_id=school.id,
        role=role,
        status="active",
        is_default=is_default,
        joined_at=datetime.now(),
        invited_by=invitation.invited_by if invitation else None,
    )
    db.add(membership)
    await db.flush()

    if invitation is not None:
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now()

    await db.commit()
    await db.refresh(membership, attribute_names=["school"])
    return JoinSchoolResponse(
        membership=_to_membership_response(membership),
        already_member=False,
    )


# ============================================================
# PUT /me/default-school：设置默认学校
# ============================================================
@me_router.put(
    "/default-school",
    response_model=SetDefaultSchoolResponse,
    summary="设置默认学校",
)
async def set_default_school(
    body: SetDefaultSchoolRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设置默认学校。

    规则：
    1. 用户须为该校 active 成员，否则 404
    2. 取消用户其它 membership 的 is_default（每用户仅一个默认）
    3. 将目标 membership 设为 is_default=true
    4. 同步更新 user.school_id（兼容旧逻辑：未指定 X-School-Code 时回退到此）
    """
    target = (
        await db.execute(
            select(SchoolMembership)
            .options(selectinload(SchoolMembership.school))
            .where(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.school_id == body.school_id,
            )
        )
    ).scalar_one_or_none()

    if target is None or target.status != "active":
        raise NotFoundException(detail="未加入该校或成员关系不可用")

    # 取消其它默认
    await db.execute(
        update(SchoolMembership)
        .where(
            SchoolMembership.user_id == current_user.id,
            SchoolMembership.id != target.id,
        )
        .values(is_default=False, updated_at=datetime.now())
    )

    # 设目标为默认
    target.is_default = True
    target.updated_at = datetime.now()
    # 同步 user.school_id
    current_user.school_id = body.school_id
    current_user.updated_at = datetime.now()

    await db.commit()
    await db.refresh(target, attribute_names=["school"])

    return SetDefaultSchoolResponse(
        default_school_id=body.school_id,
        membership=_to_membership_response(target),
    )


# ============================================================
# 内部工具
# ============================================================
def _to_membership_response(m: SchoolMembership) -> MembershipResponse:
    """将 SchoolMembership ORM 对象转为响应模型（school 关系需已加载）"""
    return MembershipResponse(
        id=m.id,
        school_id=m.school_id,
        role=m.role,
        status=m.status,
        is_default=m.is_default,
        joined_at=m.joined_at,
        school=MembershipSchoolBrief(
            id=m.school.id,
            code=m.school.code,
            name=m.school.name,
            logo_url=m.school.logo_url,
        ),
    )
