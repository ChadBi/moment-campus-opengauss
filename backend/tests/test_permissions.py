"""T-X-01 权限矩阵单元测试

覆盖：
- 角色常量与层级定义
- normalize_role / get_role_level
- has_role 层级判断
- is_admin / is_super_admin
- require_role 依赖工厂（通过模拟 User 对象）
"""
import pytest
from unittest.mock import MagicMock

from app.core.permissions import (
    Role,
    ROLE_LEVEL,
    ALL_ROLES,
    normalize_role,
    get_role_level,
    has_role,
    is_admin,
    is_super_admin,
    require_role,
)
from app.core.exceptions import ForbiddenException


def _make_user(role: str | None) -> MagicMock:
    """构造模拟用户对象"""
    user = MagicMock()
    user.role = role
    return user


class TestRoleConstants:
    """角色常量定义完整性"""

    def test_three_roles_defined(self):
        """3 种角色全部定义"""
        assert Role.USER == "user"
        assert Role.ADMIN == "admin"
        assert Role.SUPER_ADMIN == "super_admin"

    def test_role_level_hierarchy(self):
        """角色层级数值递增"""
        assert ROLE_LEVEL[Role.USER] < ROLE_LEVEL[Role.ADMIN]
        assert ROLE_LEVEL[Role.ADMIN] < ROLE_LEVEL[Role.SUPER_ADMIN]

    def test_all_roles_set(self):
        """ALL_ROLES 集合包含 3 个角色"""
        assert ALL_ROLES == {"user", "admin", "super_admin"}
        assert len(ALL_ROLES) == 3


class TestNormalizeRole:
    """normalize_role 函数"""

    def test_valid_roles_unchanged(self):
        assert normalize_role("user") == "user"
        assert normalize_role("admin") == "admin"
        assert normalize_role("super_admin") == "super_admin"

    def test_none_defaults_to_user(self):
        assert normalize_role(None) == "user"

    def test_empty_string_defaults_to_user(self):
        assert normalize_role("") == "user"

    def test_unknown_role_defaults_to_user(self):
        assert normalize_role("guest") == "user"
        assert normalize_role("moderator") == "user"


class TestGetRoleLevel:
    """get_role_level 函数"""

    def test_known_roles(self):
        assert get_role_level("user") == ROLE_LEVEL[Role.USER]
        assert get_role_level("admin") == ROLE_LEVEL[Role.ADMIN]
        assert get_role_level("super_admin") == ROLE_LEVEL[Role.SUPER_ADMIN]

    def test_none_returns_user_level(self):
        assert get_role_level(None) == ROLE_LEVEL[Role.USER]

    def test_unknown_returns_user_level(self):
        assert get_role_level("unknown") == ROLE_LEVEL[Role.USER]


class TestHasRole:
    """has_role 层级判断"""

    def test_none_user_fails_all(self):
        """未登录用户对任何角色要求都返回 False"""
        assert has_role(None, Role.USER) is False
        assert has_role(None, Role.ADMIN) is False
        assert has_role(None, Role.SUPER_ADMIN) is False

    def test_user_can_access_user(self):
        """普通用户满足 user 角色"""
        assert has_role(_make_user("user"), Role.USER) is True

    def test_user_cannot_access_admin(self):
        """普通用户不满足 admin 角色"""
        assert has_role(_make_user("user"), Role.ADMIN) is False
        assert has_role(_make_user("user"), Role.SUPER_ADMIN) is False

    def test_admin_can_access_admin_and_user(self):
        """管理员满足 admin 和 user，不满足 super_admin"""
        admin = _make_user("admin")
        assert has_role(admin, Role.USER) is True
        assert has_role(admin, Role.ADMIN) is True
        assert has_role(admin, Role.SUPER_ADMIN) is False

    def test_super_admin_accesses_all(self):
        """超级管理员满足所有角色"""
        sa = _make_user("super_admin")
        assert has_role(sa, Role.USER) is True
        assert has_role(sa, Role.ADMIN) is True
        assert has_role(sa, Role.SUPER_ADMIN) is True

    def test_unknown_role_treated_as_user(self):
        """未知角色用户被视为 user"""
        unknown = _make_user("guest")
        assert has_role(unknown, Role.USER) is True
        assert has_role(unknown, Role.ADMIN) is False


class TestIsAdmin:
    """is_admin 函数"""

    def test_none_is_not_admin(self):
        assert is_admin(None) is False

    def test_user_is_not_admin(self):
        assert is_admin(_make_user("user")) is False

    def test_admin_is_admin(self):
        assert is_admin(_make_user("admin")) is True

    def test_super_admin_is_admin(self):
        """super_admin 也通过 is_admin 校验（层级向下兼容）"""
        assert is_admin(_make_user("super_admin")) is True


class TestIsSuperAdmin:
    """is_super_admin 函数"""

    def test_none_is_not_super_admin(self):
        assert is_super_admin(None) is False

    def test_user_is_not_super_admin(self):
        assert is_super_admin(_make_user("user")) is False

    def test_admin_is_not_super_admin(self):
        assert is_super_admin(_make_user("admin")) is False

    def test_super_admin_is_super_admin(self):
        assert is_super_admin(_make_user("super_admin")) is True


class TestRequireRole:
    """require_role 依赖工厂"""

    @pytest.mark.asyncio
    async def test_require_user_passes_for_user(self):
        """require_role('user') 对普通用户通过"""
        check = require_role(Role.USER)
        user = _make_user("user")
        result = await check(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_require_admin_passes_for_admin(self):
        """require_role('admin') 对管理员通过"""
        check = require_role(Role.ADMIN)
        admin = _make_user("admin")
        result = await check(user=admin)
        assert result is admin

    @pytest.mark.asyncio
    async def test_require_admin_passes_for_super_admin(self):
        """require_role('admin') 对超级管理员通过（层级向下兼容）"""
        check = require_role(Role.ADMIN)
        sa = _make_user("super_admin")
        result = await check(user=sa)
        assert result is sa

    @pytest.mark.asyncio
    async def test_require_admin_fails_for_user(self):
        """require_role('admin') 对普通用户抛 403"""
        check = require_role(Role.ADMIN)
        with pytest.raises(ForbiddenException):
            await check(user=_make_user("user"))

    @pytest.mark.asyncio
    async def test_require_super_admin_fails_for_admin(self):
        """require_role('super_admin') 对普通管理员抛 403"""
        check = require_role(Role.SUPER_ADMIN)
        with pytest.raises(ForbiddenException):
            await check(user=_make_user("admin"))

    @pytest.mark.asyncio
    async def test_require_super_admin_passes_for_super_admin(self):
        """require_role('super_admin') 对超级管理员通过"""
        check = require_role(Role.SUPER_ADMIN)
        sa = _make_user("super_admin")
        result = await check(user=sa)
        assert result is sa
