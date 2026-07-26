from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.core.exceptions import UnauthorizedException, ForbiddenException

# Bearer token scheme
security_scheme = HTTPBearer(auto_error=False)


async def get_current_db(db: AsyncSession = Depends(get_db)):
    return db


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_current_db)
) -> Optional[User]:
    """
    可选的当前用户依赖
    如果提供了有效的 Bearer token，返回用户对象
    如果没有提供 token 或 token 无效，返回 None
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # 验证 token 类型
    if payload.get("type") != "access":
        return None
    
    user_id = payload.get("sub")
    if user_id is None:
        return None
    
    # 查询用户
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        return None
    
    # 检查用户是否被禁用或删除
    if not user.is_active or user.is_deleted:
        return None
    
    return user


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """
    获取当前登录用户
    如果没有有效的 token 或用户不存在/被禁用，抛出 401 异常
    """
    if user is None:
        raise UnauthorizedException(detail="未授权访问，请先登录")
    
    return user


async def get_current_admin(
    user: User = Depends(get_current_user)
) -> User:
    """
    获取当前管理员用户（admin 或 super_admin）
    如果用户不是管理员，抛出 403 异常

    FND-03.3: 内部委托给 require_role(Role.ADMIN) 以统一权限校验入口，
    后续 TEN-02 可在此基础上叠加租户/资源校验。
    保留此函数仅为兼容既有依赖注入，新代码请直接使用 require_role(Role.ADMIN)。
    """
    from app.core.permissions import require_role, Role
    check = require_role(Role.ADMIN)
    # check 是一个 async 函数，签名 _check_role(user: User)
    return await check(user=user)
