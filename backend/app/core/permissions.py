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
    - POST /posts/{id}/validations         提交协同验证
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
