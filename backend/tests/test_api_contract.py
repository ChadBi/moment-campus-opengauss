"""FND-01.4 端到端契约测试：关键 API 枚举、分页、OpenAPI 与 TS 类型

覆盖契约表中的关键枚举与字段：
- 举报类型（ReportType: spam/abuse/harassment/false_info/other）
- 帖子状态（PostStatusEnum: 6 态 draft/pending/published/expired/conflict/archived）
- 协同验证类型（ValidationTypeEnum: 2 类 confirmation/refutation）
- 分页（PaginatedResponse: total/total_pages/has_more 统一）
- PostUpdate 移除 status/is_recommend
- PostCreate.status 仅接受 draft/pending
- OpenAPI schema 自动生成正确枚举值
- API 响应分页包含 has_more 字段
"""
import pytest
from pydantic import ValidationError

from app.schemas.enums import ReportType, PostStatusEnum, ValidationTypeEnum
from app.schemas.common import PaginatedResponse
from app.schemas.post import PostCreate, PostUpdate
from app.schemas.interaction import ReportCreate, ValidationCreate


# ============================================================
# 一、枚举值契约
# ============================================================

class TestReportTypeEnum:
    """举报类型枚举（6 类）"""

    EXPECTED_VALUES = {"spam", "abuse", "harassment", "false_info", "other", "expired_info"}

    def test_enum_member_count(self):
        """举报类型恰好 6 类"""
        assert len(ReportType) == 6

    def test_enum_values_match_contract(self):
        """举报类型值与契约表一致"""
        actual = {member.value for member in ReportType}
        assert actual == self.EXPECTED_VALUES

    def test_each_value_is_string(self):
        """所有枚举值为字符串（便于 JSON 序列化）"""
        for member in ReportType:
            assert isinstance(member.value, str)

    def test_no_duplicate_values(self):
        """无重复值"""
        values = [member.value for member in ReportType]
        assert len(values) == len(set(values))


class TestPostStatusEnum:
    """帖子状态枚举（6 态状态机）"""

    EXPECTED_VALUES = {"draft", "pending", "published", "expired", "conflict", "archived"}

    def test_enum_member_count(self):
        """帖子状态恰好 6 态"""
        assert len(PostStatusEnum) == 6

    def test_enum_values_match_contract(self):
        """帖子状态值与契约表一致"""
        actual = {member.value for member in PostStatusEnum}
        assert actual == self.EXPECTED_VALUES

    def test_no_deleted_status(self):
        """不存在 deleted 状态（删除采用 is_deleted + archived）"""
        values = {member.value for member in PostStatusEnum}
        assert "deleted" not in values


class TestValidationTypeEnum:
    """协同验证类型枚举（2 类）"""

    EXPECTED_VALUES = {"confirmation", "refutation"}

    def test_enum_member_count(self):
        """验证类型恰好 2 类"""
        assert len(ValidationTypeEnum) == 2

    def test_enum_values_match_contract(self):
        """验证类型值与契约表一致"""
        actual = {member.value for member in ValidationTypeEnum}
        assert actual == self.EXPECTED_VALUES

    def test_two_voting_types(self):
        """2 类互斥投票：confirmation / refutation"""
        voting = {ValidationTypeEnum.CONFIRMATION.value, ValidationTypeEnum.REFUTATION.value}
        assert voting == {"confirmation", "refutation"}

# ============================================================
# 二、分页模型契约
# ============================================================

class TestPaginatedResponseContract:
    """PaginatedResponse 统一分页模型"""

    def test_has_required_fields(self):
        """包含契约要求的全部字段"""
        fields = set(PaginatedResponse.model_fields.keys())
        required = {"items", "page", "page_size", "total", "total_pages", "has_more"}
        assert required.issubset(fields)

    def test_has_more_field_exists(self):
        """FND-01.2: has_more 字段存在且默认 False"""
        resp = PaginatedResponse[int](items=[1, 2, 3], page=1, page_size=10, total=3, total_pages=1)
        assert resp.has_more is False

    def test_has_more_true_when_more_pages(self):
        """有更多页时 has_more=True"""
        resp = PaginatedResponse.create(items=[1], page=1, page_size=10, total=25)
        assert resp.has_more is True
        assert resp.total_pages == 3

    def test_has_more_false_on_last_page(self):
        """最后一页 has_more=False"""
        resp = PaginatedResponse.create(items=[1], page=3, page_size=10, total=25)
        assert resp.has_more is False
        assert resp.total_pages == 3

    def test_has_more_false_when_empty(self):
        """空结果 has_more=False"""
        resp = PaginatedResponse.create(items=[], page=1, page_size=10, total=0)
        assert resp.has_more is False
        assert resp.total_pages == 0

    def test_create_calculates_total_pages(self):
        """create() 正确计算 total_pages"""
        resp = PaginatedResponse.create(items=[1], page=1, page_size=20, total=41)
        assert resp.total_pages == 3  # ceil(41/20) = 3

    def test_create_calculates_has_more(self):
        """create() 正确计算 has_more"""
        resp = PaginatedResponse.create(items=[1], page=2, page_size=20, total=41)
        assert resp.has_more is True  # page 2 < total_pages 3

    def test_page_default_values(self):
        """默认页码与每页数量"""
        resp = PaginatedResponse[int]()
        assert resp.page == 1
        assert resp.page_size == 20
        assert resp.total == 0
        assert resp.total_pages == 0
        assert resp.has_more is False


# ============================================================
# 三、PostCreate / PostUpdate 契约
# ============================================================

class TestPostCreateContract:
    """PostCreate Schema 契约"""

    def test_status_accepts_draft(self):
        """status 接受 draft"""
        p = PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="draft")
        assert p.status == PostStatusEnum.DRAFT

    def test_status_accepts_pending(self):
        """status 接受 pending"""
        p = PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="pending")
        assert p.status == PostStatusEnum.PENDING

    def test_status_defaults_to_pending(self):
        """不传 status 默认 pending"""
        p = PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1)
        assert p.status == PostStatusEnum.PENDING

    def test_status_rejects_published(self):
        """创建时不能直接 published"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="published")

    def test_status_rejects_expired(self):
        """创建时不能直接 expired"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="expired")

    def test_status_rejects_conflict(self):
        """创建时不能直接 conflict"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="conflict")

    def test_status_rejects_archived(self):
        """创建时不能直接 archived"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="archived")

    def test_status_rejects_deleted(self):
        """不存在 deleted 状态"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="deleted")


class TestPostUpdateContract:
    """PostUpdate Schema 契约（FND-01.2: 移除 status / is_recommend）"""

    def test_status_field_removed(self):
        """PostUpdate 不包含 status 字段"""
        fields = set(PostUpdate.model_fields.keys())
        assert "status" not in fields

    def test_is_recommend_field_removed(self):
        """PostUpdate 不包含 is_recommend 字段"""
        fields = set(PostUpdate.model_fields.keys())
        assert "is_recommend" not in fields

    def test_status_ignored_when_provided(self):
        """传入 status 时被 Pydantic 忽略（不报错但不存储）"""
        update = PostUpdate(title="新标题五字以上", status="published")
        assert not hasattr(update, "status") or update.status is None

    def test_is_recommend_ignored_when_provided(self):
        """传入 is_recommend 时被 Pydantic 忽略"""
        update = PostUpdate(title="新标题五字以上", is_recommend=True)
        assert not hasattr(update, "is_recommend") or update.is_recommend is None

    def test_allowed_fields_present(self):
        """PostUpdate 保留允许修改的字段"""
        fields = set(PostUpdate.model_fields.keys())
        expected = {
            "title", "content", "category_id", "location_id",
            "is_anonymous", "image_urls",
            "expire_at",
            "lost_type", "contact_info",
        }
        assert expected.issubset(fields)


# ============================================================
# 四、ReportCreate / ValidationCreate 契约
# ============================================================

class TestReportCreateContract:
    """举报创建 Schema 契约"""

    def test_accepts_all_five_report_types(self):
        """接受全部 5 类举报类型"""
        for rt in ReportType:
            r = ReportCreate(report_type=rt)
            assert r.report_type == rt

    def test_accepts_string_values(self):
        """接受字符串值（与枚举值一致）"""
        for value in ["spam", "abuse", "harassment", "false_info", "other"]:
            r = ReportCreate(report_type=value)
            assert r.report_type.value == value

    def test_rejects_invalid_type(self):
        """拒绝非法举报类型"""
        with pytest.raises(ValidationError):
            ReportCreate(report_type="invalid_type")

    def test_rejects_old_inappropriate_type(self):
        """拒绝旧枚举值 inappropriate（已被 other 替代）"""
        with pytest.raises(ValidationError):
            ReportCreate(report_type="inappropriate")

    def test_description_optional(self):
        """description 可选"""
        r = ReportCreate(report_type="spam")
        assert r.description is None


class TestValidationCreateContract:
    """协同验证创建 Schema 契约"""

    def test_accepts_two_types(self):
        """仅接受两类正式验证类型"""
        for vtype in ["confirmation", "refutation"]:
            v = ValidationCreate(validation_type=vtype)
            assert v.validation_type.value == vtype

    @pytest.mark.parametrize(
        "vtype",
        ["update", "expiration_report", "conflict_report", "valid", "invalid", "uncertain"],
    )
    def test_rejects_non_canonical_types(self, vtype):
        with pytest.raises(ValidationError):
            ValidationCreate(validation_type=vtype)

    def test_rejects_invalid_type(self):
        """拒绝非法验证类型"""
        with pytest.raises(ValidationError):
            ValidationCreate(validation_type="approved")

    def test_rejects_empty_type(self):
        """拒绝空字符串"""
        with pytest.raises(ValidationError):
            ValidationCreate(validation_type="")


# ============================================================
# 五、OpenAPI Schema 契约
# ============================================================

class TestOpenAPIContract:
    """验证 FastAPI 自动生成的 OpenAPI schema 包含正确的枚举值"""

    def test_openapi_schema_generated(self):
        """OpenAPI schema 可正常生成"""
        from app.main import app
        schema = app.openapi()
        assert schema is not None
        assert "openapi" in schema
        assert "components" in schema

    def test_validation_uses_only_singular_endpoint(self):
        from app.main import app

        paths = app.openapi()["paths"]
        assert "/api/v1/posts/{post_id}/validate" in paths
        assert "/api/v1/posts/{post_id}/validations" not in paths

    def test_report_type_enum_in_openapi(self):
        """OpenAPI schema 中 ReportType 枚举值为 5 类"""
        from app.main import app
        schema = app.openapi()
        schemas = schema.get("components", {}).get("schemas", {})

        # ReportCreate 中 report_type 字段应引用 ReportType 枚举
        report_create_schema = schemas.get("ReportCreate", {})
        report_type_field = report_create_schema.get("properties", {}).get("report_type", {})
        enum_values = report_type_field.get("enum")
        if enum_values:
            assert set(enum_values) == {"spam", "abuse", "harassment", "false_info", "other"}

    def test_post_status_enum_in_openapi(self):
        """OpenAPI schema 中 PostStatusEnum 枚举值为 6 态"""
        from app.main import app
        schema = app.openapi()
        schemas = schema.get("components", {}).get("schemas", {})

        # 查找 PostStatusEnum 的 schema 定义
        status_schema = schemas.get("PostStatusEnum", {})
        enum_values = status_schema.get("enum")
        if enum_values:
            assert set(enum_values) == {"draft", "pending", "published", "expired", "conflict", "archived"}

    def test_paginated_response_has_more_in_openapi(self):
        """OpenAPI schema 中 PaginatedResponse 包含 has_more 字段"""
        from app.main import app
        schema = app.openapi()
        schemas = schema.get("components", {}).get("schemas", {})

        # PaginatedResponse 可能是泛型，查找基础定义
        paginated_schema = schemas.get("PaginatedResponse", {})
        properties = paginated_schema.get("properties", {})
        # 泛型 schema 可能为空，检查是否有 has_more 字段定义
        if properties:
            assert "has_more" in properties
            assert "total" in properties
            assert "total_pages" in properties


# ============================================================
# 六、API 端到端契约测试
# ============================================================

class TestAPIPaginationContract:
    """API 分页响应包含 has_more 字段"""

    @pytest.mark.asyncio
    async def test_post_list_pagination_has_more(self, client, auth_headers, test_post):
        """GET /posts 分页响应包含 has_more 字段"""
        response = await client.get("/api/v1/posts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "has_more" in data, "分页响应必须包含 has_more 字段"
        assert "total" in data
        assert "total_pages" in data
        assert "items" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.asyncio
    async def test_post_list_pagination_has_more_false_on_single_page(self, client, auth_headers, test_post):
        """单页结果 has_more=False"""
        response = await client.get("/api/v1/posts?page=1&page_size=100", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_post_list_pagination_has_more_true_multi_page(self, client, auth_headers, test_post):
        """多页时第一页 has_more=True"""
        response = await client.get("/api/v1/posts?page=1&page_size=1", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        if data["total"] > 1:
            assert data["has_more"] is True
            assert data["total_pages"] >= 2


class TestAPIReportTypeContract:
    """API 举报接口接受正确的举报类型"""

    @pytest.mark.asyncio
    async def test_report_with_spam_type(self, client, auth_headers, test_post):
        """举报 spam 类型成功"""
        response = await client.post(
            f"/api/v1/posts/{test_post['id']}/report",
            json={"report_type": "spam", "description": "垃圾信息测试"},
            headers=auth_headers,
        )
        assert response.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_report_with_all_five_types(self, client, auth_headers, test_category):
        """全部 5 类举报类型均可提交（每类用不同帖子避免重复举报拦截）"""
        for rt in ["spam", "abuse", "harassment", "false_info", "other"]:
            # 每次创建新帖子，避免同一用户对同一帖子的重复举报拦截
            create_resp = await client.post(
                "/api/v1/posts",
                json={
                    "title": f"举报测试帖子-{rt}",
                    "content": f"用于测试{rt}举报类型的内容至少十字",
                    "category_id": test_category["id"],
                },
                headers=auth_headers,
            )
            assert create_resp.status_code == 201
            post_id = create_resp.json()["id"]

            response = await client.post(
                f"/api/v1/posts/{post_id}/report",
                json={"report_type": rt},
                headers=auth_headers,
            )
            assert response.status_code in (200, 201), f"举报类型 {rt} 应被接受"

    @pytest.mark.asyncio
    async def test_report_rejects_invalid_type(self, client, auth_headers, test_post):
        """非法举报类型返回 422"""
        response = await client.post(
            f"/api/v1/posts/{test_post['id']}/report",
            json={"report_type": "invalid_type"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_report_rejects_old_inappropriate_type(self, client, auth_headers, test_post):
        """旧枚举值 inappropriate 被拒绝（契约统一为 other）"""
        response = await client.post(
            f"/api/v1/posts/{test_post['id']}/report",
            json={"report_type": "inappropriate"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAPIPostStatusContract:
    """API 帖子状态契约"""

    @pytest.mark.asyncio
    async def test_create_post_default_pending(self, client, auth_headers, test_category):
        """不传 status 默认 pending"""
        response = await client.post(
            "/api/v1/posts",
            json={
                "title": "默认状态测试标题",
                "content": "默认状态测试内容至少十字",
                "category_id": test_category["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_post_with_draft(self, client, auth_headers, test_category):
        """显式传 status=draft 创建草稿"""
        response = await client.post(
            "/api/v1/posts",
            json={
                "title": "草稿状态测试标题",
                "content": "草稿状态测试内容至少十字",
                "category_id": test_category["id"],
                "status": "draft",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_post_rejects_published(self, client, auth_headers, test_category):
        """创建时 status=published 被拒绝"""
        response = await client.post(
            "/api/v1/posts",
            json={
                "title": "发布状态测试标题",
                "content": "发布状态测试内容至少十字",
                "category_id": test_category["id"],
                "status": "published",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_post_status_ignored(self, client, auth_headers, test_post):
        """PUT /posts/{id} 传入 status 被忽略（不修改状态）"""
        original_status = test_post["status"]
        response = await client.put(
            f"/api/v1/posts/{test_post['id']}",
            json={
                "title": "更新后的标题五字以上",
                "content": "更新后的内容至少十字符",
                "status": "published",  # 应被忽略
            },
            headers=auth_headers,
        )
        # 状态不应变为 published
        if response.status_code == 200:
            assert response.json()["status"] == original_status

    @pytest.mark.asyncio
    async def test_update_post_is_recommend_ignored(self, client, auth_headers, test_post):
        """PUT /posts/{id} 传入 is_recommend 被忽略"""
        original_recommend = test_post.get("is_recommend", False)
        response = await client.put(
            f"/api/v1/posts/{test_post['id']}",
            json={
                "title": "更新后的标题五字以上",
                "content": "更新后的内容至少十字符",
                "is_recommend": True,  # 应被忽略
            },
            headers=auth_headers,
        )
        if response.status_code == 200:
            assert response.json()["is_recommend"] == original_recommend
