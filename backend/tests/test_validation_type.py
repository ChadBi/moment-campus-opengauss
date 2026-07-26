"""T-B-02 协同验证类型定义单元测试（2 类精简版）

FND-02.3: 修正为当前 2 类表逻辑现状。
当前 validation_type 只有 2 类（confirmation/refutation），
update/expiration_report/conflict_report 为历史废弃类型（数据库存量保留但不接受新提交）。
"""
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

    def test_deprecated_types_not_in_all(self):
        """历史废弃类型不在 ALL 元组中但仍定义为类属性（FND-01 契约 + GOV-01）

        FND-01.1 契约：UPDATE/EXPIRATION_REPORT/CONFLICT_REPORT 仍定义为类属性，
        供 schema 层（ValidationTypeEnum）与 GOV-01（post_change_reports 表）使用。
        ALL 元组仅含 2 类（validation_records 表处理的互斥投票）。
        """
        # 这些常量仍定义（FND-01 契约 + GOV-01）
        assert hasattr(ValidationType, "UPDATE")
        assert hasattr(ValidationType, "EXPIRATION_REPORT")
        assert hasattr(ValidationType, "CONFLICT_REPORT")
        # 但不在 ALL 元组中（validation_records 只处理 2 类）
        assert "update" not in ValidationType.ALL
        assert "expiration_report" not in ValidationType.ALL
        assert "conflict_report" not in ValidationType.ALL
        # ALL_FIVE 包含全部 5 类（schema 契约）
        assert "update" in ValidationType.ALL_FIVE
        assert "expiration_report" in ValidationType.ALL_FIVE
        assert "conflict_report" in ValidationType.ALL_FIVE


class TestIsValidValidationType:
    """is_valid_validation_type 函数"""

    @pytest.mark.parametrize("vtype", list(ValidationType.ALL))
    def test_valid_canonical_types(self, vtype):
        """2 个正式类型全部有效"""
        assert is_valid_validation_type(vtype) is True

    def test_aliases_valid(self):
        """旧 2 类别名有效"""
        assert is_valid_validation_type("valid") is True
        assert is_valid_validation_type("invalid") is True

    def test_deprecated_types_invalid(self):
        """历史废弃类型（update/expiration_report/conflict_report/uncertain）不再视为有效"""
        assert is_valid_validation_type("update") is False
        assert is_valid_validation_type("expiration_report") is False
        assert is_valid_validation_type("conflict_report") is False
        assert is_valid_validation_type("uncertain") is False

    def test_invalid_type(self):
        """非法类型值无效"""
        assert is_valid_validation_type("unknown") is False
        assert is_valid_validation_type("") is False
        assert is_valid_validation_type("CONFIRMATION") is False  # 大小写敏感
        assert is_valid_validation_type("confirmation ") is False  # 含空格


class TestNormalizeValidationType:
    """normalize_validation_type 函数"""

    def test_normalize_aliases(self):
        """旧 2 类别名归一化为正式名"""
        assert normalize_validation_type("valid") == "confirmation"
        assert normalize_validation_type("invalid") == "refutation"

    def test_normalize_canonical_unchanged(self):
        """正式名归一化后不变"""
        for vtype in ValidationType.ALL:
            assert normalize_validation_type(vtype) == vtype

    def test_normalize_unknown_unchanged(self):
        """未知值原样返回（含历史废弃类型）"""
        assert normalize_validation_type("unknown") == "unknown"
        # 历史废弃类型不在别名映射中，原样返回
        assert normalize_validation_type("update") == "update"
        assert normalize_validation_type("uncertain") == "uncertain"


class TestLegacyCountMapping:
    """旧 Post.valid_count / invalid_count 兼容映射"""

    def test_confirmation_in_positive_set(self):
        """confirmation 计入 valid_count"""
        assert ValidationType.CONFIRMATION in ValidationType.LEGACY_POSITIVE_COUNT_TYPES

    def test_refutation_in_negative_set(self):
        """refutation 计入 invalid_count"""
        assert ValidationType.REFUTATION in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES

    def test_legacy_sets_only_contain_two_types(self):
        """LEGACY 计数集合仅含 2 类正式类型"""
        assert ValidationType.LEGACY_POSITIVE_COUNT_TYPES == {ValidationType.CONFIRMATION}
        assert ValidationType.LEGACY_NEGATIVE_COUNT_TYPES == {ValidationType.REFUTATION}


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

    def test_legacy_count_mapping_preserves_old_behavior(self):
        """旧 valid/invalid 计数行为被保留"""
        # 旧逻辑：valid → valid_count+1，invalid → invalid_count+1
        # 新逻辑：confirmation → valid_count+1，refutation → invalid_count+1
        # 归一化后 valid→confirmation 仍在 LEGACY_POSITIVE_COUNT_TYPES 中
        assert normalize_validation_type("valid") in ValidationType.LEGACY_POSITIVE_COUNT_TYPES
        assert normalize_validation_type("invalid") in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES
