"""学校教育邮箱域名统一校验服务（B-01 注册阶段强制）。

对外暴露：
    ensure_email_matches_school_domains(
        db, school_id, email, *, require_email=True
    ) -> None
        - 邮箱为空 + require_email=True → 400：请填写所选学校的教育邮箱
        - 邮箱格式非法（无 @）→ 400：请输入有效的邮箱地址
        - 命中豁免域（momentcampus.com 运营邮箱）→ 放行
        - 学校不存在/禁用 → 400：所选学校不存在
        - 学校有 SchoolDomain 配置 + 邮箱域名不在其内 → 400：请使用 XX 官方教育邮箱注册
        - 学校未配置任何 SchoolDomain（配置期极端场景）→ 放行，不 400 死锁
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.school import School
from app.models.school_domain import SchoolDomain

# 运营豁免域：平台自身账号（admin@momentcampus.com 等）不受学校域名限制
ALLOWED_NON_CAMPUS_DOMAINS: frozenset[str] = frozenset({"momentcampus.com"})


def parse_email_domain(email: Optional[str]) -> Optional[str]:
    """从邮箱中解析小写域名；格式非法或空返回 None。"""
    if not email:
        return None
    s = str(email).strip().lower()
    if "@" not in s:
        return None
    return s.rsplit("@", 1)[-1]


async def ensure_email_matches_school_domains(
    db: AsyncSession,
    school_id: int,
    email: Optional[str],
    *,
    require_email: bool = True,
) -> None:
    """B-01 统一 helper：注册阶段强制校验所选学校的教育邮箱域名。

    当且仅当：
    - require_email=True 时，空邮箱被视为错误（用于 register；其他场景如编辑资料
      时可以传 require_email=False 跳过空值拦截）。
    - 学校有至少一条 SchoolDomain，且用户邮箱域名不在列表，也不在豁免域 → 抛 400。
    """
    # Rule 1: 空邮箱
    if require_email and (not email or not str(email).strip()):
        raise BadRequestException(detail="请填写所选学校的教育邮箱")

    # Rule 2: 解析域名
    domain = parse_email_domain(email)
    if domain is None:
        raise BadRequestException(detail="请输入有效的邮箱地址")

    # Rule 3: 豁免域（运营邮箱）直出
    if domain in ALLOWED_NON_CAMPUS_DOMAINS:
        return

    # Rule 4: 学校必须存在且激活
    school = (
        await db.execute(
            select(School).where(School.id == int(school_id), School.is_active == True)
        )
    ).scalar_one_or_none()
    if school is None:
        raise BadRequestException(detail="所选学校不存在")

    # Rule 5: 查该校允许域名；空配置期放行（避免 400 死锁）
    rows = (
        await db.execute(
            select(SchoolDomain.domain).where(
                SchoolDomain.school_id == school.id,
            )
        )
    ).scalars().all()
    if not rows:
        return

    allowed = {d.lower() for d in rows if d}
    if domain not in allowed:
        readable = "、".join(sorted(allowed))
        raise BadRequestException(
            detail=(
                f"请使用{school.name}的官方教育邮箱注册（@ {readable}）"
                "；或使用 @momentcampus.com 运营邮箱。"
                "若为该校学生但邮箱后缀不在列表中，请联系该校管理员添加附加域名。"
            )
        )
