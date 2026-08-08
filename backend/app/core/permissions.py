"""权限矩阵与角色控制（T-X-01）

角色层级（低 → 高）：
    user < admin < super_admin

权限规则：
    - 高级角色自动包含低级角色的全部权限
    - require_role("admin") 同时允许 admin 和 super_admin
    - require_role("super_admin") 仅允许 super_admin

权限矩阵（主要接口）：

    角色          | 公开接口 | 普通用户接口 | 管理员接口 | 超级管理员接口
    ------------|---------|------------|-----------|-------------
    anonymous    |   ✓     |     ✗      |     ✗     |     ✗
    user         |   ✓     |     ✓      |     ✗     |     ✗
    admin        |   ✓     |     ✓      |     ✓     |     ✗
    super_admin  |   ✓     |     ✓      |     ✓     |     ✓

管理员专属接口（需 admin 及以上）：
    - GET  /admin/posts/pending            待审核列表
    - PUT  /admin/posts/{id}/approve       审核通过
    - PUT  /admin/posts/{id}/reject        审核拒绝
    - GET  /admin/users                    用户列表
    - PUT  /admin/users/{id}/toggle-active 禁用/启用用户
    - GET  /admin/reports                  举报列表
    - PUT  /admin/reports/{id}/handle      处理举报
    - POST /posts/{id}/transition          状态强制流转（管理员可执行所有合法流转）

普通用户接口（需 user 及以上）：
    - POST /posts                          发布信息（含草稿/提交审核）
    - PUT  /posts/{id}                     修改自己的信息
    - DELETE /posts/{id}                   删除自己的信息
    - POST /posts/{id}/transition          仅 draft→pending / draft→archived
    - POST /posts/{id}/validate            提交、切换或取消协同验证
    - POST /posts/{id}/likes               点赞 / 收藏 / 评论等互动

公开接口（无需认证）：
    - GET /posts                           信息列表
    - GET /posts/{id}                      信息详情
    - GET /categories                      分类列表
    - GET /map/locations                   地图标记
    - GET /search                          搜索
    - POST /auth/login / POST /auth/register 登录/注册
"""
from typing import Callable

from fastapi import Depends

from app.models.user import User
from app.core.exceptions import ForbiddenException


class Role:
    """角色常量"""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# 角色层级映射：数值越大权限越高
ROLE_LEVEL: dict[str, int] = {
    Role.USER: 1,
    Role.ADMIN: 2,
    Role.SUPER_ADMIN: 3,
}

# 全部合法角色值（用于校验 User.role 字段）
ALL_ROLES: set[str] = set(ROLE_LEVEL.keys())


def normalize_role(role: str | None) -> str:
    """归一化角色值，None 或空值视为 user"""
    if not role:
        return Role.USER
    # 兼容历史值（无历史别名，但保留扩展点）
    return role if role in ROLE_LEVEL else Role.USER


def get_role_level(role: str | None) -> int:
    """获取角色层级数值，未知角色视为 user 层级"""
    return ROLE_LEVEL.get(normalize_role(role), ROLE_LEVEL[Role.USER])


def has_role(user: User | None, required_role: str) -> bool:
    """判断用户是否拥有指定角色（含层级向下兼容）

    Args:
        user: 用户对象，None 表示未登录
        required_role: 要求的角色（user/admin/super_admin）

    Returns:
        True 表示用户角色层级 >= 要求角色层级

    Examples:
        has_role(user, "user")        # 任何登录用户都为 True
        has_role(admin_user, "admin") # admin/super_admin 为 True
        has_role(None, "user")        # 未登录为 False
    """
    if user is None:
        return False
    return get_role_level(user.role) >= ROLE_LEVEL.get(required_role, ROLE_LEVEL[Role.USER])


def is_admin(user: User | None) -> bool:
    """判断用户是否为管理员（admin 或 super_admin）"""
    return has_role(user, Role.ADMIN)


def is_super_admin(user: User | None) -> bool:
    """判断用户是否为超级管理员"""
    return has_role(user, Role.SUPER_ADMIN)


def require_role(required_role: str) -> Callable:
    """FastAPI 依赖工厂：要求当前用户达到指定角色层级

    用法：
        @router.post("/admin/xxx", dependencies=[Depends(require_role(Role.ADMIN))])
        async def some_admin_endpoint(...):
            ...

        或作为参数依赖：
        async def some_endpoint(admin: User = Depends(require_role(Role.ADMIN))):
            ...

    Args:
        required_role: 要求的最低角色（user/admin/super_admin）

    Returns:
        FastAPI 依赖函数，校验通过返回 User 对象，否则抛 403
    """
    # 延迟导入避免循环依赖
    from app.dependencies import get_current_user

    async def _check_role(user: User = Depends(get_current_user)) -> User:
        if not has_role(user, required_role):
            raise ForbiddenException(
                detail=f"没有权限执行此操作，需要 {required_role} 及以上角色"
            )
        return user

    return _check_role


def require_campus_verified() -> Callable:
    """FastAPI 依赖工厂：要求当前用户已完成校园身份认证（D4 未认证全站只读门禁）

    应用于所有写操作端点（发帖/评论/点赞/评价/协同验证/订阅等）。
    未认证用户（campus_verified=False）一律 403，仅保留只读权限。

    用法：
        @router.post("/posts", dependencies=[Depends(require_campus_verified())])
        async def create_post(...):
            ...

        或作为参数依赖：
        async def some_endpoint(user: User = Depends(require_campus_verified())):
            ...
    """
    # 延迟导入避免循环依赖
    from app.dependencies import get_current_user
    from app.core.tenant import get_tenant_context
    from app.core.campus import is_registration_school

    async def _check_verified(
        user: User = Depends(get_current_user),
        tenant=Depends(get_tenant_context),
    ) -> User:
        if user.role != Role.SUPER_ADMIN and not is_registration_school(user, tenant.school_id):
            raise ForbiddenException(
                detail="当前学校仅支持浏览，校园身份认证仅适用于注册时选择的学校"
            )
        if not user.campus_verified:
            raise ForbiddenException(
                detail="请先完成校园身份认证后再发布内容（未认证用户仅拥有只读权限）"
            )
        return user

    return _check_verified


def require_campus_verified_or_admin() -> Callable:
    """要求校园认证，管理员可凭角色直接执行地点管理操作。"""
    from app.dependencies import get_current_user
    from app.core.tenant import get_tenant_context
    from app.core.campus import is_registration_school

    async def _check_verified_or_admin(
        user: User = Depends(get_current_user),
        tenant=Depends(get_tenant_context),
    ) -> User:
        if user.role != Role.SUPER_ADMIN and not has_role(user, Role.ADMIN) and not is_registration_school(user, tenant.school_id):
            raise ForbiddenException(
                detail="当前学校仅支持浏览，普通用户只能在注册学校新增地点"
            )
        if user.campus_verified or has_role(user, Role.ADMIN):
            return user
        raise ForbiddenException(
            detail="请先完成校园身份认证后再新增地点（管理员可直接操作）"
        )

    return _check_verified_or_admin


# ============================================================
# TEN-02.2: 租户内有效角色（实际实现位于 app.core.tenant，
# 避免与 TenantContext 形成循环导入；此处提供委托接口便于从 permissions 导入）
# ============================================================
def get_effective_role(user, tenant) -> str:
    """获取用户在当前租户内的有效角色（委托给 app.core.tenant.get_effective_role）

    规则：
        - super_admin：平台角色优先，跨校仍为 super_admin
        - 其他用户：取租户内的成员角色（admin/member）；非该校成员视为 guest
        - 普通 admin 无权操作其他学校（由 TenantContext 解析时校验 membership）

    Args:
        user: 当前用户（None 表示游客）
        tenant: TenantContext 实例

    Returns:
        super_admin / admin / user / guest
    """
    from app.core.tenant import get_effective_role as _impl
    return _impl(user, tenant)


def check_resource_in_tenant(resource_school_id, tenant) -> None:
    """资源级租户校验：跨校访问统一返回 404（委托给 app.core.tenant.check_resource_in_tenant）

    用法：
        post = await db.scalar(select(Post).where(Post.id == post_id))
        if post is None:
            raise NotFoundException(...)
        check_resource_in_tenant(post.school_id, tenant)  # 跨校 → 404
    """
    from app.core.tenant import check_resource_in_tenant as _impl
    _impl(resource_school_id, tenant)
