"""学校教育邮箱域名校验服务。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.school import School
from app.models.school_domain import SchoolDomain
from app.models.user import User


def parse_email_domain(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    value = str(email).strip().lower()
    if "@" not in value:
        return None
    return value.rsplit("@", 1)[-1]


async def ensure_email_matches_school_domains(
    db: AsyncSession,
    school_id: int,
    email: Optional[str],
    *,
    require_email: bool = True,
) -> None:
    """校验教育邮箱是否属于注册学校。邮箱只用于校园认证。"""
    if require_email and (not email or not str(email).strip()):
        raise BadRequestException(detail="请填写所选学校的教育邮箱")
    domain = parse_email_domain(email)
    if domain is None:
        raise BadRequestException(detail="请输入有效的邮箱地址")

    school = (
        await db.execute(
            select(School).where(School.id == int(school_id), School.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if school is None:
        raise BadRequestException(detail="所选学校不存在")

    rows = (
        await db.execute(select(SchoolDomain.domain).where(SchoolDomain.school_id == school.id))
    ).scalars().all()
    if not rows:
        return
    allowed = {str(item).strip().lower() for item in rows if item}
    if domain not in allowed:
        readable = "、".join(sorted(allowed))
        raise BadRequestException(
            detail=f"请使用{school.name}的官方教育邮箱（@{readable}）完成认证"
        )


async def auto_verify_campus_domain_match(
    db: AsyncSession,
    user: User,
    school_id: int,
    email: Optional[str],
) -> bool:
    """历史兼容 helper；新注册/认证流程不会因域名命中而自动认证。"""
    # 保留函数签名供历史脚本导入，但不再被新业务调用。
    return False
