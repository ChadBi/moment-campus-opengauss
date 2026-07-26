"""TEN-02.1 + TEN-02.2: 租户上下文与有效角色

核心概念：
    TenantContext 是单次请求所属学校 + 当前用户 + 有效角色的不可变快照。
    所有按租户过滤的查询都以 tenant.school_id 为准；写请求忽略 body 里的 school_id，
    强制使用 TenantContext 解析得到的学校。

解析优先级（spec TEN-02.1）：
    1. 显式传入的 X-School-Code 头或 ?school= query 参数
    2. 登录用户的默认学校（user.school_id 回查 schools 表确认）
    游客：必须显式提供 school code，否则 404（不泄露学校列表）

权限规则（spec TEN-02.2）：
    - super_admin：跨校操作仍需显式传 school code，但跳过 membership 校验
    - 普通登录用户：在目标学校必须有 active membership（兼容旧用户：user.school_id 匹配也可）
    - 资源级校验：resource.school_id != tenant.school_id → 404（不返回 403 以免泄露存在性）
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_optional
from app.core.exceptions import NotFoundException
from app.core.permissions import Role, is_super_admin
from app.models.user import User
from app.models.school import School
from app.models.school_membership import SchoolMembership


# ============================================================
# TEN-02.1: TenantContext
# ============================================================
@dataclass(frozen=True)
class TenantContext:
    """租户上下文：当前请求所属学校 + 当前用户 + 有效角色

    一次请求中所有按租户过滤的查询都使用 tenant.school_id；
    写请求忽略载荷里的 school_id，强制使用本上下文解析得到的 school_id。
    """
    school_id: int
    school_code: str
    user: Optional[User]
    effective_role: str  # super_admin / admin / user / guest
    is_guest: bool
    membership: Optional[SchoolMembership] = None

    @property
    def is_admin_in_tenant(self) -> bool:
        """当前租户内是否为管理员（admin/super_admin）"""
        return self.effective_role in (Role.ADMIN, Role.SUPER_ADMIN)

    @property
    def is_super_admin(self) -> bool:
        """是否为平台超级管理员（可跨校）"""
        return self.effective_role == Role.SUPER_ADMIN


def _resolve_school_code(
    x_school_code: Optional[str],
    school_query: Optional[str],
) -> Optional[str]:
    """从 header / query 解析学校 code（header 优先）"""
    if x_school_code:
        code = x_school_code.strip()
        return code or None
    if school_query:
        code = school_query.strip()
        return code or None
    return None


async def _load_school_by_code(db: AsyncSession, code: str) -> Optional[School]:
    result = await db.execute(select(School).where(School.code == code))
    return result.scalar_one_or_none()


async def _load_school_by_id(db: AsyncSession, school_id: int) -> Optional[School]:
    result = await db.execute(select(School).where(School.id == school_id))
    return result.scalar_one_or_none()


async def _load_membership(
    db: AsyncSession, user_id: int, school_id: int
) -> Optional[SchoolMembership]:
    result = await db.execute(
        select(SchoolMembership).where(
            SchoolMembership.user_id == user_id,
            SchoolMembership.school_id == school_id,
        )
    )
    return result.scalar_one_or_none()


async def get_tenant_context(
    x_school_code: Optional[str] = Header(default=None, alias="X-School-Code"),
    school: Optional[str] = Query(default=None, description="学校 code（与 X-School-Code 头等价）"),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """FastAPI 依赖：解析当前请求的租户上下文

    解析规则：
        - 游客（未登录）：必须显式提供 X-School-Code / ?school=，回查 schools 表确认存在且启用
        - 登录用户：
            * 显式提供 school code → 回查 schools 表确认存在且启用 → 校验 membership
            * 未提供 school code → 使用 user.school_id 对应学校（兼容现有调用方）
        - super_admin：可指定任意学校，跳过 membership 校验
        - 写请求忽略 body 里的 school_id（在各 API 内部实现，本依赖只负责解析）

    Raises:
        NotFoundException: 学校不存在 / 未启用 / 用户无权访问该校
    """
    requested_code = _resolve_school_code(x_school_code, school)

    # ------------------------------------------------------------
    # 游客分支
    # ------------------------------------------------------------
    if user is None:
        if not requested_code:
            raise NotFoundException(
                detail="未指定学校，请通过 X-School-Code 头或 ?school= 参数提供"
            )
        school_obj = await _load_school_by_code(db, requested_code)
        if school_obj is None or not school_obj.is_active:
            raise NotFoundException(detail="学校不存在或已停用")
        return TenantContext(
            school_id=school_obj.id,
            school_code=school_obj.code,
            user=None,
            effective_role="guest",
            is_guest=True,
            membership=None,
        )

    # ------------------------------------------------------------
    # 登录用户分支
    # ------------------------------------------------------------
    if requested_code:
        school_obj = await _load_school_by_code(db, requested_code)
        if school_obj is None or not school_obj.is_active:
            raise NotFoundException(detail="学校不存在或已停用")
    else:
        # 未显式指定 → 使用 user.school_id 对应学校
        school_obj = await _load_school_by_id(db, user.school_id)
        if school_obj is None or not school_obj.is_active:
            raise NotFoundException(detail="用户所属学校不存在或已停用")

    # super_admin 跨校操作：跳过 membership 校验，但仍需 school 存在且启用
    if is_super_admin(user):
        effective_role = Role.SUPER_ADMIN
        membership = await _load_membership(db, user.id, school_obj.id)
        return TenantContext(
            school_id=school_obj.id,
            school_code=school_obj.code,
            user=user,
            effective_role=effective_role,
            is_guest=False,
            membership=membership,
        )

    # 普通登录用户：校验在该校的访问权限
    membership = await _load_membership(db, user.id, school_obj.id)
    if membership is None or membership.status != "active":
        # 兼容旧用户：未在 school_memberships 表中，但 user.school_id 匹配
        if user.school_id != school_obj.id:
            raise NotFoundException(detail="无权访问该校")
        # 旧用户视为 active member
        membership = None
        effective_role = Role.USER
    else:
        # membership 存在且 active，按成员角色判定
        if membership.role == "admin":
            effective_role = Role.ADMIN
        else:
            effective_role = Role.USER

    return TenantContext(
        school_id=school_obj.id,
        school_code=school_obj.code,
        user=user,
        effective_role=effective_role,
        is_guest=False,
        membership=membership,
    )


# ============================================================
# TEN-02.2: get_effective_role + 资源级校验
# ============================================================
def get_effective_role(user: Optional[User], tenant: TenantContext) -> str:
    """获取用户在当前租户内的有效角色

    规则：
        - 游客（user=None）：返回 "guest"
        - super_admin：平台角色优先，跨校仍为 super_admin
        - 其他用户：
            * membership 存在且 active → 按 membership.role（admin/member）映射
            * 兼容旧用户：user.school_id == tenant.school_id 视为 user
            * 否则视为 guest（不应到达，因 get_tenant_context 已校验）

    Args:
        user: 当前用户（None 表示游客）
        tenant: 租户上下文

    Returns:
        super_admin / admin / user / guest
    """
    if user is None:
        return "guest"
    if is_super_admin(user):
        return Role.SUPER_ADMIN
    if tenant.membership is not None and tenant.membership.status == "active":
        if tenant.membership.role == "admin":
            return Role.ADMIN
        return Role.USER
    # 兼容旧用户：user.school_id == tenant.school_id 视为 user
    if user.school_id == tenant.school_id:
        return Role.USER
    return "guest"


def check_resource_in_tenant(resource_school_id: int, tenant: TenantContext) -> None:
    """资源级租户校验：跨校访问统一返回 404（不返回 403 以免泄露存在性）

    用法：
        post = await db.scalar(select(Post).where(Post.id == post_id))
        if post is None:
            raise NotFoundException(...)
        check_resource_in_tenant(post.school_id, tenant)  # 跨校 → 404

    Args:
        resource_school_id: 资源所属学校 ID
        tenant: 当前租户上下文

    Raises:
        NotFoundException: 资源不属于当前租户
    """
    if int(resource_school_id) != int(tenant.school_id):
        raise NotFoundException(detail="资源不存在")


def assert_writable_in_tenant(tenant: TenantContext) -> None:
    """校验当前租户可写：游客禁止写操作

    用法：在 POST/PUT/DELETE 接口开头调用，确保非游客
    """
    if tenant.is_guest or tenant.user is None:
        raise NotFoundException(detail="资源不存在")
