"""统一权益校验服务（COM-01.2）。

约束原则：
1. 权益校验只能在服务端执行，前端不可绕过。
   所有受限操作（创建成员/发布内容/上传/AI 调用）后端必须调用 EntitlementService.check(key, current_value)
   或专用方法（如 ai_allowed）进行校验。
2. 硬限制（is_hard=True）：
   - 当前用量 >= limit_value → 拒绝（allowed=False, code="ENT_LIMIT_HARD_EXCEEDED"）
   - 用量未达上限但已接近（>= 80%）→ 允许执行并返回告警 code="ENT_WARNING_80"
3. 软限制（is_hard=False）：
   - 超出限额 → 允许执行，返回告警 code="ENT_WARNING_SOFT_EXCEEDED"
   - 达到 80%/100% 阈值 → 返回对应告警 code
4. 学校无 active 订阅 → 硬限制类操作拒绝（ENT_NO_SUBSCRIPTION）；软限制仅告警。
5. 权益项缺失（未配置该 key）→ 默认视为不限（allowed=True），便于运营扩展。

用法：
    svc = await EntitlementService.create(db, school_id)
    allowed, reason = await svc.check("posts_max", current_value=199)
    if not allowed:
        raise BadRequestException(detail=reason.message)
    if reason.code.startswith("ENT_WARNING"):
        # 记录告警或返回前端展示
        ...
    if await svc.ai_allowed(today_ai_calls=25):
        # 调用 AI
    else:
        # 降级普通搜索
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan_entitlement import PlanEntitlement
from app.models.school_subscription import SchoolSubscription
from app.models.product_plan import ProductPlan
from app.models.tenant_usage_daily import TenantUsageDaily
from app.models.school_membership import SchoolMembership
from app.models.post import Post
from app.models.user import User


# ============================================================
# 权益 key 常量
# ============================================================
class EntitlementKey:
    MEMBERS_MAX = "members_max"
    POSTS_MAX = "posts_max"
    STORAGE_MB = "storage_mb"
    AI_CALLS_DAILY = "ai_calls_daily"


# ============================================================
# 校验结果数据结构
# ============================================================
@dataclass
class EntitlementReason:
    """权益校验返回的原因对象。

    Attributes:
        allowed: 是否允许执行（True 表示业务可继续）
        code: 错误/告警码
            ENT_OK: 通过
            ENT_NO_SUBSCRIPTION: 学校无 active 订阅
            ENT_ENTITLEMENT_MISSING: 权益项未配置（视为不限，允许）
            ENT_LIMIT_HARD_EXCEEDED: 硬限制超额（拒绝）
            ENT_WARNING_80: 用量已达 80% 告警
            ENT_WARNING_100: 用量已达 100% 告警
            ENT_WARNING_SOFT_EXCEEDED: 软限制超额告警
        message: 中文说明（可直接展示给前端/用户）
        limit_value: 限额（None 表示不限）
        current_value: 当前用量
    """
    allowed: bool
    code: str
    message: str
    limit_value: Optional[int] = None
    current_value: Optional[int] = None


# ============================================================
# 告警阈值（80%）
# ============================================================
WARNING_RATIO_80 = 0.8


class EntitlementService:
    """统一权益校验服务（每实例绑定一个学校）。

    通过 EntitlementService.create(db, school_id) 构造；构造时即异步加载该校
    当前 active 订阅及对应套餐权益，避免每次 check 都查库。
    """

    def __init__(
        self,
        db: AsyncSession,
        school_id: int,
        subscription: Optional[SchoolSubscription],
        entitlements: dict[str, PlanEntitlement],
    ):
        self.db = db
        self.school_id = school_id
        self.subscription = subscription
        self.entitlements = entitlements  # key -> PlanEntitlement

    # ------------------------------------------------------------
    # 工厂方法
    # ------------------------------------------------------------
    @classmethod
    async def create(cls, db: AsyncSession, school_id: int) -> "EntitlementService":
        """加载学校当前 active 订阅及对应套餐权益项。"""
        # 取最新一条 active 订阅（一个学校同时只能有一个 active，由应用层保证）
        sub_stmt = (
            select(SchoolSubscription)
            .where(
                SchoolSubscription.school_id == school_id,
                SchoolSubscription.status == "active",
            )
            .order_by(SchoolSubscription.assigned_at.desc())
            .limit(1)
        )
        sub_result = await db.execute(sub_stmt)
        subscription = sub_result.scalar_one_or_none()

        entitlements: dict[str, PlanEntitlement] = {}
        if subscription is not None:
            ent_stmt = select(PlanEntitlement).where(
                PlanEntitlement.plan_id == subscription.plan_id
            )
            ent_result = await db.execute(ent_stmt)
            for ent in ent_result.scalars().all():
                entitlements[ent.key] = ent

        return cls(
            db=db,
            school_id=school_id,
            subscription=subscription,
            entitlements=entitlements,
        )

    # ------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------
    @property
    def has_active_subscription(self) -> bool:
        return self.subscription is not None

    @property
    def plan_code(self) -> Optional[str]:
        """当前订阅对应套餐 code（仅供日志/UI 展示，业务校验不应依赖）。"""
        if self.subscription is None:
            return None
        # 通过 relationship 加载 plan，若未加载则查询
        plan = self.subscription.plan
        if plan is not None:
            return plan.code
        return None

    # ------------------------------------------------------------
    # 核心校验入口
    # ------------------------------------------------------------
    async def check(self, key: str, current_value: int) -> EntitlementReason:
        """校验指定 key 在当前用量下是否允许执行操作。

        Args:
            key: 权益 key（如 EntitlementKey.POSTS_MAX）
            current_value: 当前已用量（已存在成员数/已发布帖数等）

        Returns:
            EntitlementReason：allowed=True 可执行，allowed=False 拒绝。
        """
        # 无 active 订阅
        if self.subscription is None:
            return EntitlementReason(
                allowed=False,
                code="ENT_NO_SUBSCRIPTION",
                message="当前学校未开通有效套餐，请联系平台开通后继续操作",
                current_value=current_value,
            )

        # 订阅已过期 / 暂停（理论上不应处于 active 状态，但双重校验保险）
        now = datetime.now()
        if self.subscription.expires_at is not None and self.subscription.expires_at < now:
            return EntitlementReason(
                allowed=False,
                code="ENT_NO_SUBSCRIPTION",
                message="当前学校订阅已到期，请联系平台续期",
                limit_value=None,
                current_value=current_value,
            )

        ent = self.entitlements.get(key)
        if ent is None:
            # 未配置该权益项 → 视为不限
            return EntitlementReason(
                allowed=True,
                code="ENT_ENTITLEMENT_MISSING",
                message=f"权益项 {key} 未配置，默认不限",
                current_value=current_value,
            )

        limit = ent.limit_value
        if limit is None or limit <= 0:
            # 限额为 NULL 或 0 → 不限
            return EntitlementReason(
                allowed=True,
                code="ENT_OK",
                message="不限",
                limit_value=limit,
                current_value=current_value,
            )

        # 计算阈值
        threshold_80 = int(limit * WARNING_RATIO_80)  # 80% 阈值（向下取整）

        if current_value >= limit:
            # 已达或超过限额
            if ent.is_hard:
                return EntitlementReason(
                    allowed=False,
                    code="ENT_LIMIT_HARD_EXCEEDED",
                    message=f"已达 {key} 上限 {limit}（当前 {current_value}），操作被拒绝",
                    limit_value=limit,
                    current_value=current_value,
                )
            else:
                return EntitlementReason(
                    allowed=True,
                    code="ENT_WARNING_SOFT_EXCEEDED",
                    message=f"{key} 已超过软上限 {limit}（当前 {current_value}），请尽快扩容",
                    limit_value=limit,
                    current_value=current_value,
                )
        elif current_value >= threshold_80:
            # 达到 80% 告警阈值
            return EntitlementReason(
                allowed=True,
                code="ENT_WARNING_80",
                message=f"{key} 已达 80% 告警阈值（{current_value}/{limit}）",
                limit_value=limit,
                current_value=current_value,
            )
        else:
            return EntitlementReason(
                allowed=True,
                code="ENT_OK",
                message="通过",
                limit_value=limit,
                current_value=current_value,
            )

    # ------------------------------------------------------------
    # 便捷方法：AI 调用降级
    # ------------------------------------------------------------
    async def ai_allowed(self, today_ai_calls: int) -> bool:
        """AI 调用是否允许；超限时返回 False，调用方应降级为普通搜索。

        Args:
            today_ai_calls: 当日已调用 AI 次数

        Returns:
            True: 可调用 AI；False: 已达上限，降级普通搜索。
        """
        reason = await self.check(EntitlementKey.AI_CALLS_DAILY, today_ai_calls)
        return reason.allowed

    # ------------------------------------------------------------
    # 便捷方法：直接基于当前数据库实际值校验
    # ------------------------------------------------------------
    async def check_members_count(self) -> EntitlementReason:
        """基于当前实际成员数校验 members_max。"""
        current = await self._count_active_members()
        return await self.check(EntitlementKey.MEMBERS_MAX, current)

    async def check_posts_count(self) -> EntitlementReason:
        """基于当前实际帖子数（非软删除）校验 posts_max。"""
        current = await self._count_active_posts()
        return await self.check(EntitlementKey.POSTS_MAX, current)

    async def check_storage(self, current_storage_mb: int) -> EntitlementReason:
        """基于当前存储用量校验 storage_mb。

        storage 由外部统计（上传文件总大小），故需调用方传入 current_storage_mb。
        """
        return await self.check(EntitlementKey.STORAGE_MB, current_storage_mb)

    async def check_ai_calls_today(self) -> EntitlementReason:
        """基于 tenant_usage_daily 当日 ai_calls_count 校验 ai_calls_daily。"""
        today = date.today()
        current = await self._get_ai_calls_today(today)
        return await self.check(EntitlementKey.AI_CALLS_DAILY, current)

    # ------------------------------------------------------------
    # 当前用量查询（私有）
    # ------------------------------------------------------------
    async def _count_active_members(self) -> int:
        stmt = select(func.count()).select_from(SchoolMembership).where(
            SchoolMembership.school_id == self.school_id,
            SchoolMembership.status == "active",
        )
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def _count_active_posts(self) -> int:
        """统计当前学校非软删除的全部状态帖子数（包含草稿/待审/已发等）。"""
        stmt = select(func.count()).select_from(Post).where(
            Post.school_id == self.school_id,
            Post.is_deleted == False,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def _get_ai_calls_today(self, today: date) -> int:
        stmt = select(TenantUsageDaily.ai_calls_count).where(
            TenantUsageDaily.school_id == self.school_id,
            TenantUsageDaily.usage_date == today,
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return int(row or 0)
