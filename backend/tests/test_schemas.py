"""T-E-01 单元测试：关键 Schema 校验

覆盖 PostCreate / PostTransitionCreate / ValidationCreate / ValidationStatsResponse。
"""
import pytest
from pydantic import ValidationError

from app.schemas.post import PostCreate, PostTransitionCreate, PostTransitionResponse
from app.schemas.interaction import (
    ValidationCreate, ValidationResponse, ValidationStatsResponse,
)


class TestPostCreate:
    """PostCreate Schema"""

    def test_valid_pending(self):
        """合法：status=pending"""
        p = PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="pending")
        assert p.status == "pending"

    def test_valid_draft(self):
        """合法：status=draft"""
        p = PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="draft")
        assert p.status == "draft"

    def test_default_status_is_pending(self):
        """不传 status 时默认 pending"""
        p = PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1)
        assert p.status == "pending"

    def test_invalid_status_published_rejected(self):
        """非法：status=published 被拒绝（创建时不能直接发布）"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="published")

    def test_invalid_status_expired_rejected(self):
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="expired")

    def test_invalid_status_archived_rejected(self):
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="内容至少要十个字符哦", category_id=1, status="archived")

    def test_title_too_short_rejected(self):
        """标题少于 5 字符被拒绝"""
        with pytest.raises(ValidationError):
            PostCreate(title="短", content="内容至少要十个字符哦", category_id=1)

    def test_title_too_long_rejected(self):
        """标题超过 200 字符被拒绝"""
        with pytest.raises(ValidationError):
            PostCreate(title="x" * 201, content="内容至少要十个字符哦", category_id=1)

    def test_content_too_short_rejected(self):
        """内容少于 10 字符被拒绝"""
        with pytest.raises(ValidationError):
            PostCreate(title="测试标题五字以上", content="短", category_id=1)

    def test_tags_max_five(self):
        """标签最多 5 个"""
        with pytest.raises(ValidationError):
            PostCreate(
                title="测试标题五字以上",
                content="内容至少要十个字符哦",
                category_id=1,
                tags=["a", "b", "c", "d", "e", "f"],  # 6 个
            )


class TestPostTransitionCreate:
    """PostTransitionCreate Schema"""

    def test_valid_target_status(self):
        """合法目标状态"""
        for status in ["draft", "pending", "published", "expired", "conflict", "archived"]:
            t = PostTransitionCreate(target_status=status)
            assert t.target_status == status

    def test_valid_alias_pending_review(self):
        """合法别名：pending_review"""
        t = PostTransitionCreate(target_status="pending_review")
        assert t.target_status == "pending_review"

    def test_invalid_target_status_rejected(self):
        """非法目标状态被拒绝"""
        with pytest.raises(ValidationError):
            PostTransitionCreate(target_status="invalid_status")

    def test_empty_target_status_rejected(self):
        with pytest.raises(ValidationError):
            PostTransitionCreate(target_status="")

    def test_reason_optional(self):
        """reason 可选"""
        t = PostTransitionCreate(target_status="published")
        assert t.reason is None

    def test_reason_max_length(self):
        """reason 最长 500"""
        t = PostTransitionCreate(target_status="published", reason="x" * 500)
        assert len(t.reason) == 500
        with pytest.raises(ValidationError):
            PostTransitionCreate(target_status="published", reason="x" * 501)


class TestValidationCreate:
    """ValidationCreate Schema（5 类 + 3 别名）"""

    def test_valid_five_types(self):
        """5 类正式类型"""
        for vtype in ["confirmation", "refutation", "update", "expiration_report", "conflict_report"]:
            v = ValidationCreate(validation_type=vtype)
            assert v.validation_type == vtype

    def test_valid_three_aliases(self):
        """3 类旧别名"""
        for vtype in ["valid", "invalid", "uncertain"]:
            v = ValidationCreate(validation_type=vtype)
            assert v.validation_type == vtype

    def test_invalid_type_rejected(self):
        """非法类型被拒绝"""
        with pytest.raises(ValidationError):
            ValidationCreate(validation_type="approved")

    def test_empty_type_rejected(self):
        with pytest.raises(ValidationError):
            ValidationCreate(validation_type="")

    def test_comment_optional(self):
        v = ValidationCreate(validation_type="confirmation")
        assert v.comment is None

    def test_comment_max_length(self):
        """comment 最长 500"""
        v = ValidationCreate(validation_type="confirmation", comment="x" * 500)
        assert len(v.comment) == 500
        with pytest.raises(ValidationError):
            ValidationCreate(validation_type="confirmation", comment="x" * 501)


class TestValidationStatsResponse:
    """ValidationStatsResponse Schema"""

    def test_default_all_zero(self):
        """默认所有计数为 0"""
        s = ValidationStatsResponse(post_id=1)
        assert s.valid_count == 0
        assert s.invalid_count == 0
        assert s.uncertain_count == 0
        assert s.confirmation_count == 0
        assert s.refutation_count == 0
        assert s.update_count == 0
        assert s.expiration_report_count == 0
        assert s.conflict_report_count == 0
        assert s.total_count == 0

    def test_default_validity_status(self):
        s = ValidationStatsResponse(post_id=1)
        assert s.validity_status == "valid"

    def test_custom_values(self):
        """自定义计数值"""
        s = ValidationStatsResponse(
            post_id=1,
            confirmation_count=5,
            refutation_count=2,
            total_count=7,
            validity_status="valid",
        )
        assert s.confirmation_count == 5
        assert s.refutation_count == 2
        assert s.total_count == 7


class TestPostTransitionResponse:
    """PostTransitionResponse Schema"""

    def test_basic_response(self):
        from datetime import datetime
        now = datetime.now()
        r = PostTransitionResponse(
            post_id=1,
            previous_status="pending",
            current_status="published",
            transitioned_at=now,
            transitioned_by=1,
        )
        assert r.post_id == 1
        assert r.previous_status == "pending"
        assert r.current_status == "published"
        assert r.transitioned_by == 1
