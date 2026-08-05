"""TEN-04.1 + TEN-04.2: 学校开通与初始化服务。

封装 super_admin 创建学校的完整初始化流程：
1. 创建 School 行（含地图中心/Logo/主题色/简介）
2. 从江南大学（code='jiangnan'）复制默认分类到新校
3. 创建 SchoolSettings 默认行
4. 分配默认套餐（trial 或指定 plan_code）→ SchoolSubscription

并提供：
- 开通清单（provisioning checklist）：品牌已设 / 管理员已接受 / 地点已导入(≥1) /
  首批内容(≥1) / 首批成员(≥1)，每项返回 bool
- 暂停学校写断言 assert_school_writable(school)：暂停时返回明确原因 + 恢复路径

注意：本服务不修改 app/core/tenant.py 核心逻辑。系统级 is_active 拦截由
tenant.py 的 get_tenant_context 在解析阶段完成（inactive → 404）；
本服务的 assert_school_writable 用于 super_admin 平台写路径的显式校验。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.school_settings import SchoolSettings
from app.models.school_subscription import SchoolSubscription


# 江南大学作为默认分类模板源（AGENTS.md：演示学校唯一江南大学 code='jiangnan'）
TEMPLATE_SCHOOL_CODE = "jiangnan"
DEFAULT_PLAN_CODE = "trial"


# ============================================================
# 开通创建请求 / 结果数据结构
# ============================================================
@dataclass
class SchoolProvisionRequest:
    """创建学校请求（super_admin）。"""
    code: str
    name: str
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    map_zoom: Optional[int] = None
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None
    description: Optional[str] = None
    plan_code: Optional[str] = None  # 默认 trial
    province: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    email_domain: Optional[str] = None  # B-03: 默认邮箱后缀（校园身份认证允许域名）


@dataclass
class ProvisioningChecklist:
    """开通清单（TEN-04.2）：每项 bool。"""
    brand_set: bool  # 品牌已设（logo_url 或 brand_color 或 site_name 任一）
    admin_accepted: bool  # 管理员已接受邀请（存在 active admin 成员）
    locations_imported: bool  # 地点已导入（≥1）
    first_content: bool  # 首批内容（≥1 非软删帖）
    first_members: bool  # 首批成员（≥1 active 成员）

    @property
    def all_done(self) -> bool:
        return all(asdict(self).values())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["all_done"] = self.all_done
        return d


# ============================================================
# 服务实现
# ============================================================
class SchoolProvisioningService:
    """学校开通与初始化服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------
    # 创建学校 + 完整初始化
    # ------------------------------------------------------------
    async def create_school(
        self,
        req: SchoolProvisionRequest,
        operator_id: Optional[int] = None,
    ) -> dict:
        """创建学校并完成完整初始化（分类/设置/订阅）。

        返回 dict：{school, settings, subscription, categories_copied}
        """
        # 1. 校验 code 唯一
        existing = (await self.db.execute(
            select(School).where(School.code == req.code)
        )).scalar_one_or_none()
        if existing is not None:
            raise ConflictException(detail=f"学校 code='{req.code}' 已存在")

        # 2. 创建 School
        now = datetime.now()
        school = School(
            code=req.code,
            name=req.name,
            center_lat=req.center_lat,
            center_lng=req.center_lng,
            map_zoom=req.map_zoom if req.map_zoom is not None else 16,
            logo_url=req.logo_url,
            province=req.province,
            city=req.city,
            address=req.address,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(school)
        await self.db.flush()  # 拿到 school.id

        # 3. 复制默认分类（从江南大学）
        categories_copied = await self._copy_template_categories(school.id)

        # 4. 创建 SchoolSettings 默认行
        settings = SchoolSettings(
            school_id=school.id,
            site_name=req.name,  # 默认站点名 = 学校名
            description=req.description,
            brand_color=req.brand_color,
            logo_url=req.logo_url,
            created_at=now,
            updated_at=now,
        )
        self.db.add(settings)

        # 5. 分配默认套餐
        plan_code = req.plan_code or DEFAULT_PLAN_CODE
        subscription = await self._assign_plan(school.id, plan_code, operator_id, now)

        # 6. B-03: 写入默认邮箱域名（校园身份认证允许域名）
        if req.email_domain:
            from app.models.school_domain import SchoolDomain
            self.db.add(SchoolDomain(
                school_id=school.id,
                domain=req.email_domain.strip().lower().lstrip("@"),
                is_primary=True,
                created_at=now,
                updated_at=now,
            ))

        await self.db.flush()
        return {
            "school": school,
            "settings": settings,
            "subscription": subscription,
            "categories_copied": categories_copied,
        }

    # ------------------------------------------------------------
    # 复制分类模板
    # ------------------------------------------------------------
    async def _copy_template_categories(self, new_school_id: int) -> int:
        """从江南大学复制分类到新校。返回复制的数量。"""
        # 找到模板学校（江南大学）
        template_school = (await self.db.execute(
            select(School).where(School.code == TEMPLATE_SCHOOL_CODE)
        )).scalar_one_or_none()
        if template_school is None:
            # 模板学校不存在（测试环境可能未初始化）→ 跳过复制，返回 0
            return 0

        # 拉取模板分类
        rows = (await self.db.execute(
            select(Category).where(
                Category.school_id == template_school.id,
                Category.is_active == True,  # noqa: E712
            ).order_by(Category.sort_order)
        )).scalars().all()

        if not rows:
            return 0

        now = datetime.now()
        count = 0
        for c in rows:
            new_cat = Category(
                school_id=new_school_id,
                name=c.name,
                code=c.code,
                icon=c.icon,
                description=c.description,
                default_validity_days=c.default_validity_days,
                sort_order=c.sort_order,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.db.add(new_cat)
            count += 1
        await self.db.flush()
        return count

    # ------------------------------------------------------------
    # 分配套餐
    # ------------------------------------------------------------
    async def _assign_plan(
        self,
        school_id: int,
        plan_code: str,
        operator_id: Optional[int],
        now: datetime,
    ) -> SchoolSubscription:
        """给学校分配指定套餐（创建 active 订阅）。"""
        plan = (await self.db.execute(
            select(ProductPlan).where(ProductPlan.code == plan_code)
        )).scalar_one_or_none()
        if plan is None:
            raise BadRequestException(detail=f"套餐 code='{plan_code}' 不存在")
        if plan.status != "active":
            raise BadRequestException(
                detail=f"套餐 '{plan_code}' 当前状态为 {plan.status}，不可分配"
            )

        sub = SchoolSubscription(
            school_id=school_id,
            plan_id=plan.id,
            status="active",
            started_at=now,
            expires_at=None,
            assigned_by=operator_id,
            assigned_at=now,
            note=f"学校开通时自动分配套餐 {plan_code}",
            created_at=now,
            updated_at=now,
        )
        self.db.add(sub)
        await self.db.flush()
        return sub

    # ------------------------------------------------------------
    # 开通清单
    # ------------------------------------------------------------
    async def get_provisioning_checklist(self, school_id: int) -> ProvisioningChecklist:
        """计算学校开通清单各项状态。"""
        school = (await self.db.execute(
            select(School).where(School.id == school_id)
        )).scalar_one_or_none()
        if school is None:
            raise NotFoundException(detail="学校不存在")

        # 品牌已设：logo_url 或 settings.brand_color 或 settings.site_name 任一非空
        settings = (await self.db.execute(
            select(SchoolSettings).where(SchoolSettings.school_id == school_id)
        )).scalar_one_or_none()
        brand_set = bool(
            school.logo_url
            or (settings and (settings.brand_color or settings.logo_url or settings.site_name))
        )

        # 管理员已接受：存在 active admin 成员
        admin_count = (await self.db.execute(
            select(func.count()).select_from(SchoolMembership).where(
                SchoolMembership.school_id == school_id,
                SchoolMembership.status == "active",
                SchoolMembership.role == "admin",
            )
        )).scalar() or 0
        admin_accepted = int(admin_count) >= 1

        # 地点已导入（≥1 非软删）
        loc_count = (await self.db.execute(
            select(func.count()).select_from(Location).where(
                Location.school_id == school_id,
                Location.is_deleted == False,  # noqa: E712
            )
        )).scalar() or 0
        locations_imported = int(loc_count) >= 1

        # 首批内容（≥1 非软删帖）
        post_count = (await self.db.execute(
            select(func.count()).select_from(Post).where(
                Post.school_id == school_id,
                Post.is_deleted == False,  # noqa: E712
            )
        )).scalar() or 0
        first_content = int(post_count) >= 1

        # 首批成员（≥1 active 成员）
        member_count = (await self.db.execute(
            select(func.count()).select_from(SchoolMembership).where(
                SchoolMembership.school_id == school_id,
                SchoolMembership.status == "active",
            )
        )).scalar() or 0
        first_members = int(member_count) >= 1

        return ProvisioningChecklist(
            brand_set=brand_set,
            admin_accepted=admin_accepted,
            locations_imported=locations_imported,
            first_content=first_content,
            first_members=first_members,
        )

    # ------------------------------------------------------------
    # 暂停学校写断言（TEN-04.2）
    # ------------------------------------------------------------
    @staticmethod
    def assert_school_writable(school: Optional[School]) -> None:
        """显式校验学校可写：暂停时拒绝新增写入并返回明确原因 + 恢复路径。

        用法（super_admin 平台写路径或服务层显式校验）：
            school = await db.scalar(select(School).where(School.id == sid))
            SchoolProvisioningService.assert_school_writable(school)

        注意：系统级拦截由 app/core/tenant.py 的 get_tenant_context 完成
        （inactive → 404 "学校不存在或已停用"），本方法用于平台层显式断言，
        提供更明确的恢复路径提示。
        """
        if school is None:
            raise NotFoundException(detail="学校不存在")
        if not school.is_active:
            raise BadRequestException(
                detail=(
                    "学校已暂停，新增写入被拒绝。"
                    "请联系平台管理员通过 PUT /api/v1/platform/schools/{id}/status "
                    "（status=active）恢复学校后继续操作"
                )
            )


# ============================================================
# 审计日志辅助（平台动作专用，TEN-04.3）
# ============================================================
async def write_platform_audit(
    db: AsyncSession,
    *,
    operator_id: Optional[int],
    target_school_id: Optional[int],
    action: str,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """写入一条平台审计日志（不 commit，由调用方控制事务）。"""
    from app.models.platform_audit import PlatformAuditLog

    log = PlatformAuditLog(
        operator_id=operator_id,
        target_school_id=target_school_id,
        action=action,
        old_value=json.dumps(old_value, ensure_ascii=False, default=str) if old_value else None,
        new_value=json.dumps(new_value, ensure_ascii=False, default=str) if new_value else None,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.now(),
    )
    db.add(log)
    await db.flush()


# ============================================================
# COM-02.2：学校开通向导批量导入（地点 + 首批内容）
# ============================================================
# 设计要点：
# 1. 只接受当前目标学校的数据：school_id 强制为目标学校，忽略请求体里的 school_id
# 2. 预览（dry_run=True）：只校验和返回将要写入的行，不写库
# 3. 提交（dry_run=False）：任一行失败整批回滚（savepoint），记录批次（PlatformAuditLog）
# 4. 行类型：location / post；post 引用 location 时可通过 row_index 临时绑定
# 5. 不直接 commit，由调用方控制事务（保持与本文件其他方法一致）
import csv
import io
import uuid
from dataclasses import dataclass, field


@dataclass
class ImportRowError:
    """单行错误。"""
    row_index: int  # 1-based，与 CSV 行号对齐
    field: str
    message: str


@dataclass
class ImportPreviewResult:
    """导入预览结果（不写库）。"""
    school_id: int
    total_rows: int
    locations: list[dict] = field(default_factory=list)
    posts: list[dict] = field(default_factory=list)
    errors: list[ImportRowError] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "school_id": self.school_id,
            "total_rows": self.total_rows,
            "locations_count": len(self.locations),
            "posts_count": len(self.posts),
            "valid": self.valid,
            "errors": [
                {"row_index": e.row_index, "field": e.field, "message": e.message}
                for e in self.errors
            ],
            "locations": self.locations,
            "posts": self.posts,
        }


@dataclass
class ImportCommitResult:
    """导入提交结果（写库）。"""
    batch_id: str
    school_id: int
    locations_created: int
    posts_created: int
    total_created: int
    errors: list[ImportRowError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "school_id": self.school_id,
            "locations_created": self.locations_created,
            "posts_created": self.posts_created,
            "total_created": self.total_created,
            "errors": [
                {"row_index": e.row_index, "field": e.field, "message": e.message}
                for e in self.errors
            ],
        }


class SchoolBatchImportService:
    """COM-02.2：学校开通向导批量导入服务。

    支持两类行：
      - location：地点（name/description/latitude/longitude/floor/building）
      - post：首批内容（title/content/category_code/location_ref/expire_at）

    校验规则：
      - location：name 必填且非空，latitude/longitude 必填且为有效数值
      - post：title/content/category_code 必填；
              category_code 必须存在于目标学校；
              location_ref 可选，引用同批次内 location 的 row_index 或 name
      - school_id 强制为目标学校（忽略请求体里的 school_id）

    Task 1.2 调整：移除 post_type_code 字段（PostType 已删除，统一使用 category）

    用法：
        svc = SchoolBatchImportService(db)
        preview = await svc.preview(rows, school_id=1)
        if preview.valid:
            result = await svc.commit(preview, school_id=1, operator_id=1)
    """

    LOCATION_FIELDS = {"name", "description", "latitude", "longitude", "floor", "building"}
    POST_FIELDS = {
        "title", "content", "category_code",
        "location_ref", "expire_at", "is_anonymous", "contact_info",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------
    # 解析输入
    # ------------------------------------------------------------
    @staticmethod
    def parse_csv(file_bytes: bytes) -> list[dict]:
        """解析 CSV 文本为行字典列表。

        CSV 第一行为表头，必须包含 type 列（location/post）。
        编码 utf-8-sig 兼容 BOM。
        """
        text = file_bytes.decode("utf-8-sig", errors="strict")
        reader = csv.DictReader(io.StringIO(text))
        rows: list[dict] = []
        for r in reader:
            # 过滤空行
            if not any((v or "").strip() for v in r.values()):
                continue
            rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k})
        return rows

    @staticmethod
    def parse_json_rows(payload: list[dict]) -> list[dict]:
        """直接接收 JSON 数组。"""
        if not isinstance(payload, list):
            raise BadRequestException(detail="导入数据必须是数组")
        return [
            {k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            for r in payload
            if isinstance(r, dict)
        ]

    # ------------------------------------------------------------
    # 预览（不写库）
    # ------------------------------------------------------------
    async def preview(
        self,
        rows: list[dict],
        school_id: int,
    ) -> ImportPreviewResult:
        """校验并预览将要导入的行（不写库）。"""
        # 校验学校存在且可写
        school = (await self.db.execute(
            select(School).where(School.id == school_id)
        )).scalar_one_or_none()
        if school is None:
            raise NotFoundException(detail="学校不存在")
        SchoolProvisioningService.assert_school_writable(school)

        result = ImportPreviewResult(school_id=school_id, total_rows=len(rows))

        # 预加载该校分类（按 code 索引）
        cat_rows = (await self.db.execute(
            select(Category).where(
                Category.school_id == school_id,
                Category.is_active == True,  # noqa: E712
            )
        )).scalars().all()
        cat_by_code: dict[str, Category] = {c.code: c for c in cat_rows}

        # Task 1.2 调整：PostType 已删除，不再需要预加载

        # 第一遍：按行解析 + 校验
        # 用于 post.location_ref 引用同批次 location
        location_refs: dict[str, dict] = {}  # key: row_index(int) 或 name(str) → location dict
        parsed_locations: list[tuple[int, dict]] = []  # (row_index, location_dict)
        parsed_posts: list[tuple[int, dict]] = []  # (row_index, post_dict)

        for idx, raw in enumerate(rows, start=1):
            row_type = (raw.get("type") or raw.get("row_type") or "").strip().lower()
            if row_type not in ("location", "post"):
                result.errors.append(ImportRowError(
                    row_index=idx, field="type",
                    message=f"行 {idx}：type 必须为 'location' 或 'post'（当前='{row_type}'）",
                ))
                continue

            if row_type == "location":
                loc, errs = self._parse_location_row(idx, raw)
                if errs:
                    result.errors.extend(errs)
                    continue
                parsed_locations.append((idx, loc))
                # 注册引用（name + row_index 都可被 post.location_ref 引用）
                location_refs[loc["name"]] = loc
                location_refs[str(idx)] = loc
            else:  # post
                post, errs = self._parse_post_row(idx, raw, cat_by_code)
                if errs:
                    result.errors.extend(errs)
                    continue
                parsed_posts.append((idx, post))

        # 第二遍：解析 post.location_ref（引用同批次 location）
        for idx, post in parsed_posts:
            ref = post.pop("_location_ref", None)
            if ref:
                ref_key = ref.strip()
                if ref_key not in location_refs:
                    result.errors.append(ImportRowError(
                        row_index=idx, field="location_ref",
                        message=f"行 {idx}：location_ref='{ref_key}' 在同批次中找不到对应 location",
                    ))
                    continue
                post["location_name"] = location_refs[ref_key]["name"]

        if result.errors:
            return result

        # 输出预览（保留行号便于前端展示）
        for idx, loc in parsed_locations:
            loc_out = dict(loc)
            loc_out["row_index"] = idx
            result.locations.append(loc_out)
        for idx, post in parsed_posts:
            post_out = dict(post)
            post_out["row_index"] = idx
            result.posts.append(post_out)
        return result

    # ------------------------------------------------------------
    # 提交（写库，任一行失败整批回滚）
    # ------------------------------------------------------------
    async def commit(
        self,
        preview: ImportPreviewResult,
        school_id: int,
        operator_id: Optional[int] = None,
        batch_id: Optional[str] = None,
    ) -> ImportCommitResult:
        """实际写入。任一行失败整批回滚，记录批次审计。"""
        if preview.errors:
            raise BadRequestException(detail="预览存在错误，不能提交；请先修复后重试")

        batch_id = batch_id or uuid.uuid4().hex
        now = datetime.now()

        # savepoint：任一行失败整批回滚
        # 注意：begin_nested 创建 savepoint，异常时 ROLLBACK TO SAVEPOINT
        try:
            async with self.db.begin_nested():
                # 1. 写地点
                created_locations: dict[str, Location] = {}  # name → Location
                for loc in preview.locations:
                    location = Location(
                        school_id=school_id,
                        name=loc["name"],
                        description=loc.get("description"),
                        latitude=loc["latitude"],
                        longitude=loc["longitude"],
                        floor=loc.get("floor"),
                        building=loc.get("building"),
                        post_count=0,
                        is_verified=True,  # 平台导入的地点默认已核验
                        created_at=now,
                        updated_at=now,
                        is_deleted=False,
                    )
                    self.db.add(location)
                    await self.db.flush()
                    created_locations[loc["name"]] = location

                # 2. 写帖子（首批内容默认 published 状态，便于激活清单 first_content 达成）
                #    导入的帖子归属于 operator（super_admin），避免依赖具体 user
                from app.models.post import Post
                created_posts_count = 0
                for post in preview.posts:
                    loc_name = post.get("location_name")
                    location_id = None
                    if loc_name and loc_name in created_locations:
                        location_id = created_locations[loc_name].id

                    expire_at = post.get("expire_at")
                    expire_dt = None
                    if expire_at:
                        try:
                            expire_dt = datetime.fromisoformat(expire_at)
                        except ValueError:
                            # 预览阶段已校验，理论上不会到达
                            raise BadRequestException(
                                detail=f"行 {post.get('row_index')}：expire_at 格式无效"
                            )

                    new_post = Post(
                        user_id=operator_id or 1,  # 默认归属操作者；缺失时回退到 id=1
                        school_id=school_id,
                        category_id=post["category_id"],
                        location_id=location_id,
                        title=post["title"],
                        content=post["content"],
                        is_anonymous=post.get("is_anonymous", False),
                        status="published",  # 首批内容直接发布，达成激活清单
                        expire_at=expire_dt,
                        contact_info=post.get("contact_info"),
                        created_at=now,
                        updated_at=now,
                        is_deleted=False,
                    )
                    self.db.add(new_post)
                    await self.db.flush()
                    created_posts_count += 1

            # savepoint 成功提交后，写入批次审计日志（不在 savepoint 内）
            await write_platform_audit(
                self.db,
                operator_id=operator_id,
                target_school_id=school_id,
                action="school.import",
                old_value=None,
                new_value={
                    "batch_id": batch_id,
                    "locations_created": len(preview.locations),
                    "posts_created": created_posts_count,
                    "total_created": len(preview.locations) + created_posts_count,
                },
                reason=f"开通向导批量导入 batch_id={batch_id}",
            )
            await self.db.flush()

            return ImportCommitResult(
                batch_id=batch_id,
                school_id=school_id,
                locations_created=len(preview.locations),
                posts_created=created_posts_count,
                total_created=len(preview.locations) + created_posts_count,
            )
        except Exception as exc:
            # savepoint 已自动回滚到 ROLLBACK TO SAVEPOINT
            # 记录失败批次审计（在 savepoint 外，可独立提交）
            try:
                await write_platform_audit(
                    self.db,
                    operator_id=operator_id,
                    target_school_id=school_id,
                    action="school.import.failed",
                    old_value=None,
                    new_value={
                        "batch_id": batch_id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:500],
                    },
                    reason=f"开通向导批量导入失败 batch_id={batch_id}",
                )
                await self.db.flush()
            except Exception:
                pass  # 审计失败不影响主错误传播
            raise

    # ------------------------------------------------------------
    # 单行解析
    # ------------------------------------------------------------
    @staticmethod
    def _to_str(v) -> str:
        """安全转字符串：兼容 JSON 入参（float/int/bool/None）与 CSV 入参（str）。

        parse_json_rows 只对 str 值 strip，非 str 值（如 latitude=31.4912）
        会原样透传到这里；CSV 入参则全部为 str。本方法统一转为 str 供后续 strip/校验。
        """
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    def _parse_location_row(
        self,
        row_index: int,
        raw: dict,
    ) -> tuple[dict, list[ImportRowError]]:
        errs: list[ImportRowError] = []
        name = self._to_str(raw.get("name")).strip()
        if not name:
            errs.append(ImportRowError(row_index, "name", "name 不能为空"))
            name = ""

        description = self._to_str(raw.get("description")).strip() or None

        lat_raw = self._to_str(raw.get("latitude")).strip()
        lng_raw = self._to_str(raw.get("longitude")).strip()
        lat: Optional[float] = None
        lng: Optional[float] = None
        if not lat_raw:
            errs.append(ImportRowError(row_index, "latitude", "latitude 不能为空"))
        else:
            try:
                lat = float(lat_raw)
                if not (-90.0 <= lat <= 90.0):
                    errs.append(ImportRowError(
                        row_index, "latitude",
                        f"latitude 越界（-90~90），当前={lat}",
                    ))
            except ValueError:
                errs.append(ImportRowError(
                    row_index, "latitude",
                    f"latitude 不是有效数值：'{lat_raw}'",
                ))
        if not lng_raw:
            errs.append(ImportRowError(row_index, "longitude", "longitude 不能为空"))
        else:
            try:
                lng = float(lng_raw)
                if not (-180.0 <= lng <= 180.0):
                    errs.append(ImportRowError(
                        row_index, "longitude",
                        f"longitude 越界（-180~180），当前={lng}",
                    ))
            except ValueError:
                errs.append(ImportRowError(
                    row_index, "longitude",
                    f"longitude 不是有效数值：'{lng_raw}'",
                ))

        floor = self._to_str(raw.get("floor")).strip() or None
        building = self._to_str(raw.get("building")).strip() or None

        loc = {
            "name": name,
            "description": description,
            "latitude": lat,
            "longitude": lng,
            "floor": floor,
            "building": building,
        }
        return loc, errs

    def _parse_post_row(
        self,
        row_index: int,
        raw: dict,
        cat_by_code: dict[str, Category],
    ) -> tuple[dict, list[ImportRowError]]:
        errs: list[ImportRowError] = []
        title = self._to_str(raw.get("title")).strip()
        if not title:
            errs.append(ImportRowError(row_index, "title", "title 不能为空"))
        content = self._to_str(raw.get("content")).strip()
        if not content:
            errs.append(ImportRowError(row_index, "content", "content 不能为空"))

        category_code = self._to_str(raw.get("category_code")).strip()
        if not category_code:
            errs.append(ImportRowError(row_index, "category_code", "category_code 不能为空"))
        elif category_code not in cat_by_code:
            errs.append(ImportRowError(
                row_index, "category_code",
                f"category_code='{category_code}' 在目标学校不存在或未启用",
            ))

        # Task 1.2 调整：post_type_code 已移除（PostType 已删除，统一使用 category）

        location_ref = self._to_str(raw.get("location_ref")).strip() or None
        expire_at = self._to_str(raw.get("expire_at")).strip() or None
        if expire_at:
            try:
                datetime.fromisoformat(expire_at)
            except ValueError:
                errs.append(ImportRowError(
                    row_index, "expire_at",
                    f"expire_at 格式无效（需 ISO 8601），当前='{expire_at}'",
                ))

        # is_anonymous 兼容 JSON bool / 字符串
        is_anon_raw = raw.get("is_anonymous")
        if isinstance(is_anon_raw, bool):
            is_anonymous = is_anon_raw
        else:
            is_anon_str = self._to_str(is_anon_raw).strip().lower()
            is_anonymous = is_anon_str in ("1", "true", "yes", "y", "t")
        contact_info = self._to_str(raw.get("contact_info")).strip() or None

        post = {
            "title": title,
            "content": content,
            "category_code": category_code,
            "category_id": cat_by_code[category_code].id if category_code in cat_by_code else None,
            "_location_ref": location_ref,
            "expire_at": expire_at,
            "is_anonymous": is_anonymous,
            "contact_info": contact_info,
        }
        return post, errs


# ============================================================
# COM-02.4：激活漏斗
# ============================================================
@dataclass
class ActivationFunnelItem:
    """激活漏斗单条（每校一行）。"""
    school_id: int
    school_code: str
    school_name: str
    is_active: bool
    plan_code: Optional[str]
    subscription_status: Optional[str]
    checklist: dict  # ProvisioningChecklist.to_dict()
    activated: bool  # checklist.all_done 且 is_active
    activated_stage: int  # 已完成阶段数（0-5）

    def to_dict(self) -> dict:
        return {
            "school_id": self.school_id,
            "school_code": self.school_code,
            "school_name": self.school_name,
            "is_active": self.is_active,
            "plan_code": self.plan_code,
            "subscription_status": self.subscription_status,
            "checklist": self.checklist,
            "activated": self.activated,
            "activated_stage": self.activated_stage,
        }


async def build_activation_funnel(
    db: AsyncSession,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> list[ActivationFunnelItem]:
    """构建激活漏斗：每校一行，列出 5 项清单完成阶段。"""
    stmt = select(School)
    if is_active is not None:
        stmt = stmt.where(School.is_active == is_active)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((School.name.ilike(like)) | (School.code.ilike(like)))
    stmt = stmt.order_by(School.created_at.desc())
    schools = (await db.execute(stmt)).scalars().all()

    if not schools:
        return []

    school_ids = [s.id for s in schools]
    # 各校最新 active 订阅
    sub_rows = (await db.execute(
        select(SchoolSubscription)
        .options(selectinload(SchoolSubscription.plan))
        .where(
            SchoolSubscription.school_id.in_(school_ids),
            SchoolSubscription.status == "active",
        )
        .order_by(SchoolSubscription.assigned_at.desc())
    )).scalars().all()
    # 取每校最新一条
    sub_map: dict[int, SchoolSubscription] = {}
    for sub in sub_rows:
        if sub.school_id not in sub_map:
            sub_map[sub.school_id] = sub

    prov_svc = SchoolProvisioningService(db)
    items: list[ActivationFunnelItem] = []
    for s in schools:
        checklist = await prov_svc.get_provisioning_checklist(s.id)
        checklist_dict = checklist.to_dict()
        activated_stage = sum(1 for k, v in checklist_dict.items()
                              if k != "all_done" and v is True)
        sub = sub_map.get(s.id)
        items.append(ActivationFunnelItem(
            school_id=s.id,
            school_code=s.code,
            school_name=s.name,
            is_active=s.is_active,
            plan_code=(sub.plan.code if sub and sub.plan else None),
            subscription_status=(sub.status if sub else None),
            checklist=checklist_dict,
            activated=(checklist.all_done and s.is_active),
            activated_stage=activated_stage,
        ))
    return items
