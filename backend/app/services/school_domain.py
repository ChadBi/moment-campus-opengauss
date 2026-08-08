"""学校教育邮箱域名统一校验服务（B-01 注册阶段强制）。

对外暴露：
    ensure_email_matches_school_domains(
        db, school_id, email, *, require_email=True
    ) -> None
        - 邮箱为空 + require_email=True → 400：请填写所选学校的教育邮箱
        - 邮箱格式非法（无 @）→ 400：请输入有效的邮箱地址
        - 命中运营豁免域（momentcampus.com）→ 放行
        - 命中全局测试邮箱域（qq.com）→ 放行（测试阶段放宽，方便大量账户注册）
        - 学校不存在/禁用 → 400：所选学校不存在
        - 学校有 SchoolDomain 配置 + 邮箱域名不在其内 → 400：请使用 XX 官方教育邮箱注册
        - 学校未配置任何 SchoolDomain（配置期极端场景）→ 放行，不 400 死锁

    async def auto_verify_campus_domain_match(
        db, user, school_id, email
    ) -> bool
        - 当邮箱域名命中该校任一 SchoolDomain（domain 或 addl_domains）
          时，自动将 user.campus_verified 置为 True 并记录认证时间，
          用于简化教育邮箱用户的注册→认证体验。
        - 运营豁免域（momentcampus.com）和全局测试域（qq.com）不
          触发自动认证，保持需手动走 send/confirm 流程。
        - 命中并成功设置 → 返回 True；未命中或无需处理 → 返回 False。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.school import School
from app.models.school_domain import SchoolDomain
from app.models.user import User

# 运营豁免域：平台自身账号（admin@momentcampus.com 等）不受学校域名限制
ALLOWED_NON_CAMPUS_DOMAINS: frozenset[str] = frozenset({"momentcampus.com"})

# 全局测试邮箱白名单域：所有学校一律放行，用于开发/联调阶段
# （测试者账号少，没有足量校园邮箱账户）
# 若需增加通用域，直接在此 frozenset 添加域名（如 "163.com"、"gmail.com" 等）
GLOBAL_TEST_EMAIL_DOMAINS: frozenset[str] = frozenset({"qq.com"})


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

    # Rule 3: 豁免域（运营邮箱）+ 全局测试邮箱域 → 直出
    if domain in ALLOWED_NON_CAMPUS_DOMAINS or domain in GLOBAL_TEST_EMAIL_DOMAINS:
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
        test_domains = "、".join(sorted(GLOBAL_TEST_EMAIL_DOMAINS))
        raise BadRequestException(
            detail=(
                f"请使用{school.name}的官方教育邮箱注册（@ {readable}）"
                "；或使用 @momentcampus.com 运营邮箱"
                f"；或使用测试通用邮箱域（@ {test_domains}）。"
                "若为该校学生但邮箱后缀不在列表中，请联系该校管理员添加附加域名。"
            )
        )


async def auto_verify_campus_domain_match(
    db: AsyncSession,
    user: User,
    school_id: int,
    email: Optional[str],
) -> bool:
    """注册后自动校园认证：若邮箱域名命中该校任一 SchoolDomain，则置 campus_verified=True。

    目的：对使用官方教育邮箱（包括 addl_domains 附加域）注册的用户，
    省去手动发送/确认验证码的冗余流程，直接完成校园身份认证。

    规则：
    - 运营豁免域（momentcampus.com）和全局测试邮箱域（qq.com 等）
      不触发自动认证（前者为运营账号、后者为开发便捷账号，二者均非
      真实校园身份，必须手动走 verify-campus/send→confirm 流程）。
    - 学校未配置任何 SchoolDomain → 返回 False，不改动。
    - 邮箱域名命中该校 SchoolDomain.domain 集合 → 设置
      user.campus_verified=True，user.campus_verified_at=now()，返回 True。
    - 用户本来已经是 campus_verified=True → 保持原认证时间不覆盖。
    """
    domain = parse_email_domain(email)
    if domain is None:
        return False

    # 1. 豁免域/测试域不自动认证
    if domain in ALLOWED_NON_CAMPUS_DOMAINS or domain in GLOBAL_TEST_EMAIL_DOMAINS:
        return False

    # 2. 用户已认证则保持原状（保留原认证时间）
    if getattr(user, "campus_verified", False):
        return False

    # 3. 查学校：这里使用同一 session 里的 school_id 对应 SchoolDomain
    rows = (
        await db.execute(
            select(SchoolDomain.domain).where(
                SchoolDomain.school_id == int(school_id),
            )
        )
    ).scalars().all()
    if not rows:
        return False

    allowed = {d.lower() for d in rows if d}
    if domain not in allowed:
        return False

    # 4. 命中：置位自动认证
    user.campus_verified = True
    user.campus_verified_at = datetime.now()
    return True
