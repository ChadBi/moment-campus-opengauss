"""协同验证类型唯一契约测试。"""
import pytest

from app.core.validation_type import (
    ValidationType,
    normalize_validation_type,
    is_valid_validation_type,
    get_canonical_types,
)


class TestValidationTypeConstants:
    """2 类验证类型常量定义完整性"""

    def test_all_two_types_defined(self):
        """2 类全部定义"""
        assert ValidationType.CONFIRMATION == "confirmation"
        assert ValidationType.REFUTATION == "refutation"

    def test_all_tuple_contains_exactly_two(self):
        """ALL 元组恰好包含 2 个类型，无重复"""
        assert len(ValidationType.ALL) == 2
        assert len(set(ValidationType.ALL)) == 2

    def test_all_types_fit_in_string_20(self):
        """所有类型值长度 <= 20（数据库字段为 String(20)）"""
        for vtype in ValidationType.ALL:
            assert len(vtype) <= 20, f"类型 {vtype} 长度超过 20"

    @pytest.mark.parametrize(
        "attribute",
        [
            "UPDATE",
            "EXPIRATION_REPORT",
            "CONFLICT_REPORT",
            "ALL_FIVE",
            "REPORT_TYPES",
            "ALIASES",
            "LEGACY_POSITIVE_COUNT_TYPES",
            "LEGACY_NEGATIVE_COUNT_TYPES",
        ],
    )
    def test_deprecated_contract_attributes_removed(self, attribute):
        assert not hasattr(ValidationType, attribute)


class TestIsValidValidationType:
    """is_valid_validation_type 函数"""

    @pytest.mark.parametrize("vtype", list(ValidationType.ALL))
    def test_valid_canonical_types(self, vtype):
        """2 个正式类型全部有效"""
        assert is_valid_validation_type(vtype) is True

    @pytest.mark.parametrize(
        "vtype",
        ["update", "expiration_report", "conflict_report", "valid", "invalid", "uncertain"],
    )
    def test_non_canonical_types_invalid(self, vtype):
        assert is_valid_validation_type(vtype) is False

    def test_invalid_type(self):
        """非法类型值无效"""
        assert is_valid_validation_type("unknown") is False
        assert is_valid_validation_type("") is False
        assert is_valid_validation_type("CONFIRMATION") is False  # 大小写敏感
        assert is_valid_validation_type("confirmation ") is False  # 含空格


class TestNormalizeValidationType:
    """normalize_validation_type 函数"""

    def test_normalize_canonical_unchanged(self):
        """正式名归一化后不变"""
        for vtype in ValidationType.ALL:
            assert normalize_validation_type(vtype) == vtype

    @pytest.mark.parametrize("vtype", ["valid", "invalid", "update", "unknown"])
    def test_normalize_rejects_non_canonical_type(self, vtype):
        with pytest.raises(ValueError):
            normalize_validation_type(vtype)


class TestGetCanonicalTypes:
    """get_canonical_types 函数"""

    def test_returns_two_types(self):
        """返回 2 个正式类型"""
        types = get_canonical_types()
        assert len(types) == 2
        assert types == {"confirmation", "refutation"}

    def test_returns_copy(self):
        """返回集合的副本，修改不影响内部状态"""
        types = get_canonical_types()
        types.add("hacked")
        types2 = get_canonical_types()
        assert "hacked" not in types2
