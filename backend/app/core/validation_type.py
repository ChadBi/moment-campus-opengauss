"""协同验证类型定义（T-B-02 精简版）

2 类协同验证类型：
- confirmation: 证实（用户确认信息真实有效）
- refutation: 证伪（用户指出信息有误）

每用户对每帖只能有一条验证记录，可在两类之间切换或取消。

向后兼容映射：
- valid       → confirmation
- invalid     → refutation

历史类型（已废弃，数据库存量数据保留但不接受新提交）：
- update / expiration_report / conflict_report / uncertain
"""
from typing import Set


class ValidationType:
    """协同验证类型常量

    所有值长度 <= 20，与数据库 validation_type 字段 String(20) 对应。
    """

    CONFIRMATION = "confirmation"            # 证实
    REFUTATION = "refutation"                # 证伪

    # 全部正式类型（2 类）
    ALL: tuple = (
        CONFIRMATION,
        REFUTATION,
    )

    # 别名映射：旧值 → 正式名（向后兼容）
    # - valid     → confirmation（证实信息有效）
    # - invalid   → refutation（证伪信息有误）
    ALIASES: dict = {
        "valid": CONFIRMATION,
        "invalid": REFUTATION,
    }

    # 旧 3 类正向统计字段映射（用于兼容 Post 模型的 valid_count/invalid_count）
    # - confirmation → valid_count
    # - refutation   → invalid_count
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
        True 若 vtype 为 2 类之一或已知别名
    """
    return vtype in ValidationType.ALL or vtype in ValidationType.ALIASES


def get_canonical_types() -> Set[str]:
    """获取全部 2 类正式类型（不含别名）"""
    return set(ValidationType.ALL)
