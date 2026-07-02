"""协同验证类型定义（T-B-02）

5 类协同验证类型：
- confirmation: 证实（用户确认信息真实有效）
- refutation: 证伪（用户指出信息有误）
- update: 补充更新（用户提供更新的信息）
- expiration_report: 过期上报（用户报告信息已过期）
- conflict_report: 冲突上报（用户报告与其他信息冲突）

向后兼容映射：
- valid       → confirmation
- invalid     → refutation
- uncertain   → update（语义最接近：补充信息）

设计依据：
- docs/21_后续开发任务清单.md T-B-02
- docs/25_数据库概念模型设计.md ValidationRecord 实体
- docs/27_数据库物理模型设计.md SP04 协同验证统计存储过程
"""
from typing import Set


class ValidationType:
    """协同验证类型常量

    所有值长度 <= 20，与数据库 validation_type 字段 String(20) 对应。
    """

    CONFIRMATION = "confirmation"            # 证实
    REFUTATION = "refutation"                # 证伪
    UPDATE = "update"                        # 补充更新
    EXPIRATION_REPORT = "expiration_report"  # 过期上报
    CONFLICT_REPORT = "conflict_report"      # 冲突上报

    # 全部正式类型（5 类）
    ALL: tuple = (
        CONFIRMATION,
        REFUTATION,
        UPDATE,
        EXPIRATION_REPORT,
        CONFLICT_REPORT,
    )

    # 别名映射：旧 3 类 → 新 5 类（向后兼容）
    # - valid     → confirmation（证实信息有效）
    # - invalid   → refutation（证伪信息有误）
    # - uncertain → update（"不确定"语义最接近"补充更新"）
    ALIASES: dict = {
        "valid": CONFIRMATION,
        "invalid": REFUTATION,
        "uncertain": UPDATE,
    }

    # 旧 3 类正向统计字段映射（用于兼容 Post 模型的 valid_count/invalid_count）
    # - confirmation → valid_count
    # - refutation   → invalid_count
    # - 其他 3 类不计入旧字段
    LEGACY_POSITIVE_COUNT_TYPES: Set[str] = {CONFIRMATION}
    LEGACY_NEGATIVE_COUNT_TYPES: Set[str] = {REFUTATION}


def normalize_validation_type(vtype: str) -> str:
    """将验证类型归一化为正式名（别名 → 正式名）

    Args:
        vtype: 原始类型值，可能为别名（如 "valid"）

    Returns:
        归一化后的正式类型名；未知值原样返回
    """
    return ValidationType.ALIASES.get(vtype, vtype)


def is_valid_validation_type(vtype: str) -> bool:
    """判断验证类型是否有效（含别名）

    Args:
        vtype: 待判断的类型值

    Returns:
        True 若 vtype 为 5 类之一或已知别名
    """
    return vtype in ValidationType.ALL or vtype in ValidationType.ALIASES


def get_canonical_types() -> Set[str]:
    """获取全部 5 类正式类型（不含别名）"""
    return set(ValidationType.ALL)
