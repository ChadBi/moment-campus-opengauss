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

from app.core.exceptions import NotFoundException
from app.core.tenant import TenantContext, get_tenant_context
from app.database import get_db
from app.dependencies import get_current_user
from app.models.school import School
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


class JoinSchoolResponse(BaseModel):
    """加入学校响应"""
    membership: MembershipResponse
    already_member: bool = Field(
        False, description="若用户已是该校 active 成员，返回 true 并幂等返回原 membership"
    )
    switched: bool = Field(
        False, description="UC-01: 是否为切换学校（原 active 成员关系已改指向新校）"
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
    summary="加入学校（UC-01 起：普通用户为切换语义）",
)
async def join_school(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """加入/切换学校。

    UC-01 严格一对一绑定（普通用户）：
    1. 学校必须存在且 is_active=true，否则 404
    2. 用户已有 active membership 且目标校相同：幂等返回 already_member=true
    3. 用户已有 active membership 且目标校不同：执行**切换**——
       成员关系改指向新校、重置校园认证、匿名化原校内容（switched=true）
    4. 用户无 active membership：创建（is_default=true）

    super_admin 豁免一对一（可保留多校成员关系，供平台跨校管理）。
    """
    # 1. 校验学校存在且启用
    school = (
        await db.execute(select(School).where(School.code == code))
    ).scalar_one_or_none()
    if school is None or not school.is_active:
        raise NotFoundException(detail="学校不存在或已停用")

    is_super_admin = current_user.role == "super_admin"

    # 2. 查找用户唯一 active membership（super_admin 除外，兼容多校）
    if is_super_admin:
        existing = (
            await db.execute(
                select(SchoolMembership)
                .options(selectinload(SchoolMembership.school))
                .where(
                    SchoolMembership.user_id == current_user.id,
                    SchoolMembership.school_id == school.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.status == "active":
                return JoinSchoolResponse(
                    membership=_to_membership_response(existing),
                    already_member=True,
                )
            existing.status = "active"
            existing.joined_at = datetime.now()
            existing.updated_at = datetime.now()
            await db.commit()
            await db.refresh(existing, attribute_names=["school"])
            return JoinSchoolResponse(
                membership=_to_membership_response(existing),
                already_member=False,
            )
        # super_admin：创建新 membership（豁免一对一）
        membership = SchoolMembership(
            user_id=current_user.id,
            school_id=school.id,
            role="member",
            status="active",
            is_default=False,
            joined_at=datetime.now(),
        )
        db.add(membership)
        await db.commit()
        await db.refresh(membership, attribute_names=["school"])
        return JoinSchoolResponse(
            membership=_to_membership_response(membership),
            already_member=False,
        )

    # 3. 普通用户：一对一逻辑
    active = (
        await db.execute(
            select(SchoolMembership)
            .options(selectinload(SchoolMembership.school))
            .where(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.status == "active",
            )
        )
    ).scalar_one_or_none()

    if active is not None:
        if active.school_id == school.id:
            # 幂等返回
            return JoinSchoolResponse(
                membership=_to_membership_response(active),
                already_member=True,
            )
        # 切换学校（重置认证 + 匿名化原校内容）
        from app.services.school_switch import switch_school
        switched = await switch_school(db, current_user, school.id)
        return JoinSchoolResponse(
            membership=_to_membership_response(switched),
            already_member=False,
            switched=True,
        )

    # 4. 无 active membership：同校存在 invited/suspended 则升级，否则新建并设为默认
    pending = (
        await db.execute(
            select(SchoolMembership)
            .options(selectinload(SchoolMembership.school))
            .where(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.school_id == school.id,
                SchoolMembership.status.in_(["invited", "suspended"]),
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        pending.status = "active"
        pending.is_default = True
        pending.joined_at = datetime.now()
        pending.updated_at = datetime.now()
        current_user.school_id = school.id
        current_user.updated_at = datetime.now()
        await db.commit()
        await db.refresh(pending, attribute_names=["school"])
        return JoinSchoolResponse(
            membership=_to_membership_response(pending),
            already_member=False,
        )

    membership = SchoolMembership(
        user_id=current_user.id,
        school_id=school.id,
        role="member",
        status="active",
        is_default=True,
        joined_at=datetime.now(),
    )
    db.add(membership)
    current_user.school_id = school.id
    current_user.updated_at = datetime.now()
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
    summary="设置默认学校（UC-01 起：仅一致性校验）",
)
async def set_default_school(
    body: SetDefaultSchoolRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设置默认学校（UC-01 严格一对一后语义退化）。

    普通用户至多一条 active membership，且始终是默认学校；本端点仅校验：
    1. 目标学校与用户唯一 active membership 一致（或为 super_admin 的多校之一）
    2. 同步 user.school_id 保持一致性（兼容旧客户端）

    super_admin 豁免一对一：仍可切换默认学校（保持多校管理能力）。
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

    if current_user.role != "super_admin":
        # 普通用户：唯一 active membership 必须就是目标学校，否则拒绝（一对一约束）
        active_count = (
            await db.scalar(
                select(SchoolMembership)
                .where(
                    SchoolMembership.user_id == current_user.id,
                    SchoolMembership.status == "active",
                )
            )
        )
        if active_count is None or active_count.school_id != body.school_id:
            raise NotFoundException(detail="切换学校请使用「加入学校」接口（一对一绑定）")
    else:
        # super_admin：可切换默认
        await db.execute(
            update(SchoolMembership)
            .where(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.id != target.id,
            )
            .values(is_default=False, updated_at=datetime.now())
        )
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
