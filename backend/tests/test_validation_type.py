"""T-B-02 协同验证类型扩展单元测试

覆盖 5 类验证类型定义、别名映射、归一化函数。
"""
import pytest

from app.core.validation_type import (
    ValidationType,
    normalize_validation_type,
    is_valid_validation_type,
    get_canonical_types,
)


class TestValidationTypeConstants:
    """5 类验证类型常量定义完整性"""

    def test_all_five_types_defined(self):
        """5 类全部定义"""
        assert ValidationType.CONFIRMATION == "confirmation"
        assert ValidationType.REFUTATION == "refutation"
        assert ValidationType.UPDATE == "update"
        assert ValidationType.EXPIRATION_REPORT == "expiration_report"
        assert ValidationType.CONFLICT_REPORT == "conflict_report"

    def test_all_tuple_contains_exactly_five(self):
        """ALL 元组恰好包含 5 个类型，无重复"""
        assert len(ValidationType.ALL) == 5
        assert len(set(ValidationType.ALL)) == 5

    def test_all_types_fit_in_string_20(self):
        """所有类型值长度 <= 20（数据库字段为 String(20)）"""
        for vtype in ValidationType.ALL:
            assert len(vtype) <= 20, f"类型 {vtype} 长度超过 20"

    def test_longest_type_expiration_report(self):
        """最长类型为 expiration_report（17 字符），String(20) 足够"""
        max_len = max(len(t) for t in ValidationType.ALL)
        assert max_len == 17  # expiration_report
        assert max_len <= 20


class TestIsValidValidationType:
    """is_valid_validation_type 函数"""

    @pytest.mark.parametrize("vtype", list(ValidationType.ALL))
    def test_valid_canonical_types(self, vtype):
        """5 个正式类型全部有效"""
        assert is_valid_validation_type(vtype) is True

    def test_aliases_valid(self):
        """旧 3 类别名有效"""
        assert is_valid_validation_type("valid") is True
        assert is_valid_validation_type("invalid") is True
        assert is_valid_validation_type("uncertain") is True

    def test_invalid_type(self):
        """非法类型值无效"""
        assert is_valid_validation_type("unknown") is False
        assert is_valid_validation_type("") is False
        assert is_valid_validation_type("CONFIRMATION") is False  # 大小写敏感
        assert is_valid_validation_type("confirmation ") is False  # 含空格


class TestNormalizeValidationType:
    """normalize_validation_type 函数"""

    def test_normalize_aliases(self):
        """旧 3 类别名归一化为新 5 类正式名"""
        assert normalize_validation_type("valid") == "confirmation"
        assert normalize_validation_type("invalid") == "refutation"
        assert normalize_validation_type("uncertain") == "update"

    def test_normalize_canonical_unchanged(self):
        """正式名归一化后不变"""
        for vtype in ValidationType.ALL:
            assert normalize_validation_type(vtype) == vtype

    def test_normalize_unknown_unchanged(self):
        """未知值原样返回"""
        assert normalize_validation_type("unknown") == "unknown"


class TestLegacyCountMapping:
    """旧 Post.valid_count / invalid_count 兼容映射"""

    def test_confirmation_in_positive_set(self):
        """confirmation 计入 valid_count"""
        assert ValidationType.CONFIRMATION in ValidationType.LEGACY_POSITIVE_COUNT_TYPES

    def test_refutation_in_negative_set(self):
        """refutation 计入 invalid_count"""
        assert ValidationType.REFUTATION in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES

    def test_update_not_in_legacy_sets(self):
        """update 不计入旧字段"""
        assert ValidationType.UPDATE not in ValidationType.LEGACY_POSITIVE_COUNT_TYPES
        assert ValidationType.UPDATE not in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES

    def test_expiration_report_not_in_legacy_sets(self):
        """expiration_report 不计入旧字段"""
        assert ValidationType.EXPIRATION_REPORT not in ValidationType.LEGACY_POSITIVE_COUNT_TYPES
        assert ValidationType.EXPIRATION_REPORT not in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES

    def test_conflict_report_not_in_legacy_sets(self):
        """conflict_report 不计入旧字段"""
        assert ValidationType.CONFLICT_REPORT not in ValidationType.LEGACY_POSITIVE_COUNT_TYPES
        assert ValidationType.CONFLICT_REPORT not in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES


class TestGetCanonicalTypes:
    """get_canonical_types 函数"""

    def test_returns_five_types(self):
        """返回 5 个正式类型"""
        types = get_canonical_types()
        assert len(types) == 5
        assert types == {
            "confirmation", "refutation", "update",
            "expiration_report", "conflict_report"
        }

    def test_returns_copy(self):
        """返回集合的副本，修改不影响内部状态"""
        types = get_canonical_types()
        types.add("hacked")
        types2 = get_canonical_types()
        assert "hacked" not in types2


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_old_valid_alias_works(self):
        """旧值 valid 仍可用，归一化为 confirmation"""
        assert is_valid_validation_type("valid") is True
        assert normalize_validation_type("valid") == "confirmation"

    def test_old_invalid_alias_works(self):
        """旧值 invalid 仍可用，归一化为 refutation"""
        assert is_valid_validation_type("invalid") is True
        assert normalize_validation_type("invalid") == "refutation"

    def test_old_uncertain_alias_works(self):
        """旧值 uncertain 仍可用，归一化为 update"""
        assert is_valid_validation_type("uncertain") is True
        assert normalize_validation_type("uncertain") == "update"

    def test_legacy_count_mapping_preserves_old_behavior(self):
        """旧 valid/invalid 计数行为被保留"""
        # 旧逻辑：valid → valid_count+1，invalid → invalid_count+1
        # 新逻辑：confirmation → valid_count+1，refutation → invalid_count+1
        # 归一化后 valid→confirmation 仍在 LEGACY_POSITIVE_COUNT_TYPES 中
        assert normalize_validation_type("valid") in ValidationType.LEGACY_POSITIVE_COUNT_TYPES
        assert normalize_validation_type("invalid") in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES
